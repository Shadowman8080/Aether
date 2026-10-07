#!/usr/bin/env python3
"""Package Aether's integration files from an already prepared offline root."""
import hashlib,json,shutil,subprocess
from pathlib import Path
b=Path('/opt/aether/build/modern-20261006');root=b/'root';p=b/'packages/aether-experience';p.mkdir(parents=True,exist_ok=True)
paths=['usr/bin/aether-settings','usr/bin/aether-update','usr/bin/aether-recovery','usr/bin/aether-signing-setup','usr/bin/aether-preferences','usr/bin/aether-firewall','usr/bin/nimbrel','usr/bin/nimbrel-client','usr/bin/nimbrel-library','usr/libexec/aether-system-admin','usr/lib/aether-updates','usr/lib/aether-initramfs/encrypted-init','usr/share/doc/aether-updates','usr/share/applications/org.aether.Settings.desktop','usr/share/applications/org.aether.Nimbrel.desktop','usr/share/icons/hicolor/scalable/apps/org.aether.Nimbrel.svg','usr/plugins/kf6/krunner/libkrunner_nimbrel.so','etc/xdg/autostart/aether-welcome.desktop','opt/nimbrel/local_server.py']
paths+=['etc/systemd/system/'+u for u in ('nimbrel-local.service','nimbrel-local.socket','nimbrel-engine.service','aether-update-check.service','aether-update-check.timer','aether-system-health.service')]
paths+=['usr/libexec/aether-update-notify','etc/xdg/autostart/aether-update-notify.desktop']
for name in paths:
 source=root/name;dest=p/name;dest.parent.mkdir(parents=True,exist_ok=True)
 if source.is_dir():shutil.copytree(source,dest,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
 else:shutil.copy2(source,dest)
control=p/'DEBIAN';control.mkdir(exist_ok=True)
(control/'control').write_text('Package: aether-experience\nVersion: 0.3.2~dev20261006-1\nArchitecture: amd64\nMaintainer: Aether Linux developers\nDepends: python, qtbase, glibc, gcc, grub, rsync, nimbrel-engine, flatpak, fwupd, kdeconnect, plasma-discover\nDescription: Aether settings, on-demand AI and update/recovery integration\n')
(control/'conffiles').write_text(''.join('/'+name+'\n' for name in paths if name.startswith('etc/')))
(control/'postinst').write_text('''#!/bin/sh
set -eu
[ "$1" = configure ] || exit 0
for unit in nimbrel-local.service nimbrel-engine.service; do
 path=/etc/systemd/system/multi-user.target.wants/$unit
 if [ -L "$path" ]; then rm -- "$path"; fi
done
for pair in nimbrel-local.socket:sockets.target.wants aether-update-check.timer:timers.target.wants aether-system-health.service:graphical.target.wants; do
 unit=${pair%:*}; target=${pair#*:}
 if [ "$unit" = nimbrel-local.socket ] && [ -e /etc/nimbrel/disabled ]; then continue; fi
 mkdir -p /etc/systemd/system/$target
 if [ ! -e /etc/systemd/system/$target/$unit ] && [ ! -L /etc/systemd/system/$target/$unit ]; then ln -s ../$unit /etc/systemd/system/$target/$unit; fi
done
# Rebuild the candidate's boot image; never select or restart the live system.
release=$(find /boot -maxdepth 1 -type f -name 'vmlinuz-*' -printf '%f\\n' | sed 's/^vmlinuz-//' | sort -V | tail -n 1)
if [ -n "$release" ]; then aether-mkinitramfs /boot/initramfs-$release.img; fi
''')
(control/'postinst').chmod(0o755)
output=b/'packages/aether-experience_0.3.2~dev20261006-1_amd64.deb'
subprocess.run(['dpkg-deb','--build','--root-owner-group',str(p),str(output)],check=True)
subprocess.run(['dpkg','--root='+str(root),'--install',str(output)],check=True)
(b/'integration-package.json').write_text(json.dumps({'archive':output.name,'sha256':hashlib.file_digest(output.open('rb'),'sha256').hexdigest()},indent=2)+'\n')
