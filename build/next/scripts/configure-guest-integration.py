#!/usr/bin/env python3
"""Run inside the Aether chroot after native guest packages finish."""
from pathlib import Path
import os, subprocess
def write(name, text, mode=0o644):
 p=Path(name); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(text); p.chmod(mode)
def call(*args): subprocess.run(args,check=True)
write('/etc/os-release','NAME="Aether Linux"\nPRETTY_NAME="Aether Linux 0.2.1 development"\nID=aether\nVERSION_ID=0.2.1\nVERSION="0.2.1 development"\nRELEASE_TYPE=development\n')
write('/etc/issue','Aether Linux 0.2.1 development \\n \\l\n\n')
write('/etc/motd','Welcome to Aether Linux 0.2.1.\n\nRun startx for the guest integration session.\nRun aether-guest-status to inspect firmware and guest services.\nUse sudo for administration. Your files and settings persist.\n')
write('/etc/systemd/system/vmtoolsd.service','''[Unit]
Description=VMware guest services
ConditionVirtualization=vmware
After=local-fs.target network.target
[Service]
ExecStart=/usr/bin/vmtoolsd
Restart=on-failure
RestartSec=5
TimeoutStopSec=20
[Install]
WantedBy=multi-user.target
''')
write('/etc/systemd/system/vboxservice.service','''[Unit]
Description=VirtualBox guest services
ConditionVirtualization=oracle
After=local-fs.target systemd-udev-trigger.service
[Service]
ExecStart=/usr/bin/VBoxService --foreground
Restart=on-failure
RestartSec=5
TimeoutStopSec=20
[Install]
WantedBy=multi-user.target
''')
write('/etc/systemd/system/vmware-vmblock.service','''[Unit]
Description=VMware desktop file-transfer filesystem
ConditionVirtualization=vmware
After=local-fs.target
[Service]
RuntimeDirectory=vmblock-fuse
RuntimeDirectoryMode=0755
ExecStart=/usr/bin/vmware-vmblock-fuse -f -o allow_other /run/vmblock-fuse
ExecStop=/usr/bin/umount /run/vmblock-fuse
Restart=on-failure
TimeoutStopSec=20
[Install]
WantedBy=multi-user.target
''')
Path('/usr/bin/vmware-user-suid-wrapper').chmod(0o4755)
write('/etc/systemd/system/vboxdrmclient.service','''[Unit]
Description=VirtualBox VMSVGA display resizing
ConditionVirtualization=oracle
ConditionPathExists=/sys/module/vmwgfx
After=systemd-udev-trigger.service vboxservice.service
[Service]
ExecStart=/usr/bin/VBoxDRMClient
Restart=on-failure
RestartSec=5
TimeoutStopSec=20
[Install]
WantedBy=multi-user.target
''')
write('/etc/udev/rules.d/60-aether-vbox.rules','KERNEL=="vboxguest", OWNER="root", GROUP="root", MODE="0600"\nKERNEL=="vboxuser", OWNER="root", GROUP="root", MODE="0666"\n')
for group in ('vboxsf','vboxdrmipc'):
 if not any(s.startswith(group+':') for s in Path('/etc/group').read_text().splitlines()): call('groupadd','-r',group)
call('usermod','-aG','vboxsf,vboxdrmipc,video,input','aether')
for service in ('vmtoolsd','vmware-vmblock','vboxservice','vboxdrmclient'):
 call('systemctl','--root=/','enable',service+'.service')
write('/etc/X11/Xwrapper.config','allowed_users=console\nneeds_root_rights=yes\n')
write('/etc/X11/xorg.conf.d/10-aether-modesetting.conf','''Section "Device"
    Identifier "Aether virtual display"
    Driver "modesetting"
    Option "AccelMethod" "none"
EndSection
''')
write('/etc/X11/xinit/xinitrc','''#!/bin/bash
exec dbus-run-session -- /usr/bin/aether-x-session
''',0o755)
write('/usr/bin/aether-x-session','''#!/bin/bash
set -u
export XDG_SESSION_TYPE=x11 XDG_CURRENT_DESKTOP=Aether
export GTK_THEME=Adwaita
runtime="${XDG_RUNTIME_DIR:-/tmp/aether-runtime-$(id -u)}"
if [ ! -d "$runtime" ]; then (umask 077; mkdir "$runtime") || exit 1; fi
[ "$(stat -c %u "$runtime")" = "$(id -u)" ] || exit 1
chmod 700 "$runtime"
export XDG_RUNTIME_DIR="$runtime"
clients=()
cleanup() { for pid in "${clients[@]}"; do kill "$pid" 2>/dev/null || true; done; }
trap cleanup EXIT
case "$(systemd-detect-virt --vm 2>/dev/null)" in
 vmware) vmware-user-suid-wrapper ;;
 oracle)
  for feature in clipboard vmsvga seamless; do
   VBoxClient --foreground --"$feature" & clients+=("$!")
  done ;;
esac
twm -f /etc/X11/twm/system.twmrc & clients+=("$!")
aether-guest-panel
''',0o755)
write('/etc/X11/twm/system.twmrc','''NoGrabServer
RestartPreviousState
DecorateTransients
RandomPlacement
TitleFont "fixed"
MenuFont "fixed"
IconFont "fixed"
ResizeFont "fixed"
Color {
 BorderColor "#64748b"
 DefaultBackground "#f1f5f9"
 DefaultForeground "#0f172a"
 TitleBackground "#e2e8f0"
 TitleForeground "#0f172a"
}
Button1 = : root : f.menu "main"
Button1 = : title : f.move
Button2 = : title : f.resize
menu "main" {
 "Aether" f.title
 "Terminal" f.exec "xterm -fa 'DejaVu Sans Mono' -fs 11 &"
 "Guest status" f.exec "xterm -hold -e aether-guest-status &"
}
''')
write('/usr/bin/aether-efi-status','''#!/bin/bash
if [ -d /sys/firmware/efi ]; then
 echo "Firmware: UEFI $(cat /sys/firmware/efi/fw_platform_size 2>/dev/null)-bit"
 findmnt --mountpoint /sys/firmware/efi/efivars
else
 echo 'Firmware: legacy BIOS. Select UEFI in the VM firmware settings to use EFI services.'
fi
findmnt --mountpoint /boot/efi
''',0o755)
write('/usr/bin/aether-guest-status','''#!/bin/bash
aether-efi-status
printf '\\nVirtualization: '
systemd-detect-virt --vm || true
printf '\\nGuest services:\\n'
systemctl --no-pager --full status vmtoolsd vmware-vmblock vboxservice vboxdrmclient || true
printf '\\nVirtualBox utilities: '
VBoxControl --version
printf '\\nVMware tools package: 13.1.0-25218885\\n'
if vmware-checkvm >/dev/null 2>&1; then vmtoolsd --version; fi
printf '\\nDesktop clients:\\n'
ps -eo user,pid,args | grep -E '[V]BoxClient|[v]mtoolsd -n vmusr|[V]BoxDRMClient' || true
if [ -n "${DISPLAY:-}" ]; then xrandr --current; fi
''',0o755)
write('/usr/bin/aether-mount-share','''#!/bin/bash
set -euo pipefail
if [ "$(id -u)" != 0 ] || [ "$#" != 1 ]; then
 echo 'Usage: sudo aether-mount-share SHARED_FOLDER_NAME' >&2; exit 2
fi
name=$1
[[ "$name" =~ ^[a-zA-Z0-9_.\\ -]+$ && "$name" != . && "$name" != .. ]] || { echo 'Invalid share name' >&2; exit 2; }
dest="/mnt/aether-shares/$name"
test ! -L /mnt/aether-shares
test ! -L "$dest"
if mountpoint -q "$dest"; then echo 'This share is already mounted.' >&2; exit 1; fi
install -d -m755 "$dest"
uid=${SUDO_UID:-0}; gid=${SUDO_GID:-0}
case "$(systemd-detect-virt --vm)" in
 vmware) vmhgfs-fuse ".host:/$name" "$dest" -o "uid=$uid,gid=$gid,allow_other" ;;
 oracle) mount -t vboxsf -o "uid=$uid,gid=$gid" -- "$name" "$dest" ;;
 *) echo 'Shared folders require VMware or VirtualBox.' >&2; exit 1 ;;
esac
printf 'Mounted at %s\\n' "$dest"
''',0o755)
write('/usr/bin/aether-vmware-tools', Path('/recipes/guest/aether-vmware-tools').read_text(), 0o755)
flags=subprocess.check_output(['pkg-config','--cflags','--libs','gtk+-3.0'],text=True).split()
call('cc','-O2','-march=x86-64','/recipes/guest/aether-guest-panel.c','-o','/usr/bin/aether-guest-panel',*flags)
Path('/var/lib/xkb').mkdir(parents=True,exist_ok=True)
call('sh','-n','/usr/bin/aether-vmware-tools')
call('ldconfig')
call('systemd-analyze','--man=no','verify','/etc/systemd/system/vmtoolsd.service','/etc/systemd/system/vmware-vmblock.service','/etc/systemd/system/vboxservice.service','/etc/systemd/system/vboxdrmclient.service')
print('Configured source-native guest services and integration session.')
