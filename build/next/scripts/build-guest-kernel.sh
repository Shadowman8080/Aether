#!/bin/bash
set -euo pipefail
cd /opt/aether
exec >logs/next/guest-kernel.log 2>&1
date -u '+STARTED %FT%TZ' > logs/next/guest-kernel.status
trap 'echo "EXIT $?" >>/opt/aether/logs/next/guest-kernel.status' EXIT
src=/opt/aether/sources/linux-6.18.54
out=/opt/aether/build/kernel-6.18.54
for opt in DRM_FBDEV_EMULATION DRM_BOCHS DRM_VBOXVIDEO MOUSE_PS2_VMMOUSE; do
 "$src/scripts/config" --file "$out/.config" --enable "$opt"
done
make -C "$src" O="$out" olddefconfig
for opt in DRM_FBDEV_EMULATION DRM_BOCHS DRM_VBOXVIDEO EFIVAR_FS MOUSE_PS2_VMMOUSE; do grep -qx "CONFIG_$opt=y" "$out/.config"; done
make -C "$src" O="$out" -j"$(nproc)" bzImage modules
stage=/opt/aether/build/guest-kernel-stage
mkdir -p "$stage/boot"
make -C "$src" O="$out" -j"$(nproc)" INSTALL_MOD_PATH="$stage" modules_install
release=$(make -s -C "$src" O="$out" kernelrelease)
install -m644 "$out/arch/x86/boot/bzImage" "$stage/boot/vmlinuz-$release"
install -m644 "$out/.config" "$stage/boot/config-$release"
install -m644 "$out/System.map" "$stage/boot/System.map-$release"
cp "$out/.config" next/configs/guest-kernel.config
