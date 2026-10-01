#!/bin/bash
# Prepare a new kernel for the desktop/live image; preserve released disk images.
set -euo pipefail
base=/opt/aether
src=$base/sources/linux-6.18.54
out=$base/build/kernel-6.18.54
stage=$base/build/desktop-kernel-stage
exec >"$base/logs/desktop/kernel.log" 2>&1
date -u '+STARTED %FT%TZ' >"$base/logs/desktop/kernel.status"
trap 'echo "EXIT $?" >>/opt/aether/logs/desktop/kernel.status' EXIT
# This existing build tree is reusable; no released image is mounted or edited here.
cp "$base/next/configs/guest-kernel.config" "$out/.config"
for opt in BLK_DEV_LOOP INPUT_UINPUT OVERLAY_FS SQUASHFS SQUASHFS_XZ SQUASHFS_ZSTD; do
 "$src/scripts/config" --file "$out/.config" --enable "$opt"
done
"$src/scripts/config" --file "$out/.config" --set-str LOCALVERSION '-aether3'
make -C "$src" O="$out" olddefconfig
for opt in EFI EFIVAR_FS DRM_BOCHS DRM_VBOXVIDEO OVERLAY_FS SQUASHFS BLK_DEV_LOOP INPUT_UINPUT; do
 grep -qx "CONFIG_$opt=y" "$out/.config"
done
make -C "$src" O="$out" -j"$(nproc)" bzImage modules
mkdir -p "$stage/boot"
make -C "$src" O="$out" -j"$(nproc)" INSTALL_MOD_PATH="$stage" modules_install
release=$(make -s -C "$src" O="$out" kernelrelease)
install -m644 "$out/arch/x86/boot/bzImage" "$stage/boot/vmlinuz-$release"
install -m644 "$out/.config" "$stage/boot/config-$release"
install -m644 "$out/System.map" "$stage/boot/System.map-$release"
cp "$out/.config" "$base/desktop/configs/kernel-x86_64.config"
printf '%s\n' "$release" >"$stage/kernel-release"
