#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Aether Beam — install several applications at once, without breaking dpkg.

A package database has one writer. Running two `dpkg` transactions together
corrupts it, and flatpak refuses a concurrent deploy for the same reason. So
Beam splits every install into two stages:

    prepare   download and verify. Safe to run concurrently. This is the slow
              part (network, disk, digest checks) and it is what gets threaded.
    commit    mutate the system. Always serialized, dependency ordered, and
              guarded by a file lock that also covers a second Beam process.

Jobs are a validated JSON plan. Nothing here builds a shell command line: every
argument is a list element, and every string is checked against a narrow pattern
before it reaches a subprocess.
"""
import argparse
import json
import os
import platform
import re
import secrets
import stat
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SCHEMA = 1
ARCHES = {'x86_64': 'amd64', 'amd64': 'amd64', 'aarch64': 'arm64', 'arm64': 'arm64',
          'i686': 'i386', 'armv7l': 'armhf'}
SOURCES = ('flatpak', 'deb')
MAX_APPS = 64
MAX_WORKERS = 8
DEFAULT_WORKERS = min(os.cpu_count() or 1, MAX_WORKERS)
NAME = re.compile(r'[a-z0-9][a-z0-9+.-]{0,127}\Z')
REF = re.compile(r'[A-Za-z0-9][A-Za-z0-9._+@-]{0,63}(/[A-Za-z0-9._+@-]{1,64}){0,2}\Z')
DEB_ROOT = Path('/var/cache/aether-update')
TERMINAL = ('installed', 'failed', 'blocked', 'cancelled')


def native_arch():
    machine = platform.machine()
    if machine not in ARCHES:
        raise ValueError('Unsupported architecture: ' + machine)
    return machine, ARCHES[machine]


def default_state():
    return Path(os.environ.get('AETHER_BEAM_STATE') or
                Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'aether/beam')


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix=path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, 0o600)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def validate_plan(value, arch=None):
    """Return normalized apps. Raises ValueError on anything ambiguous."""
    if not isinstance(value, dict) or value.get('schema') != SCHEMA:
        raise ValueError('Plan must be an object with "schema": %d' % SCHEMA)
    apps = value.get('apps')
    if not isinstance(apps, list) or not 0 < len(apps) <= MAX_APPS:
        raise ValueError('Plan must list 1-%d applications' % MAX_APPS)
    _, native = native_arch()
    native = arch or native
    if native not in ARCHES.values() and native not in ARCHES:
        raise ValueError('Unknown architecture: ' + str(arch))
    native = ARCHES.get(native, native)
    clean, seen = [], set()
    for raw in apps:
        if not isinstance(raw, dict):
            raise ValueError('Each application must be an object')
        app_id = raw.get('id')
        if not isinstance(app_id, str) or not NAME.fullmatch(app_id):
            raise ValueError('Invalid application id')
        if app_id in seen:
            raise ValueError('Duplicate application id: ' + app_id)
        seen.add(app_id)
        source = raw.get('source')
        if source not in SOURCES:
            raise ValueError('Application %s: source must be one of %s' % (app_id, ', '.join(SOURCES)))
        target = raw.get('arch', native)
        target = ARCHES.get(target, target) if target != 'all' else 'all'
        if target not in ('all', native):
            raise ValueError('Application %s targets %s but this system is %s' % (app_id, target, native))
        depends = raw.get('depends', [])
        if not isinstance(depends, list) or not all(isinstance(d, str) and NAME.fullmatch(d) for d in depends):
            raise ValueError('Application %s: invalid dependency list' % app_id)
        item = {'id': app_id, 'source': source, 'arch': target, 'depends': sorted(set(depends))}
        if source == 'flatpak':
            ref = raw.get('ref')
            if not isinstance(ref, str) or not REF.fullmatch(ref):
                raise ValueError('Application %s: invalid Flatpak reference' % app_id)
            item['ref'] = ref
            remote = raw.get('remote', 'flathub')
            if not isinstance(remote, str) or not NAME.fullmatch(remote):
                raise ValueError('Application %s: invalid Flatpak remote' % app_id)
            item['remote'] = remote
        else:
            path = raw.get('file')
            if not isinstance(path, str) or not path.startswith(DEB_ROOT.as_posix() + '/'):
                raise ValueError('Application %s: packages must come from %s' % (app_id, DEB_ROOT))
            if not path.endswith('.deb') or '/../' in path or '//' in path:
                raise ValueError('Application %s: invalid package path' % app_id)
            digest = raw.get('sha256')
            if not isinstance(digest, str) or not re.fullmatch(r'[a-f0-9]{64}', digest):
                raise ValueError('Application %s: a SHA-256 digest is required' % app_id)
            item['file'] = path
            item['sha256'] = digest
        clean.append(item)
    known = {a['id'] for a in clean}
    for app in clean:
        missing = [d for d in app['depends'] if d not in known]
        if missing:
            raise ValueError('Application %s depends on something not in this plan: %s' %
                             (app['id'], ', '.join(missing)))
    check_cycles(clean)
    return clean


def check_cycles(apps):
    graph = {a['id']: a['depends'] for a in apps}
    state = {}

    def visit(node, trail):
        if state.get(node) == 'done':
            return
        if state.get(node) == 'open':
            raise ValueError('Dependency cycle: ' + ' → '.join(trail + [node]))
        state[node] = 'open'
        for dep in graph[node]:
            visit(dep, trail + [node])
        state[node] = 'done'

    for node in graph:
        visit(node, [])


class State:
    """Resumable journal. A finished application is not downloaded twice."""

    def __init__(self, directory):
        self.dir = Path(directory)
        if self.dir.is_symlink():
            raise ValueError('Beam state must not be a symlink')
        self.dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.dir / 'journal.json'
        self.lock = threading.Lock()

    def read(self):
        try:
            value = json.loads(self.path.read_text(encoding='utf-8'))
            return value if isinstance(value, dict) and isinstance(value.get('apps'), dict) else {'schema': 1, 'apps': {}}
        except (FileNotFoundError, ValueError):
            return {'schema': 1, 'apps': {}}

    def record(self, app_id, **fields):
        with self.lock:
            value = self.read()
            entry = value['apps'].setdefault(app_id, {})
            entry.update(fields)
            entry['at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            atomic_json(self.path, value)

    def installed(self):
        return {k for k, v in self.read()['apps'].items() if v.get('state') == 'installed'}


class FileLock:
    """Coordinate commits between Beam processes; dpkg's own lock is separate."""

    def __init__(self, directory, seconds=600):
        self.path = Path(directory) / 'commit.lock'
        self.seconds = seconds

    def __enter__(self):
        import fcntl
        self.handle = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        deadline = time.monotonic() + self.seconds
        while True:
            try:
                fcntl.flock(self.handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except BlockingIOError:
                if time.monotonic() > deadline:
                    os.close(self.handle)
                    raise RuntimeError('Another install holds the package lock')
                time.sleep(0.1)

    def __exit__(self, *_):
        import fcntl
        try:
            fcntl.flock(self.handle, fcntl.LOCK_UN)
        finally:
            os.close(self.handle)


class SystemBackend:
    """Runs the image's own packaging front-ends. No shell, no user strings."""

    def __init__(self, run=subprocess.run):
        self.run = run

    def prepare(self, app, stop=None):
        if app['source'] == 'flatpak':
            # --no-deploy downloads and verifies; deployment happens in commit.
            self.run(['flatpak', 'install', '--noninteractive', '--user', '--no-deploy',
                      app['remote'], app['ref']], check=True, capture_output=True, timeout=3600)
            return
        path = Path(app['file'])
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode):
            raise ValueError('%s is not a regular file' % app['id'])
        if info.st_size > 4 * 1024 ** 3:
            raise ValueError('%s is larger than 4 GiB' % app['id'])
        import hashlib
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(block)
        if digest.hexdigest() != app['sha256']:
            raise ValueError('%s does not match its recorded digest' % app['id'])

    def commit(self, app):
        if app['source'] == 'flatpak':
            self.run(['flatpak', 'install', '--noninteractive', '--user',
                      app['remote'], app['ref']], check=True, capture_output=True, timeout=3600)
            return
        self.run(['pkexec', '/usr/bin/dpkg', '--install', app['file']],
                 check=True, capture_output=True, timeout=3600)


def run_plan(apps, *, backend=None, state=None, workers=DEFAULT_WORKERS, emit=None,
             stop=None, resume=True):
    """Prepare concurrently, commit one at a time. Returns a receipt."""
    backend = backend or SystemBackend()
    state = state or State(default_state())
    emit = emit or (lambda event: None)
    stop = stop or threading.Event()
    workers = max(1, min(int(workers), MAX_WORKERS, len(apps) or 1))
    status = {a['id']: 'pending' for a in apps}
    errors = {}
    finished = state.installed() if resume else set()
    meta = threading.Lock()
    wake = threading.Event()
    started = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    for app in apps:
        if app['id'] in finished:
            status[app['id']] = 'installed'
            emit({'event': 'resumed', 'id': app['id']})

    def set_status(app_id, value):
        with meta:
            status[app_id] = value
        wake.set()

    def prepare(app):
        if stop.is_set():
            set_status(app['id'], 'cancelled')
            return
        try:
            emit({'event': 'prepare', 'id': app['id'], 'source': app['source']})
            backend.prepare(app, stop=stop)
            set_status(app['id'], 'prepared')
        except Exception as error:  # A single failure must not stop the others.
            errors[app['id']] = str(error)[:500]
            emit({'event': 'error', 'id': app['id'], 'stage': 'prepare', 'error': errors[app['id']]})
            set_status(app['id'], 'failed')

    def commit(app):
        app_id = app['id']
        if stop.is_set():
            set_status(app_id, 'cancelled')
            return
        emit({'event': 'commit', 'id': app_id})
        try:
            with FileLock(state.dir):
                backend.commit(app)
        except Exception as error:
            errors[app_id] = str(error)[:500]
            emit({'event': 'error', 'id': app_id, 'stage': 'commit', 'error': errors[app_id]})
            set_status(app_id, 'failed')
            return
        state.record(app_id, state='installed', source=app['source'],
                     ref=app.get('ref') or app.get('file'))
        set_status(app_id, 'installed')
        emit({'event': 'installed', 'id': app_id})

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for app in apps:
            if status[app['id']] == 'pending':
                pool.submit(prepare, app)
        while True:
            progressed = False
            for app in apps:
                app_id = app['id']
                if status[app_id] != 'prepared':
                    continue
                deps = [status[d] for d in app['depends']]
                if any(value in ('failed', 'blocked', 'cancelled') for value in deps):
                    set_status(app_id, 'blocked')
                    progressed = True
                elif all(value == 'installed' for value in deps):
                    commit(app)
                    progressed = True
            if all(value in TERMINAL for value in status.values()):
                break
            if not progressed:
                wake.wait(0.25)
                wake.clear()
            elif wake.is_set():
                wake.clear()

    receipt = {
        'schema': 1,
        'started': started,
        'finished': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'workers': workers,
        'architecture': native_arch()[1],
        'applications': [{'id': a['id'], 'source': a['source'], 'state': status[a['id']],
                          'depends': a['depends'], 'error': errors.get(a['id'])} for a in apps],
        'counts': {value: sum(1 for s in status.values() if s == value)
                   for value in ('installed', 'failed', 'blocked', 'cancelled')},
        'cancelled': stop.is_set(),
    }
    receipt['ok'] = receipt['counts']['installed'] == len(apps)
    atomic_json(state.dir / 'receipt.json', receipt)
    emit({'event': 'finished', 'ok': receipt['ok'], 'counts': receipt['counts']})
    return receipt


def read_plan(path):
    raw = Path(path).read_bytes()
    if len(raw) > 256 * 1024:
        raise ValueError('Plan is larger than 256 KiB')
    return validate_plan(json.loads(raw))


def main():
    parser = argparse.ArgumentParser(prog='aether-beam',
                                     description='Install several applications at once.')
    commands = parser.add_subparsers(dest='action', required=True)
    install = commands.add_parser('install', help='prepare in parallel, commit in order')
    install.add_argument('plan', help='JSON plan file')
    install.add_argument('--workers', type=int, default=DEFAULT_WORKERS,
                         help='concurrent prepare slots (1-%d, default %d)' % (MAX_WORKERS, DEFAULT_WORKERS))
    install.add_argument('--state', default=str(default_state()))
    install.add_argument('--fresh', action='store_true', help='ignore the journal and start over')
    install.add_argument('--json', action='store_true', help='print only the receipt')
    install.add_argument('--events', action='store_true', help='stream progress as JSON lines on stderr')
    commands.add_parser('status', help='show the last receipt')
    plan = commands.add_parser('plan', help='validate a plan and print it without installing')
    plan.add_argument('file')
    parser.add_argument('--state', dest='global_state', default=None)
    args = parser.parse_args()
    if args.action == 'plan':
        print(json.dumps(validate_plan(json.loads(Path(args.file).read_text())), indent=2))
        return 0
    state_dir = args.global_state or getattr(args, 'state', None) or str(default_state())
    if args.action == 'status':
        receipt = Path(state_dir) / 'receipt.json'
        if not receipt.exists():
            print('No install has been recorded in %s.' % state_dir)
            return 0
        print(receipt.read_text())
        return 0
    apps = read_plan(args.plan)
    emit = None
    if args.events:
        emit = lambda event: print(json.dumps(event), file=sys.stderr, flush=True)
    elif not args.json:
        def emit(event):
            if event['event'] == 'prepare':
                print('  fetching  ' + event['id'])
            elif event['event'] == 'commit':
                print('  installing ' + event['id'])
            elif event['event'] == 'error':
                print('  failed    %s: %s' % (event['id'], event['error']))
            elif event['event'] == 'resumed':
                print('  already installed  ' + event['id'])
    receipt = run_plan(apps, state=State(state_dir), workers=args.workers, emit=emit,
                       resume=not args.fresh)
    if args.json:
        print(json.dumps(receipt))
    else:
        counts = receipt['counts']
        print('Installed %d of %d. %d failed, %d blocked, %d cancelled.'
              % (counts['installed'], len(apps), counts['failed'], counts['blocked'], counts['cancelled']))
        print('Receipt: ' + str(Path(state_dir) / 'receipt.json'))
    return 0 if receipt['ok'] else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError, TypeError) as error:
        print('aether-beam: ' + str(error), file=sys.stderr)
        sys.exit(2)
