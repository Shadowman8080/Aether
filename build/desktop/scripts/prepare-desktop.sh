#!/bin/bash
set -euo pipefail
base=/opt/aether
image=$base/build/aether-0.3-system.raw
root=$base/desktop-system
mkdir -p "$base/desktop/scripts" "$base/desktop/configs" "$base/build/native-desktop" "$base/logs/desktop" "$root"
test -z "$(losetup -j "$base/build/aether-0.2.1-system.raw")"
if [ ! -f "$image" ]; then cp --reflink=auto --sparse=always "$base/build/aether-0.2.1-system.raw" "$image"; fi
if ! mountpoint -q "$root"; then
 test -z "$(losetup -j "$image")"
 loop=$(losetup --find --show --partscan "$image")
 udevadm settle
 mount "${loop}p3" "$root"
 mount "${loop}p2" "$root/boot/efi"
fi
source=$(findmnt -n -o SOURCE --mountpoint "$root")
[[ "$source" == /dev/loop*p3 ]]
[[ "$(losetup -n -O BACK-FILE "${source%p3}")" == "$image" ]]
mkdir -p "$root"/{build,sources,recipes}
grep -qxF '/desktop-system/' "$base/.gitignore" || printf '\n/desktop-system/\n' >> "$base/.gitignore"
echo 'Desktop development image mounted separately from released images.'
ls "$root/usr/bin/llvm-config" "$root/usr/lib/libLLVM"* 2>/dev/null || true
