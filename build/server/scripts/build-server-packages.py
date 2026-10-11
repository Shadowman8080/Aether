#!/usr/bin/env python3
"""Source-build plan for Aether Server roles.

The role catalog (src/server/roles/catalog.json) declares which packages each
server role needs. This script turns that declaration into the corresponding
build() calls from the desktop foundation recipe, so a role becomes
"available" when its software is compiled into the image.

STATUS. This is scaffolding, not a finished build. None of these recipes has
been compiled, and no source pins exist for them yet. Running --build for the
first time is a bring-up: each package needs its pinned upstream source in
configs/direct-sources.json, and the options below must be treated as a first
attempt verified against the per-package build log, exactly like the desktop's
--domain chain was treated. Do not claim an available role without a built,
booted check of its service.

The one thing that is already exercised is the mapping itself: `--list` reads
the catalog and prints exactly what each role would be built from.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CATALOG = REPO / 'src/server/roles/catalog.json'

# Build recipe per role: list of (package, build type, configure options).
# Choose the smallest viable build for each software, mirroring the desktop
# recipe's taste for `--without-*` trimming.
PLAN = {
    'ssh': [('openssh', 'autoconf', ['--without-pam']), ],
    'dhcp': [('kea', 'cmake', []), ],
    'dns': [('bind', 'autoconf', []), ],
    'ntp': [('chrony', 'autoconf', []), ],
    'aaa': [('freeradius', 'cmake', []), ('tacacs', 'autoconf', []), ],
    'reverse-proxy': [('haproxy', 'autoconf2', []), ],
    'vpn': [('wireguard-tools', 'autoconf', []), ],
    'directory': [('openldap', 'autoconf', []), ],
    'ca': [('step-ca', 'gomod', []), ],
    'ad-dc': [('samba', 'autoconf',
               ['--without-ad-dc'] if False else ['--with-ads', '--with-shared-modules=idmap_ad']), ],
    'syslog': [('rsyslog', 'autoconf',
                ['--disable-generator', '--enable-imtcp', '--enable-imudp']), ],
    'monitoring': [('prometheus', 'gomod', []), ('grafana', 'gomod', []),
                   ('node_exporter', 'gomod', []), ],
    'file': [('samba', 'autoconf', ['--without-async-dns']), ],
    'database': [('postgresql', 'autoconf2', []), ],
    'ftp': [('vsftpd', 'make', []), ],
    'backup': [('restic', 'gomod', []), ],
    'web': [('nginx', 'autoconf', []), ],
    'appserver': [('php', 'autoconf', ['--enable-fpm']), ],
    'mail': [('postfix', 'make', []), ('dovecot', 'autoconf', []), ],
    'proxy': [('squid', 'autoconf', []), ],
    'git': [('gitea', 'gomod', []), ],
    'hypervisor': [('libvirt', 'meson', []), ('qemu', 'meson', []), ],
    'container': [('podman', 'golang', []), ],
    'print': [('cups', 'autoconf', []), ],
    'voip': [('asterisk', 'autoconf', []), ],
    'media': [('jellyfin', 'dotnet', []), ],
    'ci': [('gitlab-runner', 'gomod', []), ],
}

# Roles whose software must be present to say "applied": pull the first
# named binary path from the catalog for a post-build presence check.
def expected_binaries(role_id: dict) -> list[str]:
    return role_id.get('binaries', [])[:1]


def build_plan(catalog: dict) -> dict[str, list[tuple[str, str, list[str]]]]:
    chosen = {}
    for role in catalog['roles']:
        choices = PLAN.get(role['id'])
        if not choices:
            continue  # role exists but has no recipe yet; unavailable
        chosen[role['id']] = choices
    return chosen


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--list', action='store_true',
                        help='print the role-to-recipe mapping from the catalog')
    parser.add_argument('--build', action='store_true',
                        help='run the recipes under /recipes (bring-up; see the module note)')
    parser.add_argument('--only', help='build a single role id')
    args = parser.parse_args()

    catalog = json.loads(CATALOG.read_text())
    plan = build_plan(catalog)
    if args.list:
        for role in catalog['roles']:
            recipes = plan.get(role['id'], [])
            marker = 'built' if recipes else 'NO RECIPE'
            print(f"{role['id']:<14} {marker:<9} "
                  + (', '.join(r[0] for r in recipes) if recipes else 'available only as config'))
        return 0

    if not args.build:
        print('Nothing built. Pass --list to inspect the plan or --build to run it. '
              'First run is a bring-up; see the STATUS note in this file.')
        return 0

    # Importing the desktop foundation recipe is what makes build() available.
    ns = {}
    foundation = Path('/recipes/scripts/build-desktop-foundation.py')
    if not foundation.exists():
        print('No /recipes/scripts/build-desktop-foundation.py on this host; '
              'cannot build. Nothing was built.', file=sys.stderr)
        return 1
    exec(compile(foundation.read_text(), foundation, 'exec'), ns)
    build = ns['build']

    targets = [args.only] if args.only else list(plan)
    for role_id in targets:
        recipes = plan.get(role_id)
        if not recipes:
            print(f'{role_id}: no recipe; skipping')
            continue
        role = next((r for r in catalog['roles'] if r['id'] == role_id), {})
        for name, kind, options in recipes:
            print(f'>>> {role_id}: {name}')
            build(name, kind, options)
        for binary in expected_binaries(role):
            if not Path(binary).exists():
                print(f'!!! {role_id}: expected {binary} but it was not produced', file=sys.stderr)
                return 1
        print(f'{role_id}: built')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())