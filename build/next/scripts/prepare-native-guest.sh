#!/bin/bash
set -euo pipefail
base=/opt/aether
original=$base/build/aether-system.raw
image=$base/build/aether-0.2.1-system.raw
root=$base/guest-system
mkdir -p "$root" "$base/build/native-guest" "$base/logs/next/native-guest"
test -z "$(losetup -j "$original")"
if [ ! -f "$image" ]; then cp --reflink=auto --sparse=always "$original" "$image"; fi
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
mkdir -p "$root"/{build,sources,recipes} "$base/build/native-guest/host-tools"
cp /usr/bin/kmk /usr/bin/kmk_* /usr/bin/nasm /usr/bin/yasm "$base/build/native-guest/host-tools/"
cp -a /usr/share/kBuild "$base/build/native-guest/host-tools/"
echo 'Separate 0.2.1 image mounted; original 0.2 disk preserved.'
