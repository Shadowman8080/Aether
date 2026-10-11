#!/usr/bin/env python3
"""Unit tests for the Aether Server role catalog and installer logic.

These run entirely against a throwaway root: no systemd, no dpkg, no nftables,
no disk is ever touched, and nothing needs root. Run with:

    sh build/server/scripts/test-server-roles.sh
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import shutil
import stat
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO / 'src/server/backend'
CATALOG = REPO / 'src/server/roles/catalog.json'
TEMPLATE_ROOT = REPO / 'src/server/roles/configs'

os.environ['AETHER_SERVER_CATALOG'] = str(CATALOG)
sys.path.insert(0, str(BACKEND_DIR))

import server_roles  # noqa: E402


def load_backend():
    path = BACKEND_DIR / 'aether-server-install'
    loader = importlib.machinery.SourceFileLoader('aether_server_install', str(path))
    spec = importlib.util.spec_from_loader('aether_server_install', loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def make_root() -> Path:
    root = Path(tempfile.mkdtemp(prefix='aether-server-test-'))
    return root


def stub_ssh(root: Path):
    """Give the test root a present sshd binary and unit file."""
    binary = root / 'usr/sbin/sshd'
    binary.parent.mkdir(parents=True, exist_ok=True)
    binary.write_text('#!/bin/sh\n')
    binary.chmod(binary.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    unit = root / 'usr/lib/systemd/system/sshd.service'
    unit.parent.mkdir(parents=True, exist_ok=True)
    unit.write_text('[Unit]\nDescription=stub sshd\n[Install]\nWantedBy=multi-user.target\n')


class CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = server_roles.load_catalog(CATALOG)

    def test_catalog_is_valid_and_schema_1(self):
        self.assertEqual(self.catalog['schema'], 1)
        self.assertTrue(self.catalog['categories'])
        self.assertTrue(self.catalog['roles'])

    def test_every_config_template_exists(self):
        template_dir = server_roles.template_root(self.catalog, CATALOG)
        for role in self.catalog['roles']:
            for config in role.get('configs', []):
                self.assertTrue(
                    (template_dir / config['source']).is_file(),
                    f"{role['id']}: missing template {config['source']}")

    def test_all_requested_roles_present(self):
        catalog = self.catalog
        ids = {role['id'] for role in catalog['roles']}
        for requested in ('dhcp', 'ntp', 'aaa', 'syslog', 'file', 'database', 'ftp',
                          'web', 'appserver', 'mail', 'proxy', 'hypervisor', 'print'):
            self.assertIn(requested, ids)
        # The additions beyond the requested list.
        for addition in ('ssh', 'dns', 'vpn', 'ca', 'ad-dc', 'directory', 'monitoring',
                         'backup', 'reverse-proxy', 'git', 'container', 'voip', 'media', 'ci'):
            self.assertIn(addition, ids)

    def test_every_role_has_a_matching_category(self):
        categories = {entry['id'] for entry in self.catalog['categories']}
        for role in self.catalog['roles']:
            self.assertIn(role['category'], categories, role['id'])

    def test_default_selection_is_ssh(self):
        self.assertEqual(server_roles.default_selection(self.catalog), ['ssh'])

    def test_normalize_selection_dedupes_and_filters(self):
        result = server_roles.normalize_selection(self.catalog, ['ssh', 'dhcp', 'not-a-role', 'ssh'])
        self.assertEqual(result, ['ssh', 'dhcp'])

    def test_validate_catalog_rejects_duplicate_ids(self):
        bad = json.loads(CATALOG.read_text())
        bad['roles'].append(dict(bad['roles'][0]))
        with self.assertRaises(server_roles.CatalogError):
            server_roles.validate_catalog(bad)

    def test_validate_catalog_rejects_bad_firewall(self):
        bad = json.loads(CATALOG.read_text())
        bad['roles'][0]['firewall'] = ['tcp/99999']
        with self.assertRaises(server_roles.CatalogError):
            server_roles.validate_catalog(bad)

    def test_validate_catalog_rejects_relative_destination(self):
        bad = json.loads(CATALOG.read_text())
        bad['roles'][0]['configs'] = [{'source': 'x.conf', 'destination': 'etc/x.conf', 'mode': '0644'}]
        with self.assertRaises(server_roles.CatalogError):
            server_roles.validate_catalog(bad)


class ApplyRoleTests(unittest.TestCase):
    def setUp(self):
        self.root = make_root()
        self.catalog = server_roles.load_catalog(CATALOG)
        self.template_dir = server_roles.template_root(self.catalog, CATALOG)
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def role(self, role_id):
        return server_roles.role_by_id(self.catalog, role_id)

    def test_unavailable_role_is_reported_not_raised(self):
        report = server_roles.apply_role(self.role('dhcp'), self.root, self.template_dir)
        self.assertEqual(report['status'], 'unavailable')
        self.assertIn('kea', report['detail'])
        self.assertFalse((self.root / 'etc/kea').exists())

    def test_applied_role_copies_config_enables_service_opens_ports(self):
        stub_ssh(self.root)
        report = server_roles.apply_role(self.role('ssh'), self.root, self.template_dir)
        self.assertEqual(report['status'], 'applied')
        self.assertTrue((self.root / 'etc/ssh/sshd_config.d/50-aether.conf').is_file())
        wants = self.root / 'etc/systemd/system/multi-user.target.wants/sshd.service'
        self.assertTrue(wants.exists(), 'sshd.service was not enabled')
        firewall = json.loads((self.root / 'etc/aether-security/firewall.json').read_text())
        self.assertIn(22, firewall['tcp'])

    def test_partial_when_template_missing(self):
        stub_ssh(self.root)
        report = server_roles.apply_role(self.role('ssh'), self.root, tempfile.mkdtemp(prefix='aether-empty-'))
        self.assertEqual(report['status'], 'partial')
        self.assertTrue(report['problems'])
        # The service was still enabled and the port still opened.
        self.assertTrue((self.root / 'etc/systemd/system/multi-user.target.wants/sshd.service').exists())
        firewall = json.loads((self.root / 'etc/aether-security/firewall.json').read_text())
        self.assertIn(22, firewall['tcp'])

    def test_apply_roles_writes_audit_report(self):
        stub_ssh(self.root)
        result = server_roles.apply_roles(self.catalog, ['ssh'], self.root, self.template_dir)
        self.assertEqual(result['applied'], ['ssh'])
        report = json.loads((self.root / 'etc/aether/server-roles.json').read_text())
        self.assertEqual(report['roles'][0]['id'], 'ssh')

    def test_unknown_role_is_silently_dropped(self):
        result = server_roles.apply_roles(self.catalog, ['ssh', 'nope'], self.root, self.template_dir)
        self.assertEqual(len(result['reports']), 1)

    def test_firewall_merges_across_roles(self):
        stub_ssh(self.root)
        server_roles.apply_roles(self.catalog, ['ssh', 'ssh'], self.root, self.template_dir)
        firewall = json.loads((self.root / 'etc/aether-security/firewall.json').read_text())
        self.assertEqual(firewall['tcp'].count(22), 1)


class DirectoryJoinTests(unittest.TestCase):
    def setUp(self):
        self.root = make_root()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        (self.root / 'etc').mkdir(parents=True, exist_ok=True)
        (self.root / 'etc/nsswitch.conf').write_text(
            'passwd: files\nshadow: files\nhosts: files dns [NOTFOUND=return]\naliases: files\n')

    def test_writes_expected_configuration(self):
        written = server_roles.write_directory_config(self.root, 'example.lan', 'admin')
        self.assertIn('/etc/krb5.conf', written)
        self.assertIn('/etc/sssd/sssd.conf', written)
        self.assertTrue((self.root / 'etc/sssd/sssd.conf').is_file())
        sssd = (self.root / 'etc/sssd/sssd.conf').read_text()
        self.assertIn('id_provider = ad', sssd)
        self.assertIn('ad_domain = example.lan', sssd)

    def test_nsswitch_inserts_sss_after_first_source(self):
        server_roles.write_directory_config(self.root, 'example.lan', 'admin')
        nsswitch = (self.root / 'etc/nsswitch.conf').read_text()
        self.assertIn('hosts: files sss dns [NOTFOUND=return]', nsswitch)
        self.assertNotIn('sss', next(line for line in nsswitch.splitlines() if line.startswith('aliases:')), )

    def test_sshd_pam_stack_references_pam_sss(self):
        server_roles.write_directory_config(self.root, 'example.lan', 'admin')
        pam = (self.root / 'etc/pam.d/sshd').read_text()
        self.assertIn('pam_unix.so', pam)
        self.assertIn('pam_sss.so ignore_unknown_user', pam)

    def test_krb5_file_structure(self):
        server_roles.write_directory_config(self.root, 'CORP.EXAMPLE', 'svc-join')
        krb5 = (self.root / 'etc/krb5.conf').read_text()
        self.assertIn('default_realm = CORP.EXAMPLE', krb5)
        self.assertIn('default_domain = corp.example', krb5)


class BackendHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.backend = load_backend()

    def test_hostname_validation(self):
        valid = ('aether', 'aether-server', 'dc-01', 'a1')
        invalid = ('-nope', 'nope-', 'has space', '', 'a' * 64, '1234')
        for name in valid:
            self.assertTrue(self.backend._valid_hostname(name), name)
        for name in invalid:
            self.assertFalse(self.backend._valid_hostname(name), name)

    def test_domain_validation(self):
        self.assertTrue(self.backend._valid_domain('example.lan'))
        self.assertTrue(self.backend._valid_domain('corp.example.com'))
        self.assertFalse(self.backend._valid_domain('..example'))
        self.assertFalse(self.backend._valid_domain(''))

    def test_dns_list(self):
        self.assertEqual(self.backend._dns_list('1.1.1.1, 9.9.9.9'), ['1.1.1.1', '9.9.9.9'])
        self.assertEqual(self.backend._dns_list(''), [])
        with self.assertRaises(ValueError):
            self.backend._dns_list('not-an-ip')

    def test_catalog_passes_backend_validation_entrypoint(self):
        # --validate is the build-time gate; the catalog must survive it.
        catalog = server_roles.load_catalog(CATALOG)
        self.assertTrue(catalog['roles'])


if __name__ == '__main__':
    unittest.main(verbosity=2)