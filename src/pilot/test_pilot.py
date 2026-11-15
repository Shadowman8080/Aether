# SPDX-License-Identifier: GPL-3.0-or-later
"""Offline checks for Aether Pilot. Nothing here runs a privileged command."""
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

HERE = Path(__file__).resolve().parent

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

pilot = load('pilot', HERE / 'pilot.py')
admin = importlib.machinery.SourceFileLoader('pilot_admin', str(HERE / 'aether-pilot-admin')).load_module()


def catalog(**changes):
    value = json.loads((HERE / 'actions.json').read_text())
    value.update(changes)
    return value


class Temp(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'XDG_STATE_HOME': self.temp.name, 'AETHER_PILOT_STATE': ''})
        self.env.start()
        os.environ.pop('AETHER_PILOT_STATE', None)
        self.actions = pilot.catalog(HERE / 'actions.json')

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()


class CatalogTests(Temp):
    def test_shipped_catalog_is_valid(self):
        self.assertGreaterEqual(len(self.actions), 8)
        for action in self.actions.values():
            self.assertTrue(action['argv'][0].startswith('/'))
            self.assertFalse(action['privilege'] == 'admin' and action['argv'][0].startswith('/usr/bin/flatpak'))

    def test_rejects_duplicate_ids(self):
        value = catalog()
        value['actions'].append(dict(value['actions'][0]))
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            pilot.validate_catalog(value)

    def test_rejects_shell_metacharacters_in_argv(self):
        for token in ('; rm -rf /', '$(id)', 'a|b', 'x\ny'):
            value = catalog()
            value['actions'][0]['argv'] = ['/usr/bin/aether-security-status', token]
            with self.assertRaises(ValueError):
                pilot.validate_catalog(value)

    def test_rejects_undeclared_and_unused_parameters(self):
        value = catalog()
        value['actions'][0]['argv'] = ['/usr/bin/tool', '{nope}']
        with self.assertRaisesRegex(ValueError, 'undeclared'):
            pilot.validate_catalog(value)
        value = catalog()
        value['actions'][0]['params'] = {'unused': {'type': 'pattern', 'pattern': 'x+'}}
        with self.assertRaisesRegex(ValueError, 'use every declared parameter'):
            pilot.validate_catalog(value)

    def test_rejects_bad_risk_and_choice(self):
        value = catalog()
        value['actions'][0]['risk'] = 'harmless'
        with self.assertRaises(ValueError):
            pilot.validate_catalog(value)
        value = catalog()
        value['actions'][0]['params'] = {'x': {'type': 'choice', 'values': ['$(id)']}}
        with self.assertRaises(ValueError):
            pilot.validate_catalog(value)

    def test_parameter_pattern_is_compiled(self):
        value = catalog()
        value['actions'][0]['params'] = {'x': {'type': 'pattern', 'pattern': '('}}
        with self.assertRaises(ValueError):
            pilot.validate_catalog(value)


class SuggestionTests(Temp):
    def test_matches_phrase_without_inventing_arguments(self):
        proposals = pilot.propose('install app', self.actions)
        self.assertEqual(proposals[0]['action'], 'install.flatpak')
        self.assertEqual(proposals[0]['missing'], ['ref'])

    def test_extracts_a_valid_application_reference(self):
        proposal = pilot.propose('install app org.example.Tool', self.actions)[0]
        self.assertEqual(proposal['params'], {'ref': 'org.example.Tool'})
        self.assertEqual(proposal['command'], ['/usr/bin/flatpak', 'install', '--noninteractive',
                                               '--user', 'org.example.Tool'])

    def test_unknown_request_proposes_nothing(self):
        self.assertEqual(pilot.propose('write me a poem about weather', self.actions), [])

    def test_read_action_needs_no_confirmation(self):
        proposal = pilot.propose('what is my security status', self.actions)[0]
        self.assertEqual(proposal['risk'], 'read')
        self.assertFalse(proposal['requires_confirmation'])

    def test_model_answer_must_name_a_catalog_action(self):
        forged = '{"action": "format.disk", "params": {}}'
        with self.assertRaisesRegex(ValueError, 'not available'):
            pilot.propose_from_model('```json\n' + forged + '\n```', self.actions)

    def test_model_answer_parameters_are_revalidated(self):
        forged = '{"action": "install.flatpak", "params": {"ref": "x; rm -rf /"}}'
        with self.assertRaisesRegex(ValueError, 'allowed format'):
            pilot.propose_from_model('```json\n' + forged + '\n```', self.actions)
        forged = '{"action": "install.flatpak", "params": {"ref": "org.example.Tool", "sudo": "yes"}}'
        with self.assertRaisesRegex(ValueError, 'Unexpected parameter'):
            pilot.propose_from_model('```json\n' + forged + '\n```', self.actions)

    def test_valid_model_answer_becomes_a_pending_proposal(self):
        answer = 'I can do that.\n```json\n{"action":"install.flatpak","params":{"ref":"org.example.Tool"}}\n```'
        proposal = pilot.propose_from_model(answer, self.actions)
        self.assertEqual(proposal['action'], 'install.flatpak')
        self.assertIn(proposal['id'], pilot.load_pending())

    def test_plain_text_answer_is_not_executable(self):
        with self.assertRaisesRegex(ValueError, 'did not propose'):
            pilot.propose_from_model('Run sudo rm -rf / and everything will be fine.', self.actions)


class RunTests(Temp):
    def runner(self, exit_code=0):
        calls = []

        def run(command, **options):
            calls.append((command, options))
            return SimpleNamespace(returncode=exit_code, stdout='done\n', stderr='')
        return calls, run

    def proposal(self, text='check for updates'):
        return pilot.propose(text, self.actions)[0]

    def test_run_requires_a_pending_proposal(self):
        with self.assertRaisesRegex(ValueError, 'unknown'):
            pilot.run('deadbeefdeadbeef', actions=self.actions)

    def test_run_is_single_use(self):
        calls, runner = self.runner()
        proposal = self.proposal()
        pilot.run(proposal['id'], actions=self.actions, runner=runner)
        with self.assertRaisesRegex(ValueError, 'unknown'):
            pilot.run(proposal['id'], actions=self.actions, runner=runner)
        self.assertEqual(len(calls), 1)

    def test_run_expires(self):
        proposal = self.proposal()
        store = pilot.load_pending()
        store[proposal['id']]['expires'] = int(time.time()) - 1
        pilot.save_pending(store)
        with self.assertRaisesRegex(ValueError, 'expired'):
            pilot.run(proposal['id'], actions=self.actions, runner=self.runner()[1])

    def test_high_risk_needs_yes(self):
        calls, runner = self.runner()
        proposal = pilot.propose('turn off ai', self.actions)[0]
        with self.assertRaisesRegex(ValueError, 'high risk'):
            pilot.run(proposal['id'], actions=self.actions, runner=runner)
        pilot.run(proposal['id'], yes=True, actions=self.actions, runner=runner)
        self.assertEqual(calls[0][0], ['pkexec', pilot.HELPER, 'ai.disable'])

    def test_disabled_pilot_refuses_everything(self):
        proposal = self.proposal()
        pilot.set_enabled(False)
        with self.assertRaisesRegex(ValueError, 'disabled'):
            pilot.run(proposal['id'], actions=self.actions, runner=self.runner()[1])
        pilot.set_enabled(True)

    def test_execution_never_uses_a_shell(self):
        calls, runner = self.runner()
        proposal = pilot.propose('install app org.example.Tool', self.actions)[0]
        receipt = pilot.run(proposal['id'], actions=self.actions, runner=runner)
        command, options = calls[0]
        self.assertIsInstance(command, list)
        self.assertFalse(options.get('shell', False))
        self.assertEqual(receipt['status'], 'completed')

    def test_failure_is_reported_not_hidden(self):
        calls, runner = self.runner(exit_code=3)
        proposal = self.proposal()
        receipt = pilot.run(proposal['id'], actions=self.actions, runner=runner)
        self.assertEqual(receipt['status'], 'failed')
        self.assertEqual(receipt['exit'], 3)

    def test_audit_stays_private_and_records_the_action(self):
        proposal = self.proposal()
        pilot.run(proposal['id'], actions=self.actions, runner=self.runner()[1])
        entries = pilot.audit()
        self.assertEqual(entries[-1]['action'], 'updates.check')
        self.assertEqual(entries[-1]['status'], 'completed')
        self.assertEqual((pilot.audit_path()).stat().st_mode & 0o777, 0o600)


class AdminHelperTests(Temp):
    uuid = '11111111-2222-3333-4444-555555555555'

    def test_builds_argv_itself_for_admin_actions(self):
        self.assertEqual(admin.resolve('network.trust-home', [self.uuid], HERE / 'actions.json'),
                         ['/usr/libexec/aether-system-admin', 'network-home', self.uuid])

    def test_refuses_user_privilege_actions(self):
        with self.assertRaisesRegex(ValueError, 'not an administrator action'):
            admin.resolve('security.status', [], HERE / 'actions.json')

    def test_refuses_unknown_id_and_wrong_parameter_count(self):
        with self.assertRaisesRegex(ValueError, 'not an administrator action'):
            admin.resolve('root.shell', [], HERE / 'actions.json')
        with self.assertRaisesRegex(ValueError, 'exactly'):
            admin.resolve('network.trust-home', [], HERE / 'actions.json')

    def test_refuses_invalid_parameter_value(self):
        with self.assertRaisesRegex(ValueError, 'Invalid value'):
            admin.resolve('network.trust-home', ['../../etc/shadow'], HERE / 'actions.json')

    def test_refuses_world_writable_catalog(self):
        path = Path(self.temp.name) / 'actions.json'
        path.write_text(json.dumps(catalog()))
        path.chmod(0o666)
        with patch.object(admin.os, 'geteuid', return_value=0):
            with self.assertRaises(PermissionError):
                admin.checked(path)


if __name__ == '__main__':
    sys.exit(unittest.main())
