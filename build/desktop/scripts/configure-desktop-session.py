#!/usr/bin/env python3
"""Run inside the offline Aether root after desktop installation, before boot tests."""
from pathlib import Path
import grp
import pwd
import shutil
import shlex
import subprocess

os_release = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines()
                  if '=' in line and not line.startswith('#'))
if shlex.split(os_release.get('ID', '')) != ['aether']:
    raise SystemExit('Refusing to configure a non-Aether system')
required = ('lightdm', 'aether-greeter', 'startplasma-wayland', 'kwin_wayland', 'plasmashell', 'krunner',
            'NetworkManager', 'pipewire', 'wireplumber', 'dolphin', 'konsole')
missing = [name for name in required if not shutil.which(name)]
if missing:
    raise SystemExit('Desktop is not installed: ' + ', '.join(missing))

def write(name, content, mode=0o644):
    path = Path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    path.chmod(mode)

for name, home in [('lightdm', '/var/lib/lightdm'), ('polkitd', '/var/lib/polkit-1'),
                   ('avahi', '/run/avahi-daemon')]:
    try:
        grp.getgrnam(name)
    except KeyError:
        subprocess.run(['groupadd', '--system', name], check=True)
    try:
        pwd.getpwnam(name)
    except KeyError:
        subprocess.run(['useradd', '--system', '--gid', name, '--home-dir', home,
                        '--shell', '/usr/bin/false', name], check=True)
    directory = Path(home)
    directory.mkdir(parents=True, exist_ok=True)
    shutil.chown(directory, name, name)

# The greeter runs on X11; LightDM starts the authenticated Wayland session.
sessions = [p for p in Path('/usr/share/wayland-sessions').glob('*.desktop')
            if 'startplasma-wayland' in p.read_text()]
if len(sessions) != 1:
    raise SystemExit('Expected exactly one installed Plasma Wayland session')
write('/etc/lightdm/lightdm.conf', '''[LightDM]
greeter-user=lightdm
minimum-vt=7

[Seat:*]
greeter-session=aether
greeter-wrapper=/usr/bin/dbus-run-session
session-wrapper=/usr/bin/aether-session
user-session=''' + sessions[0].stem + '''
allow-guest=false
greeter-allow-guest=false
xserver-allow-tcp=false

[XDMCPServer]
enabled=false

[VNCServer]
enabled=false
''')
write('/usr/share/xgreeters/aether.desktop', '''[Desktop Entry]
Name=Aether Login
Type=Application
Exec=/usr/bin/aether-greeter
''')
write('/usr/bin/aether-session', '''#!/bin/bash
# LightDM supplies a shell-quoted desktop Exec line as one argument.
if [ "$#" -eq 1 ]; then set -- /bin/sh -c "exec $1"; fi
if [ -r /etc/profile ]; then . /etc/profile; fi
if [ -r "$HOME/.profile" ]; then . "$HOME/.profile"; fi
if [ -r /usr/libexec/aether-vector-migrate.py ]; then
    /usr/bin/python3 /usr/libexec/aether-vector-migrate.py
fi
if [ -z "${DBUS_SESSION_BUS_ADDRESS:-}" ] && [ -n "${XDG_RUNTIME_DIR:-}" ] && [ -S "$XDG_RUNTIME_DIR/bus" ]; then
    export DBUS_SESSION_BUS_ADDRESS="unix:path=$XDG_RUNTIME_DIR/bus"
fi
if [ -z "${DBUS_SESSION_BUS_ADDRESS:-}" ]; then
    exec /usr/bin/dbus-run-session -- "$@"
fi
exec "$@"
''', 0o755)
write('/usr/lib/systemd/system/lightdm.service', '''[Unit]
Description=Aether graphical login
After=systemd-user-sessions.service systemd-logind.service
Conflicts=getty@tty7.service

[Service]
ExecStartPre=-/usr/bin/plymouth quit
ExecStart=/usr/sbin/lightdm
Restart=on-failure
BusName=org.freedesktop.DisplayManager

[Install]
Alias=display-manager.service
''')
write('/etc/X11/xorg.conf.d/10-aether-modesetting.conf', '''Section "Device"
    Identifier "Aether display"
    Driver "modesetting"
EndSection
''')
write('/etc/X11/Xwrapper.config', 'allowed_users=console\nneeds_root_rights=auto\n')
write('/etc/X11/xinit/xinitrc', '''#!/bin/bash
exec /usr/bin/aether-session /usr/bin/startplasma-x11
''', 0o755)
for directory, label in [('/usr/share/wayland-sessions', 'Aether'),
                         ('/usr/share/xsessions', 'Aether (X11 compatibility)')]:
    for entry in Path(directory).glob('*.desktop'):
        text = entry.read_text()
        if 'startplasma-' not in text:
            continue
        lines = [line for line in text.splitlines() if not line.startswith('Name[')]
        lines = ['Name=' + label if line.startswith('Name=') else line for line in lines]
        entry.write_text('\n'.join(lines) + '\n')
write('/etc/NetworkManager/conf.d/10-aether.conf', '[main]\nplugins=keyfile\ndns=systemd-resolved\n')
write('/etc/polkit-1/rules.d/40-aether-administrators.rules', '''polkit.addAdminRule(function(action, subject) {
    return ["unix-group:wheel"];
});
''')
write('/etc/xdg/xdg-desktop-portal/portals.conf', '[preferred]\ndefault=kde\n')
write('/usr/bin/aether-virtualbox-session', '''#!/bin/sh
[ "$(systemd-detect-virt --vm)" = oracle ] || exit 0
# These clients require X11. Wayland support is validated separately.
[ "${XDG_SESSION_TYPE:-}" = x11 ] || exit 0
for feature in clipboard draganddrop seamless; do
    /usr/bin/VBoxClient --"$feature"
done
''', 0o755)
write('/etc/xdg/autostart/aether-virtualbox.desktop', '''[Desktop Entry]
Type=Application
Name=VirtualBox Guest Integration
Exec=/usr/bin/aether-virtualbox-session
TryExec=/usr/bin/VBoxClient
NoDisplay=true
''')
subprocess.run(['systemctl', '--root=/', 'disable', 'systemd-networkd.service'], check=True)
subprocess.run(['systemctl', '--root=/', 'enable', 'NetworkManager.service',
                'systemd-resolved.service', 'lightdm.service', 'cups.socket',
                'bluetooth.service', 'avahi-daemon.service'], check=True)
subprocess.run(['systemctl', '--root=/', 'set-default', 'graphical.target'], check=True)
subprocess.run(['systemctl', '--root=/', '--global', 'enable', 'pipewire.socket',
                'pipewire-pulse.socket', 'wireplumber.service'], check=True)
subprocess.run(['python3', '/recipes/scripts/configure-vmware-desktop.py'], check=True)
subprocess.run(['python3', '/recipes/scripts/configure-login-options.py'], check=True)
print('Offline session configured. Login, lock, networking and sound require boot tests.')

# Preserve installed Aether security defaults on subsequent desktop rebuilds.
if Path("/usr/libexec/aether-configure-security").is_file():
    subprocess.run(["python3", "/usr/libexec/aether-configure-security"], check=True)
