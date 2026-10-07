#!/usr/bin/env python3
"""Configure bundled VMware integration inside an offline Aether chroot."""
from pathlib import Path
import os
import shlex
import subprocess

release = Path('/etc/os-release').read_text()
assert any(line in ('ID=aether', 'ID="aether"') for line in release.splitlines())
required = (
    '/usr/bin/vmtoolsd', '/usr/bin/vmware-checkvm',
    '/usr/bin/vmware-user-suid-wrapper', '/usr/bin/vmware-vmblock-fuse',
    '/usr/bin/startplasma-x11', '/usr/bin/kwin_x11',
    '/usr/lib/open-vm-tools/plugins/vmusr/libdndcp.so',
    '/usr/lib/open-vm-tools/plugins/vmusr/libresolutionSet.so',
)
for name in required:
    if not Path(name).is_file():
        raise SystemExit('Required guest integration component missing: ' + name)
for name in ('/usr/bin/vmtoolsd', '/usr/lib/open-vm-tools/plugins/vmusr/libdndcp.so',
             '/usr/lib/open-vm-tools/plugins/vmusr/libresolutionSet.so'):
    result = subprocess.run(['ldd', name], capture_output=True, text=True, check=True)
    if 'not found' in result.stdout:
        raise SystemExit('Missing runtime library: ' + result.stdout)

def write(name, contents, mode=0o644):
    p = Path(name)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(contents)
    p.chmod(mode)

def session_key(directory, program):
    candidates = [p.stem for p in Path(directory).glob('*.desktop')
                  if program in p.read_text()]
    if len(candidates) != 1:
        raise SystemExit('Cannot identify a unique session for ' + program)
    return candidates[0]

x11 = session_key('/usr/share/xsessions', 'startplasma-x11')
wayland = session_key('/usr/share/wayland-sessions', 'startplasma-wayland')
conf = Path('/etc/lightdm/lightdm.conf')
text = conf.read_text()
# Main-file settings override conf.d, so move this managed default to conf.d.
conf.write_text('\n'.join(line for line in text.splitlines()
                          if not line.startswith('user-session=')) + '\n')
write('/etc/lightdm/lightdm.conf.d/50-aether-session.conf',
      '[Seat:*]\nuser-session=' + wayland + '\n')
write('/usr/libexec/aether-guest-display-setup', '''#!/bin/sh
set -eu
config=/etc/lightdm/lightdm.conf.d/60-aether-vmware-session.conf
session=''' + shlex.quote(x11) + '''
hypervisor=$(systemd-detect-virt --vm 2>/dev/null || true)
if [ "$hypervisor" = vmware ] || [ "$hypervisor" = oracle ]; then
    printf '%s\\n' '[Seat:*]' "user-session=$session" > "$config.tmp"
    chmod 644 "$config.tmp"
    mv -f "$config.tmp" "$config"
    # LightDM reads Session= from ~/.dmrc, which overrides the seat default.
    # Both bundled desktop integration clients need X11, so keep VM users
    # on the X11 session even if they previously saved a Wayland choice.
    for dmrc in /home/*/.dmrc; do
        [ -f "$dmrc" ] || continue
        grep -qi "^[[:space:]]*Session[[:space:]]*=[[:space:]]*$session$" "$dmrc" && continue
        tmp=$(mktemp)
        grep -v -i '^[[:space:]]*Session[[:space:]]*=' "$dmrc" > "$tmp" || true
        grep -q '^\\[Desktop\\]' "$tmp" || printf '%s\\n' '[Desktop]' >> "$tmp"
        printf 'Session=%s\\n' "$session" >> "$tmp"
        cat "$tmp" > "$dmrc"
        rm -f "$tmp"
    done
else
    rm -f "$config"
fi
''', 0o755)
write('/etc/systemd/system/lightdm.service.d/20-aether-guest.conf', '''[Unit]
Wants=vmtoolsd.service vmware-vmblock.service
After=vmtoolsd.service vmware-vmblock.service

[Service]
ExecStartPre=/usr/libexec/aether-guest-display-setup
''')
write('/usr/bin/aether-vmware-session', '''#!/bin/sh
[ "$(systemd-detect-virt --vm 2>/dev/null)" = vmware ] || exit 0
[ "${XDG_SESSION_TYPE:-}" = x11 ] || exit 0
exec /usr/bin/vmware-user-suid-wrapper
''', 0o755)
write('/etc/xdg/autostart/vmware-user.desktop', '''[Desktop Entry]
Type=Application
Name=VMware Desktop Integration
Exec=/usr/bin/aether-vmware-session
TryExec=/usr/bin/vmware-user-suid-wrapper
NoDisplay=true
X-KDE-autostart-phase=1
''')
# First-class integration manager: reports and enables the bundled components.
write('/usr/bin/aether-vmware-tools', Path('/recipes/guest/aether-vmware-tools').read_text(), 0o755)
os.chown('/usr/bin/vmware-user-suid-wrapper', 0, 0)
Path('/usr/bin/vmware-user-suid-wrapper').chmod(0o4755)
for service in ('vmtoolsd.service', 'vmware-vmblock.service'):
    subprocess.run(['systemctl', '--root=/', 'enable', service], check=True)
subprocess.run(['sh', '-n', '/usr/bin/aether-vmware-session'], check=True)
subprocess.run(['sh', '-n', '/usr/libexec/aether-guest-display-setup'], check=True)
subprocess.run(['sh', '-n', '/usr/bin/aether-vmware-tools'], check=True)
print('VMware integration configured; native-host validation still required.')
