# SPDX-License-Identifier: GPL-3.0-or-later
"""Offline checks for Aether Beam's scheduler. No dpkg, flatpak or root needed."""
import importlib.util
import os
import stat
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location('beam', Path(__file__).with_name('beam.py'))
beam = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(beam)


def plan(*apps):
    return {'schema': 1, 'apps': list(apps)}


def flatpak(name, **kw):
    item = {'id': name, 'source': 'flatpak', 'ref': 'org.example.' + name.capitalize() + '/x86_64/stable'}
    item.update(kw)
    return item


def deb(name, digest='a' * 64, **kw):
    item = {'id': name, 'source': 'deb', 'file': str(beam.DEB_ROOT / (name + '.deb')), 'sha256': digest}
    item.update(kw)
    return item


class FakeBackend:
    """Records real overlap instead of trusting the scheduler's own claims."""

    def __init__(self, fail=(), delay=0.15, commit_delay=0.05):
        self.fail = set(fail)
        self.delay = delay
        self.commit_delay = commit_delay
        self.lock = threading.Lock()
        self.active = 0
        self.peak = 0
        self.commit_active = 0
        self.commit_peak = 0
        self.prepared = []
        self.commits = []

    def prepare(self, app, stop=None):
        with self.lock:
            self.active += 1
            self.peak = max(self.peak, self.active)
        try:
            time.sleep(self.delay)
            if app['id'] in self.fail:
                raise RuntimeError('staged failure for ' + app['id'])
            with self.lock:
                self.prepared.append(app['id'])
        finally:
            with self.lock:
                self.active -= 1

    def commit(self, app):
        with self.lock:
            self.commit_active += 1
            self.commit_peak = max(self.commit_peak, self.commit_active)
        try:
            time.sleep(self.commit_delay)
            self.commits.append(app['id'])
        finally:
            with self.lock:
                self.commit_active -= 1


class PlanTests(unittest.TestCase):
    def test_accepts_mixed_sources(self):
        apps = beam.validate_plan(plan(flatpak('firefox'), deb('ripgrep')))
        self.assertEqual([a['source'] for a in apps], ['flatpak', 'deb'])

    def test_rejects_wrong_architecture(self):
        with self.assertRaisesRegex(ValueError, 'targets'):
            beam.validate_plan(plan(flatpak('firefox', arch='amd64')), arch='arm64')
        self.assertTrue(beam.validate_plan(plan(flatpak('firefox', arch='all')), arch='arm64'))

    def test_knows_arm64_spellings(self):
        self.assertTrue(beam.validate_plan(plan(deb('curl', arch='aarch64')), arch='arm64'))
        self.assertTrue(beam.validate_plan(plan(deb('curl', arch='arm64')), arch='aarch64'))

    def test_rejects_duplicate_and_unknown_dependency(self):
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            beam.validate_plan(plan(flatpak('a'), flatpak('a')))
        with self.assertRaisesRegex(ValueError, 'not in this plan'):
            beam.validate_plan(plan(flatpak('a', depends=['ghost'])))

    def test_rejects_cycle(self):
        with self.assertRaisesRegex(ValueError, 'cycle'):
            beam.validate_plan(plan(flatpak('a', depends=['b']), flatpak('b', depends=['a'])))

    def test_rejects_shell_metacharacters(self):
        for ref in ('org.example.Pkg/x86_64/stable; id', '$(id)', 'org.example.Pkg`id`'):
            with self.assertRaises(ValueError):
                beam.validate_plan(plan({'id': 'x', 'source': 'flatpak', 'ref': ref}))

    def test_rejects_package_outside_cache(self):
        for path in ('/etc/passwd', '/var/cache/aether-update/../../etc/shadow', '/var/cache/aether-update/x.txt'):
            with self.assertRaises(ValueError):
                beam.validate_plan(plan({'id': 'x', 'source': 'deb', 'file': path, 'sha256': 'a' * 64}))

    def test_rejects_missing_digest(self):
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            beam.validate_plan(plan({'id': 'x', 'source': 'deb', 'file': str(beam.DEB_ROOT / 'x.deb')}))

    def test_rejects_oversized_plan(self):
        with self.assertRaises(ValueError):
            beam.validate_plan(plan(*[flatpak('app%d' % i) for i in range(beam.MAX_APPS + 1)]))


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.state = beam.State(Path(self.temp.name))

    def tearDown(self):
        self.temp.cleanup()

    def test_prepare_runs_in_parallel_and_commit_does_not(self):
        apps = beam.validate_plan(plan(*[flatpak('app%d' % i) for i in range(4)]))
        backend = FakeBackend()
        receipt = beam.run_plan(apps, backend=backend, state=self.state, workers=4)
        self.assertTrue(receipt['ok'])
        self.assertGreater(backend.peak, 1, 'downloads did not overlap')
        self.assertEqual(backend.commit_peak, 1, 'package transactions overlapped')
        self.assertEqual(receipt['counts']['installed'], 4)

    def test_worker_cap_is_respected(self):
        apps = beam.validate_plan(plan(*[flatpak('app%d' % i) for i in range(6)]))
        backend = FakeBackend()
        beam.run_plan(apps, backend=backend, state=self.state, workers=2)
        self.assertLessEqual(backend.peak, 2)

    def test_commit_follows_dependencies(self):
        apps = beam.validate_plan(plan(flatpak('leaf', depends=['trunk']), flatpak('trunk')))
        backend = FakeBackend()
        beam.run_plan(apps, backend=backend, state=self.state, workers=2)
        self.assertLess(backend.commits.index('trunk'), backend.commits.index('leaf'))

    def test_failure_is_isolated_and_blocks_dependents(self):
        apps = beam.validate_plan(plan(flatpak('broken'), flatpak('child', depends=['broken']), flatpak('fine')))
        backend = FakeBackend(fail={'broken'})
        receipt = beam.run_plan(apps, backend=backend, state=self.state, workers=3)
        states = {a['id']: a['state'] for a in receipt['applications']}
        self.assertEqual(states, {'broken': 'failed', 'child': 'blocked', 'fine': 'installed'})
        self.assertFalse(receipt['ok'])
        self.assertIn('staged failure', [a['error'] for a in receipt['applications'] if a['id'] == 'broken'][0])

    def test_commit_failure_is_recorded_not_raised(self):
        class Refusing(FakeBackend):
            def commit(self, app):
                super().commit(app)
                raise RuntimeError('dpkg refused')
        apps = beam.validate_plan(plan(flatpak('a')))
        receipt = beam.run_plan(apps, backend=Refusing(), state=self.state, workers=1)
        self.assertEqual(receipt['applications'][0]['state'], 'failed')
        self.assertIn('dpkg refused', receipt['applications'][0]['error'])

    def test_second_run_reuses_the_journal(self):
        apps = beam.validate_plan(plan(flatpak('a')))
        first, second = FakeBackend(), FakeBackend()
        beam.run_plan(apps, backend=first, state=self.state, workers=1)
        receipt = beam.run_plan(apps, backend=second, state=self.state, workers=1)
        self.assertEqual(second.prepared, [])
        self.assertEqual(receipt['counts']['installed'], 1)
        self.assertEqual(second.commits, [])

    def test_fresh_ignores_the_journal(self):
        apps = beam.validate_plan(plan(flatpak('a')))
        beam.run_plan(apps, backend=FakeBackend(), state=self.state, workers=1)
        again = FakeBackend()
        beam.run_plan(apps, backend=again, state=self.state, workers=1, resume=False)
        self.assertEqual(again.prepared, ['a'])

    def test_cancellation_is_recorded(self):
        apps = beam.validate_plan(plan(*[flatpak('app%d' % i) for i in range(3)]))
        stop = threading.Event()
        stop.set()
        receipt = beam.run_plan(apps, backend=FakeBackend(), state=self.state, workers=2, stop=stop)
        self.assertTrue(receipt['cancelled'])
        self.assertEqual(receipt['counts']['installed'], 0)
        self.assertEqual(receipt['counts']['cancelled'], 3)

    def test_receipt_is_private_and_arch_stamped(self):
        apps = beam.validate_plan(plan(flatpak('a')))
        receipt = beam.run_plan(apps, backend=FakeBackend(), state=self.state, workers=1)
        path = Path(self.temp.name) / 'receipt.json'
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(receipt['architecture'], beam.native_arch()[1])


class BackendTests(unittest.TestCase):
    def test_prepare_rejects_digest_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'pkg.deb'
            path.write_bytes(b'not the package the plan describes')
            backend = beam.SystemBackend(run=lambda *a, **k: None)
            with self.assertRaisesRegex(ValueError, 'digest'):
                backend.prepare({'id': 'pkg', 'source': 'deb', 'file': str(path), 'sha256': 'b' * 64})

    def test_commit_never_uses_a_shell(self):
        calls = []
        backend = beam.SystemBackend(run=lambda argv, **kw: calls.append((argv, kw)))
        backend.commit({'id': 'pkg', 'source': 'flatpak', 'remote': 'flathub',
                        'ref': 'org.example.Pkg/x86_64/stable'})
        argv, options = calls[0]
        self.assertIsInstance(argv, list)
        self.assertNotIn('shell', options)
        self.assertEqual(argv[:4], ['flatpak', 'install', '--noninteractive', '--user'])

    def test_deb_commit_elevates_with_pkexec(self):
        calls = []
        backend = beam.SystemBackend(run=lambda argv, **kw: calls.append(argv))
        backend.commit({'id': 'pkg', 'source': 'deb', 'file': str(beam.DEB_ROOT / 'pkg.deb')})
        self.assertEqual(calls[0][:2], ['pkexec', '/usr/bin/dpkg'])


if __name__ == '__main__':
    sys.exit(unittest.main())
