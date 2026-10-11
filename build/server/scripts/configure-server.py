#!/usr/bin/env python3
"""Finish the offline Aether Server image before it is squashed.

Runs inside a chroot of the server rootfs (or with --root pointing at it) and
records the server edition facts that belong to the image rather than to a
single installation: version markers, service accounts for instruments that
ship in the base, and the first-boot preparation service.
"""
from pathlib import Path
import argparse
import shutil
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--root', default='/')
parser.add_argument('--version', default='0.1')
args = parser.parse_args()
root = Path(args.root)

release = root / 'etc/os-release'
if release.is_file():
    text = release.read_text()
    if 'ID=aether' not in text or 'ID="aether"' not in text:
        raise SystemExit('Refusing to configure a non-Aether system')

def write(relative, contents, mode=0o644):
    destination = root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(contents)
    try:
        destination.chmod(mode)
    except OSError:
        pass

# Version marker read by the server edition's own tools.
write('etc/aether/server-version', 'AETHER_SERVER=' + args.version + '\n')

# The installed system boots to the console (multi-user) target. The live ISO
# also uses this target; the graphical installer is launched on demand.
target = root / 'etc/systemd/system/default.target'
target.parent.mkdir(parents=True, exist_ok=True)
if target.is_symlink() or target.exists():
    target.unlink()
target.symlink_to('/usr/lib/systemd/system/multi-user.target')

# First-boot secret preparation must run on every installed system. Enabling
# from a chroot is safe: systemctl --root only creates the wants symlink.
systemctl = shutil.which('systemctl')
unit = root / 'usr/lib/systemd/system/aether-server-firstboot.service'
if not unit.exists():
    raise SystemExit('aether-server-firstboot.service was not installed')
if systemctl:
    result = subprocess.run([systemctl, '--root=' + str(root), 'enable',
                             'aether-server-firstboot.service'], capture_output=True, text=True)
    if result.returncode != 0:
        # Fall back to a symlink when systemctl refuses an offline root.
        wants = root / 'etc/systemd/system/multi-user.target.wants'
        wants.mkdir(parents=True, exist_ok=True)
        (wants / 'aether-server-firstboot.service').unlink(missing_ok=True)
        (wants / 'aether-server-firstboot.service').symlink_to(
            '/usr/lib/systemd/system/aether-server-firstboot.service')
else:
    wants = root / 'etc/systemd/system/multi-user.target.wants'
    wants.mkdir(parents=True, exist_ok=True)
    (wants / 'aether-server-firstboot.service').symlink_to(
        '/usr/lib/systemd/system/aether-server-firstboot.service')

# Directories the shipped role templates assume exist.
for directory in ('/srv/www', '/srv/aether', '/srv/restic', '/var/log/remote',
                  '/etc/aether', '/etc/aether-security'):
    (root / directory.lstrip('/')).mkdir(parents=True, exist_ok=True)

# The default firewall config belongs in the image; roles add the ports they
# need at installation time.
firewall = root / 'etc/aether-security/firewall.json'
if not firewall.exists():
    write('etc/aether-security/firewall.json', '{\n  "tcp": [],\n  "udp": []\n}\n')

print('Aether Server image configured for version ' + args.version + '.')