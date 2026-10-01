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
chmod 755 "$root/usr/bin/aurasearch"
chmod 755 "$root/usr/lib/aether-initramfs/start-splash" "$root/usr/lib/aether-initramfs/unlock-root"
# XDG system defaults affect new accounts without overwriting user configuration.
if [ -x "$root/usr/bin/update-desktop-database" ]; then
 chroot "$root" /usr/bin/update-desktop-database /usr/share/applications
fi
if [ -x "$root/usr/bin/gtk-update-icon-cache" ]; then
 chroot "$root" /usr/bin/gtk-update-icon-cache -f -t /usr/share/icons/hicolor
fi
