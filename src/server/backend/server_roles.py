#!/usr/bin/env python3
"""Apply Aether Server installation roles and directory-join configuration.

This module is deliberately free of command-line handling so that it can be
imported by the privileged installer backend and exercised by unit tests
against a throwaway root.

The role catalog (catalog.json) is data, not code: the graphical installer and
this module read the same file. A role whose software is not built into the
image is reported as "unavailable" rather than being allowed to fail the whole
installation, which matches Aether's habit of stating what is not done.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

DEFAULT_CATALOG = Path('/usr/share/aether/server/roles.json')
CATEGORY_ORDER = (
    'network', 'identity', 'logging', 'storage', 'web', 'compute', 'productivity',
)


class CatalogError(ValueError):
    """The role catalog is missing or malformed."""


def catalog_path() -> Path:
    override = os.environ.get('AETHER_SERVER_CATALOG')
    return Path(override) if override else DEFAULT_CATALOG


def load_catalog(path: Path | str | None = None) -> dict:
    path = Path(path) if path else catalog_path()
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError as error:
        raise CatalogError(f'Server role catalog not found: {path}') from error
    except json.JSONDecodeError as error:
        raise CatalogError(f'Server role catalog is not valid JSON: {path}: {error}') from error
    validate_catalog(data)
    return data


def template_root(catalog: dict, catalog_file: Path | str | None = None) -> Path:
    """Directory the per-role config ``source`` paths are relative to."""
    root = catalog.get('config_root', 'configs')
    base = Path(catalog_file).parent if catalog_file else catalog_path().parent
    return base / root


def validate_catalog(catalog: dict) -> None:
    """Raise CatalogError unless the catalog is internally consistent.

    This runs on every load so a bad catalog fails loudly at install start
    rather than halfway through writing configuration.
    """
    if not isinstance(catalog, dict):
        raise CatalogError('Catalog must be a JSON object.')
    if catalog.get('schema') != 1:
        raise CatalogError('Unsupported catalog schema.')
    if not isinstance(catalog.get('config_root'), str) or not catalog['config_root']:
        raise CatalogError('Catalog must set a non-empty config_root.')

    categories = catalog.get('categories')
    roles = catalog.get('roles')
    if not isinstance(categories, list) or not categories:
        raise CatalogError('Catalog must define at least one category.')
    if not isinstance(roles, list) or not roles:
        raise CatalogError('Catalog must define at least one role.')

    category_ids = set()
    for category in categories:
        for field in ('id', 'name', 'summary'):
            if not isinstance(category.get(field), str) or not category[field]:
                raise CatalogError(f'Category entry missing {field!r}.')
        if category['id'] in category_ids:
            raise CatalogError(f"Duplicate category id {category['id']!r}.")
        category_ids.add(category['id'])

    seen = set()
    for role in roles:
        if not isinstance(role, dict):
            raise CatalogError('Each role must be a JSON object.')
        for field in ('id', 'name', 'category', 'summary'):
            if not isinstance(role.get(field), str) or not role[field]:
                raise CatalogError(f'Role entry missing {field!r}.')
        if role['id'] in seen:
            raise CatalogError(f"Duplicate role id {role['id']!r}.")
        seen.add(role['id'])
        if role['category'] not in category_ids:
            raise CatalogError(f"Role {role['id']!r} uses unknown category {role['category']!r}.")
        for field in ('packages', 'binaries', 'services', 'configs', 'firewall'):
            value = role.get(field, [])
            if not isinstance(value, list):
                raise CatalogError(f"Role {role['id']!r}: {field!r} must be a list.")
        for config in role.get('configs', []):
            if not isinstance(config, dict):
                raise CatalogError(f"Role {role['id']!r}: each config must be an object.")
            source = config.get('source')
            destination = config.get('destination')
            if not isinstance(source, str) or not source or source.startswith('/'):
                raise CatalogError(f"Role {role['id']!r}: config source must be a relative path.")
            if not isinstance(destination, str) or not destination.startswith('/'):
                raise CatalogError(f"Role {role['id']!r}: config destination must be absolute.")
            mode = config.get('mode', '0644')
            if not (isinstance(mode, str) and len(mode) == 4 and all(c in '01234567' for c in mode)):
                raise CatalogError(f"Role {role['id']!r}: config mode must be four octal digits.")
        for binary in role.get('binaries', []):
            if not isinstance(binary, str) or not binary.startswith('/'):
                raise CatalogError(f"Role {role['id']!r}: binary paths must be absolute.")
        for spec in role.get('firewall', []):
            _parse_firewall_spec(role['id'], spec)


def _parse_firewall_spec(role_id: str, spec: str) -> tuple[str, int]:
    if not isinstance(spec, str) or spec.count('/') != 1:
        raise CatalogError(f"Role {role_id!r}: firewall entry {spec!r} must look like tcp/443.")
    protocol, _, port = spec.partition('/')
    if protocol not in ('tcp', 'udp') or not port.isdigit() or not 1 <= int(port) <= 65535:
        raise CatalogError(f"Role {role_id!r}: invalid firewall entry {spec!r}.")
    return protocol, int(port)


def role_by_id(catalog: dict, role_id: str) -> dict | None:
    for role in catalog['roles']:
        if role['id'] == role_id:
            return role
    return None


def category_name(catalog: dict, category_id: str) -> str:
    for category in catalog['categories']:
        if category['id'] == category_id:
            return category['name']
    return category_id


def ordered_roles(catalog: dict) -> list[dict]:
    """Roles grouped in a stable, category-first order for the UI."""
    order = {cid: i for i, cid in enumerate(CATEGORY_ORDER)}
    return sorted(
        catalog['roles'],
        key=lambda r: (order.get(r['category'], len(CATEGORY_ORDER)), r['name'].lower()),
    )


def default_selection(catalog: dict) -> list[str]:
    return [role['id'] for role in catalog['roles'] if role.get('default')]


def normalize_selection(catalog: dict, selected) -> list[str]:
    """Keep only known ids, in catalog order, without duplicates."""
    wanted = set(selected)
    return [role['id'] for role in catalog['roles'] if role['id'] in wanted]


# --- availability ----------------------------------------------------------

def installed_packages(root: Path | str) -> set[str]:
    """Package names marked installed in the target dpkg database."""
    status = Path(root) / 'var/lib/dpkg/status'
    installed: set[str] = set()
    if not status.is_file():
        return installed
    block: dict[str, str] = {}

    def flush():
        if block.get('Package') and block.get('Status', '').startswith('install ok installed'):
            installed.add(block['Package'])

    for line in status.read_text(encoding='utf-8', errors='replace').splitlines():
        if not line.strip():
            flush()
            block = {}
        elif ': ' in line:
            key, value = line.split(': ', 1)
            block[key] = value
    flush()
    return installed


def binary_present(root: Path | str, binary: str) -> bool:
    relative = binary.lstrip('/')
    candidate = Path(root) / relative
    return candidate.is_file() and os.access(candidate, os.X_OK)


def missing_requirements(role: dict, root: Path | str) -> list[str]:
    """Human-readable list of the packages/binaries that are absent."""
    missing: list[str] = []
    installed = None
    for package in role.get('packages', []):
        if installed is None:
            installed = installed_packages(root)
        if package not in installed:
            missing.append(f'package {package}')
    for binary in role.get('binaries', []):
        if not binary_present(root, binary):
            missing.append(f'binary {binary}')
    return missing


def role_available(role: dict, root: Path | str) -> bool:
    """A role with no package/binary requirement is configuration-only."""
    if not role.get('packages') and not role.get('binaries'):
        return True
    installed = installed_packages(root)
    if any(package in installed for package in role.get('packages', [])):
        return True
    return any(binary_present(root, binary) for binary in role.get('binaries', []))


# --- application -----------------------------------------------------------

def _copy_config(role: dict, config: dict, root: Path, template_dir: Path) -> tuple[bool, str]:
    source = template_dir / config['source']
    if not source.is_file():
        return False, f"template missing: {config['source']}"
    destination = root / config['destination'].lstrip('/')
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    try:
        os.chmod(destination, int(config.get('mode', '0644'), 8))
    except OSError:
        # A filesystem that cannot carry the mode is reported by the tests, not
        # treated as an installation failure.
        pass
    return True, str(config['destination'])


def _enable_service(root: Path, service: str) -> tuple[bool, str]:
    """Enable a unit in the target root by creating its wants symlink.

    The symlink is written *relative* to the unit so it resolves inside the
    image root. Calling ``systemctl --root`` from here would either fail in an
    offline chroot or leave a host-absolute link that does not resolve within
    the image, so the enable is performed directly instead.
    """
    unit = None
    for location in ('usr/lib/systemd/system', 'lib/systemd/system', 'etc/systemd/system'):
        candidate = root / location / service
        if candidate.exists():
            unit = candidate
            break
    if unit is None:
        return False, 'unit not installed'
    wants = root / 'etc/systemd/system/multi-user.target.wants'
    wants.mkdir(parents=True, exist_ok=True)
    link = wants / service
    target = os.path.relpath(unit, wants)
    try:
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(target)
    except OSError as error:
        return False, f'symlink failed: {error}'
    return True, 'wants symlink'


def _merge_firewall(root: Path, ports: list[tuple[str, int]]) -> None:
    """Open ports in the target's Aether firewall configuration."""
    path = root / 'etc/aether-security/firewall.json'
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            data = {}
    else:
        data = {}
    tcp = set(int(p) for p in data.get('tcp', []) if isinstance(p, int))
    udp = set(int(p) for p in data.get('udp', []) if isinstance(p, int))
    for protocol, port in ports:
        (tcp if protocol == 'tcp' else udp).add(port)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({'tcp': sorted(tcp), 'udp': sorted(udp)}, indent=2) + '\n',
        encoding='utf-8',
    )
    try:
        os.chmod(path, 0o644)
    except OSError:
        pass


def apply_role(
    role: dict,
    root: Path | str,
    template_dir: Path | str,
    *,
    enable_services: bool = True,
    open_firewall: bool = True,
    logger=print,
) -> dict:
    """Apply one role. Never raises for a missing dependency; reports instead."""
    root = Path(root)
    template_dir = Path(template_dir)
    report = {
        'id': role['id'],
        'name': role['name'],
        'configs': [],
        'services': [],
        'firewall': [],
        'problems': [],
    }
    if not role_available(role, root):
        report['status'] = 'unavailable'
        report['detail'] = 'not built into this image (' + ', '.join(missing_requirements(role, root)) + ')'
        logger(f"  {role['name']}: {report['detail']}")
        return report

    for config in role.get('configs', []):
        ok, detail = _copy_config(role, config, root, template_dir)
        if ok:
            report['configs'].append(detail)
        else:
            report['problems'].append(detail)

    if enable_services:
        for service in role.get('services', []):
            ok, how = _enable_service(root, service)
            if ok:
                report['services'].append(service)
            else:
                report['problems'].append(f'service {service}: {how}')

    if open_firewall and role.get('firewall'):
        ports = [_parse_firewall_spec(role['id'], spec) for spec in role['firewall']]
        _merge_firewall(root, ports)
        report['firewall'] = list(role['firewall'])

    report['status'] = 'applied' if not report['problems'] else 'partial'
    logger(
        f"  {role['name']}: {report['status']} "
        f"({len(report['configs'])} config, {len(report['services'])} service, "
        f"{len(report['firewall'])} port)"
    )
    return report


def apply_roles(
    catalog: dict,
    selected,
    root: Path | str,
    template_dir: Path | str | None = None,
    *,
    enable_services: bool = True,
    open_firewall: bool = True,
    logger=print,
) -> dict:
    """Apply every selected role and write an audit report into the target."""
    root = Path(root)
    if template_dir is None:
        template_dir = template_root(catalog)
    template_dir = Path(template_dir)
    reports = []
    for role_id in normalize_selection(catalog, selected):
        reports.append(apply_role(
            role_by_id(catalog, role_id), root, template_dir,
            enable_services=enable_services, open_firewall=open_firewall, logger=logger,
        ))
    summary_path = root / 'etc/aether/server-roles.json'
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps({'catalog_version': catalog.get('catalog_version', ''),
                    'roles': reports}, indent=2) + '\n',
        encoding='utf-8',
    )
    applied = [r['id'] for r in reports if r['status'] == 'applied']
    unavailable = [r['id'] for r in reports if r['status'] == 'unavailable']
    partial = [r['id'] for r in reports if r['status'] == 'partial']
    return {
        'reports': reports,
        'applied': applied,
        'unavailable': unavailable,
        'partial': partial,
    }


# --- directory (Active Directory) join ------------------------------------

def render_krb5_conf(domain: str) -> str:
    realm = domain.upper()
    lower = domain.lower()
    return (
        '[libdefaults]\n'
        '  dns_lookup_realm = false\n'
        '  dns_lookup_kdc = true\n'
        f'  default_realm = {realm}\n\n'
        '[realms]\n'
        f'  {realm} = {{\n'
        f'    default_domain = {lower}\n'
        '  }\n\n'
        '[domain_realm]\n'
        f'  .{lower} = {realm}\n'
        f'  {lower} = {realm}\n'
    )


def render_sssd_conf(domain: str) -> str:
    realm = domain.upper()
    lower = domain.lower()
    return (
        '# Managed by the Aether Server installer. Removed by aether-directory leave.\n'
        '[sssd]\n'
        'config_file_version = 2\n'
        'services = nss, pam\n'
        f'domains = {realm}\n'
        f'default_domain_suffix = {lower}\n\n'
        f'[domain/{realm}]\n'
        f'ad_domain = {lower}\n'
        'id_provider = ad\n'
        'auth_provider = ad\n'
        'access_provider = ad\n'
        'cache_credentials = true\n'
    )


def write_directory_config(root: Path | str, domain: str, join_user: str) -> list[str]:
    """Write Kerberos/sssd/PAM/nsswitch configuration into the target root.

    Returns the list of relative paths written. The actual machine-account join
    is performed separately by aether-directory because it needs adcli and a
    reachable domain controller.
    """
    root = Path(root)
    written = []

    def write(relative: str, contents: str, mode: int) -> None:
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(contents, encoding='utf-8')
        try:
            os.chmod(destination, mode)
        except OSError:
            pass
        written.append('/' + relative)

    write('etc/krb5.conf', render_krb5_conf(domain), 0o644)
    write('etc/sssd/sssd.conf', render_sssd_conf(domain), 0o600)

    nsswitch = root / 'etc/nsswitch.conf'
    if nsswitch.is_file():
        lines = []
        for line in nsswitch.read_text(encoding='utf-8').splitlines():
            key = line.split(':', 1)[0].strip()
            if key in ('passwd', 'group', 'shadow', 'hosts') and 'sss' not in line.split(':', 1)[1]:
                name, _, rest = line.partition(':')
                tokens = rest.split()
                insert = 1 if tokens else 0
                tokens.insert(insert, 'sss')
                line = name + ':' + ' ' + ' '.join(tokens)
            lines.append(line)
        nsswitch.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        written.append('/etc/nsswitch.conf')

    # The SSH PAM stack accepts local accounts first and domain accounts when
    # joined, mirroring the desktop greeter's stack.
    write('etc/pam.d/sshd', (
        '# Aether Server: local accounts first, Active Directory when joined.\n'
        'auth       required      pam_env.so\n'
        'auth       sufficient    pam_unix.so try_first_pass nullok\n'
        'auth       sufficient    pam_sss.so ignore_unknown_user\n'
        'auth       required      pam_deny.so\n'
        'account    required      pam_access.so\n'
        'account    sufficient    pam_unix.so\n'
        'account    sufficient    pam_sss.so ignore_unknown_user\n'
        'account    required      pam_deny.so\n'
        'password   include       system-password\n'
        'session    required      pam_limits.so\n'
        'session    required      pam_mkhomedir.so skel=/etc/skel umask=0077\n'
        'session    optional      pam_sss.so\n'
    ), 0o644)

    marker = root / 'etc/aether/domain-login'
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text('# Presence marks an Active Directory capable system.\n', encoding='utf-8')
    try:
        os.chmod(marker, 0o644)
    except OSError:
        pass
    written.append('/etc/aether/domain-login')

    state_dir = root / 'etc/aether'
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / 'directory.conf').write_text(
        f'# Managed by the Aether Server installer.\nAD_DOMAIN={domain.upper()}\n'
        f'AD_JOIN_USER={join_user}\nAD_JOINED=0\n',
        encoding='utf-8',
    )
    written.append('/etc/aether/directory.conf')
    return written
