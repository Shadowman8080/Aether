#!/usr/bin/env python3
"""Configure only the mounted Aether disk image; never the build host."""
from pathlib import Path
import os, secrets, string, subprocess

root = Path('/opt/aether/system')
image = Path('/opt/aether/build/aether-system.raw')
source = subprocess.check_output(['findmnt', '-n', '-o', 'SOURCE', '--mountpoint', str(root)], text=True).strip()
assert source.startswith('/dev/loop') and source.endswith('p3'), source
loop = source[:-2]
backing = subprocess.check_output(['losetup', '-n', '-O', 'BACK-FILE', loop], text=True).strip()
assert Path(backing).resolve() == image.resolve(), backing
os.chown(root, 0, 0)

def write(name, text, mode=0o644):
    p = root / name.lstrip('/')
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    p.chmod(mode)

def target(*args, **kw):
    return subprocess.run(['chroot', str(root), *args], check=True, **kw)

write('/etc/os-release', '''NAME="Aether Linux"
PRETTY_NAME="Aether Linux 0.2 development"
ID=aether
VERSION_ID=0.2
VERSION="0.2 development"
RELEASE_TYPE=development
''')
write('/etc/issue', 'Aether Linux 0.2 development \\n \\l\n\n')
write('/etc/hostname', 'aether\n')
write('/etc/hosts', '127.0.0.1 localhost\n::1 localhost\n127.0.1.1 aether\n')
write('/etc/locale.conf', 'LANG=en_US.UTF-8\n')
write('/etc/vconsole.conf', 'KEYMAP=us\n')
profile = root / 'etc/profile'
if '# Aether shell defaults' not in profile.read_text():
    with profile.open('a') as f:
        f.write("\n# Aether shell defaults\nexport PATH=/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin\numask 022\nif [[ $- == *i* ]]; then\n  PS1='\\u@\\h:\\w\\$ '\nfi\n")
write('/etc/fstab', 'LABEL=AETHER_ROOT / ext4 defaults 1 1\nLABEL=AETHER_EFI /boot/efi vfat defaults,umask=0077 0 2\n/swapfile none swap sw 0 0\n')
for p in (root / 'etc/systemd/network').glob('*.network'):
    p.unlink()
write('/etc/systemd/network/20-wired.network', '''[Match]
Name=en* eth*
Type=ether

[Network]
DHCP=yes
IPv6AcceptRA=yes
LLMNR=no
MulticastDNS=no

[DHCPv4]
UseDNS=yes
UseNTP=yes
RouteMetric=100
''')
resolv = root / 'etc/resolv.conf'
resolv.unlink(missing_ok=True)
resolv.symlink_to('/run/systemd/resolve/stub-resolv.conf')
write('/etc/systemd/system/systemd-networkd-wait-online.service.d/timeout.conf', '[Service]\nExecStart=\nExecStart=/usr/lib/systemd/systemd-networkd-wait-online --any --timeout=20\n')
write('/etc/systemd/journald.conf.d/aether.conf', '[Journal]\nStorage=persistent\nSystemMaxUse=128M\nRuntimeMaxUse=32M\n')
write('/etc/systemd/coredump.conf.d/aether.conf', '[Coredump]\nStorage=none\nProcessSizeMax=0\n')
write('/etc/systemd/system-preset/00-aether.preset', 'enable systemd-networkd.service\nenable systemd-resolved.service\nenable systemd-timesyncd.service\nenable fstrim.timer\n')
write('/etc/motd', '''Welcome to Aether Linux 0.2 (persistent console development build).

Use sudo for administrative commands. Your home and system settings persist.
Run aether-system-status for a health summary.
This image does not yet include a graphical desktop, AI, or an installer.
''')
write('/usr/bin/aether-system-status', '''#!/bin/bash
printf 'Aether Linux system status\\n'
uname -r
findmnt --mountpoint /
findmnt --mountpoint /boot/efi
df -h / /home
free -h
ip -br address
systemctl --no-pager --failed
systemctl is-active systemd-networkd systemd-resolved systemd-timesyncd
''', 0o755)
new_user = not any(line.startswith('aether:') for line in (root / 'etc/passwd').read_text().splitlines())
if new_user:
    target('/usr/sbin/useradd', '-m', '-U', '-G', 'wheel,audio,video,input', '-s', '/bin/bash', 'aether')
(root / 'home/aether').chmod(0o700)
credentials = Path('/opt/aether/build/persistent-credentials.txt')
new_credentials = not credentials.exists()
if new_credentials:
    alphabet = string.ascii_letters + string.digits
    password = 'Ae7!' + ''.join(secrets.choice(alphabet) for _ in range(20))
    fd = os.open(credentials, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f:
        f.write('Username: aether\nTemporary password: ' + password + '\n\nChange this password when prompted at first login.\nRoot login is locked; use sudo with your own password.\nThese credentials apply only to this persistent 0.2 disk image.\n')
if new_user or new_credentials:
    password = next(line.removeprefix('Temporary password: ') for line in credentials.read_text().splitlines() if line.startswith('Temporary password: '))
    target('/usr/sbin/chpasswd', input='aether:' + password + '\n', text=True)
    target('/usr/bin/chage', '-d', '0', 'aether')
target('/usr/sbin/usermod', '-L', 'root')
write('/etc/sudoers.d/aether-admin', '%wheel ALL=(ALL:ALL) ALL\n', 0o440)
(root / 'etc/sudoers.d/00-sudo').unlink(missing_ok=True)
# Sudo was built with shadow-password authentication, not PAM.
(root / 'etc/pam.d/sudo').unlink(missing_ok=True)
target('/usr/sbin/visudo', '-c')
for name in ('systemd-networkd.service', 'systemd-resolved.service', 'systemd-timesyncd.service', 'fstrim.timer', 'getty@tty1.service', 'serial-getty@ttyS0.service'):
    subprocess.run(['systemctl', '--root', str(root), 'enable', name], check=True)
subprocess.run(['systemctl', '--root', str(root), 'disable', 'systemd-networkd-wait-online.service'], check=True)
subprocess.run(['systemctl', '--root', str(root), 'set-default', 'multi-user.target'], check=True)
swap = root / 'swapfile'
if not swap.exists():
    subprocess.run(['fallocate', '-l', '2G', str(swap)], check=True)
    swap.chmod(0o600)
    subprocess.run(['mkswap', str(swap)], check=True)
# Per-install identity and randomness are initialized on first real boot.
write('/etc/machine-id', '')
for name in ('var/lib/systemd/random-seed', 'var/lib/dbus/machine-id'):
    (root / name).unlink(missing_ok=True)
print('Configured Aether persistent base; credentials stored privately under build/.')
