#!/usr/bin/env python3
"""Apply Aether workstation defaults inside an OFFLINE Aether chroot.

Do not execute this against the Ubuntu build host. Existing user passwords,
boot trust keys and disk encryption are never changed by this script.
"""
from pathlib import Path
import grp
import json
import os
import pwd
import shutil
import subprocess

assert os.geteuid() == 0
assert 'ID=aether' in Path('/etc/os-release').read_text().splitlines()
assert os.environ.get('SYSTEMD_OFFLINE') == '1'

def write(name, data, mode=0o644):
    p = Path(name)
    if p.is_symlink():
        raise RuntimeError('Refusing symlink: ' + name)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(data)
    p.chmod(mode)

def run(*args):
    subprocess.run(args, check=True)

# Fail before changing PAM if the dictionary required by password checks is absent.
dictionary_files = [Path('/usr/share/cracklib/pw_dict.' + suffix) for suffix in ('hwm', 'pwd', 'pwi')]
if not all(p.is_file() and p.stat().st_size > 0 for p in dictionary_files):
    run('/usr/sbin/create-cracklib-dict', '-o', '/usr/share/cracklib/pw_dict',
        '/usr/share/cracklib/cracklib-small')
for path in dictionary_files:
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError('Password dictionary generation failed: ' + str(path))
    path.chmod(0o644)
probe = subprocess.run(['/usr/sbin/cracklib-check'], input='administration\n',
                       text=True, capture_output=True, check=True)
if 'error' in (probe.stdout + probe.stderr).lower() or 'dictionary' not in probe.stdout.lower():
    raise RuntimeError('Password dictionary check failed: ' + probe.stdout + probe.stderr)

write('/etc/sysctl.d/60-aether-security.conf', '''# Aether workstation baseline. User namespaces remain available for sandboxes.
kernel.randomize_va_space = 2
kernel.kptr_restrict = 2
kernel.dmesg_restrict = 1
kernel.perf_event_paranoid = 3
kernel.yama.ptrace_scope = 1
kernel.unprivileged_bpf_disabled = 2
kernel.kexec_load_disabled = 1
kernel.sysrq = 176
fs.suid_dumpable = 0
fs.protected_hardlinks = 1
fs.protected_symlinks = 1
fs.protected_fifos = 2
fs.protected_regular = 2
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv4.conf.all.secure_redirects = 0
net.ipv4.conf.default.secure_redirects = 0
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.default.send_redirects = 0
net.ipv4.conf.all.accept_source_route = 0
net.ipv4.conf.default.accept_source_route = 0
net.ipv6.conf.all.accept_redirects = 0
net.ipv6.conf.default.accept_redirects = 0
net.ipv6.conf.all.accept_source_route = 0
net.ipv6.conf.default.accept_source_route = 0
net.ipv4.tcp_syncookies = 1
''')
write('/etc/security/faillock.conf', '''# Temporary throttling; no permanent lockout and root remains excluded.
deny = 5
fail_interval = 900
unlock_time = 120
silent
audit
''')
write('/etc/pam.d/system-auth', '''# Aether: common console, greeter, screen-lock and polkit authentication.
auth optional pam_faildelay.so delay=3000000
auth required pam_faillock.so preauth silent
auth [success=1 default=bad] pam_unix.so try_first_pass
auth [default=die] pam_faillock.so authfail
auth sufficient pam_faillock.so authsucc
auth required pam_deny.so
''')
write('/etc/pam.d/system-password', '''# Quality checks affect new passwords; existing credentials are preserved.
password requisite pam_pwquality.so retry=3
password required pam_unix.so yescrypt shadow use_authtok
''')
write('/etc/security/pwquality.conf', '''minlen = 12
minclass = 0
dictcheck = 1
usercheck = 1
maxrepeat = 3
enforcing = 1
enforce_for_root
''')
session = Path('/etc/pam.d/system-session')
if 'pam_umask.so' not in session.read_text():
    session.write_text(session.read_text() + 'session optional pam_umask.so umask=0077\n')
write('/etc/pam.d/sudo', '''auth include system-auth
account include system-account
session required pam_limits.so
session include system-session
''')
write('/etc/sudoers.d/10-aether-security', '''Defaults use_pty
Defaults timestamp_timeout=5
Defaults passwd_timeout=2
Defaults passwd_tries=3
Defaults env_reset
Defaults umask=0077
''', 0o440)
run('/usr/sbin/visudo', '-c')
write('/etc/profile.d/60-aether-private-files.sh', 'umask 077\n')
write('/etc/security/limits.d/60-aether-security.conf', '* hard core 0\n')
write('/etc/systemd/coredump.conf.d/60-aether-security.conf', '''[Coredump]
Storage=none
ProcessSizeMax=0
''')
write('/etc/systemd/journald.conf.d/60-aether-security.conf', '''[Journal]
Storage=persistent
Compress=yes
SystemMaxUse=256M
SystemKeepFree=512M
RuntimeMaxUse=32M
MaxRetentionSec=1month
ForwardToSyslog=no
''')
write('/etc/systemd/system.conf.d/60-aether-security.conf', '[Manager]\nDefaultLimitCORE=0\n')
write('/etc/systemd/user.conf.d/60-aether-security.conf', '[Manager]\nDefaultLimitCORE=0\n')
write('/etc/systemd/system/tmp.mount.d/60-aether-security.conf', '''[Mount]
Options=mode=1777,strictatime,nosuid,nodev,size=25%,nr_inodes=1m
''')
write('/etc/systemd/sleep.conf.d/60-aether-security.conf', '''# Disk hibernation needs an encrypted resume design; ordinary sleep remains available.
[Sleep]
AllowHibernation=no
AllowHybridSleep=no
AllowSuspendThenHibernate=no
''')
# Unencrypted swap must not receive new sensitive memory. No disk is formatted.
fstab = Path('/etc/fstab')
lines = fstab.read_text().splitlines()
lines = ['# Aether security: unencrypted swap disabled: ' + line
         if not line.lstrip().startswith('#') and len(line.split()) >= 3
         and line.split()[2] == 'swap' else line for line in lines]
fstab.write_text('\n'.join(lines) + '\n')
write('/etc/systemd/system/aether-zram.service', '''[Unit]
Description=Aether compressed RAM swap (no persistent swap data)
DefaultDependencies=no
After=systemd-modules-load.service systemd-remount-fs.service
Before=swap.target shutdown.target
Conflicts=shutdown.target
ConditionPathExists=/sys/class/zram-control
[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/libexec/aether-zram-start
# systemd discovers the active device as dev-zram0.swap and stops it itself.
# A second swapoff here races that unit during shutdown.
[Install]
WantedBy=swap.target
''')
write('/etc/modules-load.d/aether-zram.conf', 'zram\n')
write('/usr/libexec/aether-zram-start', '''#!/bin/sh
set -eu
[ -e /sys/block/zram0/disksize ] || exit 1
# Do not resize or reformat an existing active device.
[ "$(cat /sys/block/zram0/disksize)" = 0 ] || exit 0
memory=$(awk '/^MemTotal:/ {print int($2 * 512)}' /proc/meminfo)
echo "$memory" > /sys/block/zram0/disksize
/usr/sbin/mkswap /dev/zram0
/usr/sbin/swapon --priority 100 /dev/zram0
''', 0o755)
write('/etc/xdg/kscreenlockerrc', '''[Daemon]
Autolock=true
LockOnResume=true
Timeout=5
RequirePassword=true
Lock=true
LockGrace=0
''')
write('/etc/xdg/klipperrc', '''[General]
KeepClipboardContents=false
MaxClipItems=1
IgnoreSelection=true
SelectionTextOnly=true
SyncClipboards=false
''')
write('/etc/xdg/kded_device_automounterrc', '[General]\nAutomountEnabled=false\n')
write('/etc/xdg/kactivitymanagerd-pluginsrc', '[Plugin-org.kde.ActivityManager.Resources.Scoring]\nwhat-to-remember=1\n')
write('/etc/xdg/baloofilerc', '''[Basic Settings]
Indexing-Enabled=true
[General]
only basic indexing=true
index hidden folders=false
exclude filters=.git,node_modules,__pycache__,build,.cache,.ssh,.gnupg,.password-store,*.key,*.pem,*.p12,*.pfx
''')
# Session ACLs granted by logind replace permanent access to input devices.
for name in ('input', 'audio', 'video'):
    try:
        if 'aether' in grp.getgrnam(name).gr_mem:
            run('/usr/bin/gpasswd', '-d', 'aether', name)
    except KeyError:
        pass
for account in pwd.getpwall():
    if 1000 <= account.pw_uid < 65534:
        home = Path(account.pw_dir)
        if home.is_dir() and not home.is_symlink():
            home.chmod(0o700)
Path('/root').chmod(0o700)
Path('/etc/shadow').chmod(0o600)
if Path('/etc/gshadow').exists():
    Path('/etc/gshadow').chmod(0o600)
# Prevent DBus and socket activation from quietly enabling network discovery.
for service in ('avahi-daemon.service', 'avahi-daemon.socket', 'cups-browsed.service', 'sshd.service', 'sshd.socket'):
    if Path('/usr/lib/systemd/system', service).exists():
        override = Path('/etc/systemd/system', service)
        if override.is_symlink() and os.readlink(override) == '/dev/null':
            continue
        run('systemctl', '--root=/', 'disable', service)
        run('systemctl', '--root=/', 'mask', service)
write('/etc/NetworkManager/conf.d/60-aether-security.conf', '''[connection]
connection.mdns=0
connection.llmnr=0
''')
write('/etc/systemd/resolved.conf.d/60-aether-security.conf', '''[Resolve]
LLMNR=no
MulticastDNS=no
''')
write('/etc/ssh/sshd_config.d/60-aether-security.conf', '''# Applies when an administrator explicitly installs/enables SSH.
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
PermitEmptyPasswords no
X11Forwarding no
AllowAgentForwarding no
AllowTcpForwarding no
PermitTunnel no
MaxAuthTries 3
LoginGraceTime 30
AllowGroups wheel
''')
write('/etc/ssh/ssh_config.d/60-aether-security.conf', '''Host *
    ForwardAgent no
    StrictHostKeyChecking ask
''')
run('systemctl', '--root=/', 'enable', 'systemd-timesyncd.service')
for name in ('cups.service', 'cups.socket'):
    unit = Path('/usr/lib/systemd/system', name)
    if unit.is_file():
        unit.write_text(unit.read_text().replace('/var/run/cups', '/run/cups'))
print('AETHER_SECURITY_DEFAULTS_CONFIGURED; runtime enforcement tests still required')
