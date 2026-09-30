#!/usr/bin/env python3
"""Install the security integration after source-built dependencies, offline."""
from pathlib import Path
import json
import os
import shutil
import subprocess

assert 'ID=aether' in Path('/etc/os-release').read_text().splitlines()
assert os.environ.get('SYSTEMD_OFFLINE') == '1'
source = Path('/security')

def write(name, data, mode=0o644):
    path = Path(name)
    assert not path.is_symlink(), name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data)
    path.chmod(mode)

Path('/usr/libexec').mkdir(exist_ok=True)
shutil.copyfile(source / 'configure-security.py', '/usr/libexec/aether-configure-security')
Path('/usr/libexec/aether-configure-security').chmod(0o755)

for name in ('aether-firewall', 'aether-security-status', 'aether-backup', 'aether-install', 'aether-mkinitramfs'):
    shutil.copyfile(source / name, '/usr/bin/' + name)
    Path('/usr/bin/' + name).chmod(0o755)
Path('/usr/lib/aether-initramfs').mkdir(parents=True, exist_ok=True)
shutil.copyfile(source / 'encrypted-init', '/usr/lib/aether-initramfs/encrypted-init')
Path('/usr/lib/aether-initramfs/encrypted-init').chmod(0o755)
Path('/etc/aether-security').mkdir(exist_ok=True)
Path('/etc/aether-security').chmod(0o700)
if not Path('/etc/aether-security/firewall.json').exists():
    write('/etc/aether-security/firewall.json', '{"tcp": [], "udp": []}\n', 0o600)
write('/usr/lib/systemd/system/aether-firewall.service', '''[Unit]
Description=Aether stateful IPv4 and IPv6 firewall
DefaultDependencies=no
After=systemd-sysctl.service local-fs.target
Before=network-pre.target shutdown.target
Wants=network-pre.target
Conflicts=shutdown.target
[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/bin/aether-firewall apply
ExecReload=/usr/bin/aether-firewall apply
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictSUIDSGID=yes
LockPersonality=yes
CapabilityBoundingSet=CAP_NET_ADMIN
RestrictAddressFamilies=AF_UNIX AF_NETLINK
RuntimeDirectory=aether-firewall
RuntimeDirectoryMode=0700
ReadWritePaths=/run/aether-firewall
[Install]
WantedBy=multi-user.target
''')
write('/etc/systemd/system/NetworkManager.service.d/60-aether-firewall.conf', '''[Unit]
Requires=aether-firewall.service
After=aether-firewall.service
''')
write('/usr/libexec/aether-apparmor-load', '''#!/bin/sh
set -eu
test -d /sys/kernel/security/apparmor
for profile in /etc/apparmor.d/aether-*; do
    [ -f "$profile" ] || continue
    /usr/sbin/apparmor_parser --replace --skip-cache "$profile"
done
''', 0o755)
write('/etc/systemd/system/apparmor.service', '''[Unit]
Description=Aether selected AppArmor enforcement profiles
DefaultDependencies=no
After=local-fs.target sys-kernel-security.mount
Before=sysinit.target
[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/libexec/aether-apparmor-load
ExecReload=/usr/libexec/aether-apparmor-load
[Install]
WantedBy=sysinit.target
''')
# No blanket claim of desktop confinement: one real daemon plus a boundary probe.
write('/etc/apparmor.d/aether-timesyncd', '''#include <tunables/global>
/usr/lib/systemd/systemd-timesyncd flags=(attach_disconnected) {
  #include <abstractions/base>
  #include <abstractions/nameservice>
  capability sys_time,
  capability setuid,
  capability setgid,
  capability chown,
  capability dac_override,
  network inet dgram,
  network inet6 dgram,
  network netlink raw,
  /usr/lib/systemd/systemd-timesyncd mr,
  /etc/systemd/timesyncd.conf r,
  /etc/systemd/timesyncd.conf.d/** r,
  /usr/lib/systemd/timesyncd.conf.d/** r,
  /run/systemd/resolve/** r,
  /run/systemd/netif/** r,
  /run/systemd/timesync/** rw,
  /run/systemd/notify w,
  /run/systemd/journal/{socket,stdout} w,
  /run/dbus/system_bus_socket rw,
  /var/lib/systemd/timesync/ rw,
  /var/lib/systemd/timesync/** rwk,
  /proc/sys/kernel/random/boot_id r,
  /proc/sys/kernel/osrelease r,
  /proc/cmdline r,
  /etc/adjtime r,
  /sys/fs/cgroup/system.slice/systemd-timesyncd.service/memory.pressure rw,
  /proc/@{pid}/stat r,
  /proc/@{pid}/status r,
  /sys/devices/system/clocksource/** r,
}
''')
write('/etc/apparmor.d/aether-boundary-probe', '''#include <tunables/global>
/usr/libexec/aether-boundary-probe {
  #include <abstractions/base>
  /usr/libexec/aether-boundary-probe mr,
  /tmp/aether-public-probe r,
  audit deny /tmp/aether-private-probe r,
}
''')
write('/etc/systemd/system/systemd-timesyncd.service.d/60-aether-apparmor.conf', '[Unit]\nRequires=apparmor.service\nAfter=apparmor.service\n')
write('/usr/lib/systemd/system/aether-backup.service', '''[Unit]
Description=Aether encrypted data backup
After=network-online.target
Wants=network-online.target
ConditionPathExists=/etc/aether-security/backup.json
[Service]
Type=oneshot
ExecStart=/usr/bin/aether-backup run
UMask=0077
Nice=10
IOSchedulingClass=best-effort
IOSchedulingPriority=7
NoNewPrivileges=yes
PrivateTmp=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
LockPersonality=yes
RestrictSUIDSGID=yes
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
MemoryMax=1G
TasksMax=128
TimeoutStartSec=6h
''')
write('/usr/lib/systemd/system/aether-backup.timer', '''[Unit]
Description=Daily Aether encrypted backup
[Timer]
OnCalendar=daily
RandomizedDelaySec=30min
Persistent=true
[Install]
WantedBy=timers.target
''')
write('/usr/lib/systemd/system/aether-backup-share.service', '''[Unit]
Description=Selected VMware encrypted-backup destination
ConditionVirtualization=vmware
After=vmtoolsd.service
Requires=vmtoolsd.service
[Service]
Type=simple
ExecStartPre=/usr/bin/install -d -m0700 /mnt/aether-shares/AetherEncryptedBackups
ExecStart=/usr/bin/vmhgfs-fuse .host:/AetherEncryptedBackups /mnt/aether-shares/AetherEncryptedBackups -f -o uid=0,gid=0,umask=077,allow_other,nodev,nosuid,noexec
ExecStop=/usr/bin/umount /mnt/aether-shares/AetherEncryptedBackups
TimeoutStopSec=30
Restart=on-failure
RestartSec=30
[Install]
WantedBy=multi-user.target
''')
write('/usr/share/applications/aether-security.desktop', '''[Desktop Entry]
Type=Application
Name=Aether Security
Comment=Inspect protections and incomplete security setup
Exec=aether-security-center
Icon=security-high
Categories=System;Security;
Terminal=false
''')
write('/usr/libexec/aether-security-read-status', '''#!/usr/bin/python3
import os, pwd, sys
if len(sys.argv) != 1 or os.geteuid() != 0:
    raise SystemExit('Read-only privileged status helper; authorize through Aether Security.')
uid = os.environ.get('PKEXEC_UID', '')
env = {'PATH': '/usr/bin:/usr/sbin:/bin:/sbin', 'LANG': 'C.UTF-8'}
if uid.isdigit():
    env['SUDO_USER'] = pwd.getpwuid(int(uid)).pw_name
os.execve('/usr/bin/aether-security-status', ['/usr/bin/aether-security-status'], env)
''', 0o755)
write('/usr/share/polkit-1/actions/org.aether.security.policy', '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN" "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
 <vendor>Aether Linux</vendor>
 <action id="org.aether.security.read-status">
  <description>Inspect protected security settings</description>
  <message>Authentication is required to read Aether's active firewall and confinement settings. This check does not change them.</message>
  <defaults><allow_any>no</allow_any><allow_inactive>no</allow_inactive><allow_active>auth_admin_keep</allow_active></defaults>
  <annotate key="org.freedesktop.policykit.exec.path">/usr/libexec/aether-security-read-status</annotate>
 </action>
</policyconfig>
''')
write('/usr/share/applications/aether-backup-setup.desktop', '''[Desktop Entry]
Type=Application
Name=Set Up Encrypted Backups
Exec=konsole --hold -e sudo aether-backup setup
Icon=folder-backup
Categories=System;Security;
Terminal=false
''')
write('/usr/share/applications/aether-install.desktop', '''[Desktop Entry]
Type=Application
Name=Install Aether Linux
Comment=Install from live media with optional LUKS2 encryption
Exec=konsole --hold -e sudo aether-install
Icon=drive-harddisk
Categories=System;
Terminal=false
''')
for name in ('checklist.json', 'sources.json', 'SECURITY.md'):
    if (source / name).exists():
        dest = Path('/usr/share/aether-security') / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, dest)
subprocess.run(['python3', str(source / 'configure-security.py')], check=True)
subprocess.run(['systemctl', '--root=/', 'enable', 'aether-firewall.service', 'apparmor.service', 'aether-zram.service'], check=True)
print('AETHER_SECURITY_INTEGRATION_INSTALLED; boot verification pending')
