#!/bin/bash
set -euo pipefail
root=${1:?Usage: install-assets.sh /path/to/offline/aether-root}
root=$(realpath -e "$root")
[[ "$root" != / && -f "$root/etc/os-release" ]] || { echo 'An offline Aether root is required.' >&2; exit 1; }
grep -q 'Aether' "$root/etc/os-release" || { echo 'Target is not an Aether root.' >&2; exit 1; }
assets=$(realpath "$(dirname "$0")/../assets")
while IFS= read -r -d '' source; do
 install -d -o 0 -g 0 -m 755 "$root/${source#"$assets/"}"
done < <(find "$assets" -mindepth 1 -type d -print0)
while IFS= read -r -d '' source; do
 install -D -o 0 -g 0 -m 644 "$source" "$root/${source#"$assets/"}"
done < <(find "$assets" -type f -print0)
pilot=$(realpath "$(dirname "$0")/../pilot" 2>/dev/null || true)
if [ -n "$pilot" ] && [ -f "$pilot/pilot.py" ]; then
 install -D -o 0 -g 0 -m 755 "$pilot/pilot.py" "$root/usr/bin/aether-pilot"
 install -D -o 0 -g 0 -m 755 "$pilot/aether-pilot-admin" "$root/usr/libexec/aether-pilot-admin"
 install -D -o 0 -g 0 -m 644 "$pilot/actions.json" "$root/usr/share/aether/pilot/actions.json"
fi
chmod 755 "$root/usr/bin/aurasearch" "$root/usr/bin/aether-login" "$root/usr/bin/aether-live-welcome" "$root/usr/bin/aether-pilot-ui" "$root/usr/bin/aether-mkinitramfs" "$root/usr/libexec/aether-live-autologin" "$root/usr/libexec/aether-live-report" "$root/usr/libexec/aether-installer-backend" "$root/usr/libexec/aether-secureboot-enroll" "$root/usr/libexec/aether-efi-updatevar" "$root/usr/bin/efi-updatevar"
chmod 755 "$root/usr/lib/aether-initramfs/start-splash" "$root/usr/lib/aether-initramfs/unlock-root" "$root/usr/lib/aether-initramfs/encrypted-init"
base=${AETHER_BASE:-/opt/aether}
if [ -f "$base/build/prototype/target/bin/busybox" ]; then
    install -D -o 0 -g 0 -m 755 "$base/build/prototype/target/bin/busybox" "$root/usr/lib/aether-initramfs/busybox"
fi
# XDG system defaults affect new accounts without overwriting user configuration.
if [ -x "$root/usr/bin/update-desktop-database" ]; then
 chroot "$root" /usr/bin/update-desktop-database /usr/share/applications
fi
if [ -x "$root/usr/bin/gtk-update-icon-cache" ]; then
 chroot "$root" /usr/bin/gtk-update-icon-cache -f -t /usr/share/icons/hicolor
fi
