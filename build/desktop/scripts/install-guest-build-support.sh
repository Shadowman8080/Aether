#!/bin/bash
# Let the installed image compile third-party kernel modules.
#
# VMware Tools and VirtualBox Guest Additions both build modules when they are
# installed, and both of them fail without a prepared kernel tree. The LFS base
# only ships sanitised userspace headers, so the tree is assembled here from the
# exact source and build output the running kernel was produced from.
set -euo pipefail
base=/opt/aether
root=$base/desktop-system
src=$base/sources/linux-6.18.54
build=$base/build/kernel-6.18.54
stage=$base/build/desktop-kernel-stage
release=$(cat "$stage/kernel-release")
[[ $release == 6.18.54-aether3 ]] || { echo "Unexpected kernel release: $release" >&2; exit 1; }
source=$(findmnt -n -o SOURCE --mountpoint "$root")
[[ $source == /dev/loop*p3 ]]
[[ $(losetup -n -O BACK-FILE "${source%p3}") == "$base/build/aether-0.3-system.raw" ]]
test -s "$build/Module.symvers"
dest=$root/usr/src/linux-6.18.54
mkdir -p "$root/usr/src"
rm -rf "$dest"
mkdir -p "$dest"
tar -C "$src" --exclude=.git -cf - . | tar -C "$dest" -xf -
install -m644 "$build/.config" "$dest/.config"
install -m644 "$build/Module.symvers" "$dest/Module.symvers"
# Generated Kconfig/header state and the helper programs `make modules` needs.
for dir in include/generated include/config arch/x86/include/generated; do
    mkdir -p "$dest/$dir"
    rsync -a --delete "$build/$dir/" "$dest/$dir/"
done
for helper in scripts/basic/fixdep scripts/mod/modpost scripts/kconfig/conf scripts/genksyms/genksyms; do
    test -f "$build/$helper" || continue
    install -D -m755 "$build/$helper" "$dest/$helper"
done
install -d "$root/usr/lib/modules/$release"
ln -sfn /usr/src/linux-6.18.54 "$root/usr/lib/modules/$release/build"
ln -sfn /usr/src/linux-6.18.54 "$root/usr/lib/modules/$release/source"
for program in gcc make perl pkg-config; do
    test -x "$root/usr/bin/$program" || { echo "The image has no $program; module builds cannot run." >&2; exit 1; }
done
test -f "$root/usr/include/xcb/xcb.h" || { echo 'The xcb development headers are missing; X11 guest drivers cannot build.' >&2; exit 1; }
test -f "$dest/include/generated/utsrelease.h"
grep -qx 'CONFIG_LOCALVERSION="-aether3"' "$dest/.config"
du -sh "$dest"
echo 'Prepared kernel tree installed; VMware Tools and VirtualBox Guest Additions can compile modules.'
