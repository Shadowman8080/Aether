#!/bin/bash
set -euo pipefail
cd /opt/aether
exec >logs/next/persistent-kernel.log 2>&1
date -u '+STARTED %FT%TZ' >logs/next/persistent-kernel.status
trap 'echo "EXIT $?" >>/opt/aether/logs/next/persistent-kernel.status' EXIT
src=/opt/aether/sources/linux-6.18.54
out=/opt/aether/build/kernel-6.18.54
cfg=("$src/scripts/config" --file "$out/.config")
for opt in PSI VIRT_DRIVERS VMWARE_VMCI VMWARE_PVSCSI VBOXGUEST VBOXSF_FS FUSE_FS SCSI_VIRTIO SCSI_MPT3SAS SCSI_MPT2SAS FUSION FUSION_SPI FUSION_SAS SYSFB_SIMPLEFB DRM_SIMPLEDRM FRAMEBUFFER_CONSOLE EFI_VARS_PSTORE; do
  "${cfg[@]}" --enable "$opt"
done
make -C "$src" O="$out" olddefconfig
for opt in PSI VMWARE_PVSCSI VBOXGUEST SCSI_VIRTIO FUSION_SPI FUSION_SAS DRM_SIMPLEDRM; do
  grep -qx "CONFIG_$opt=y" "$out/.config"
done
make -C "$src" O="$out" -j"$(nproc)" bzImage modules
stage=/opt/aether/build/kernel-stage
make -C "$src" O="$out" -j"$(nproc)" INSTALL_MOD_PATH="$stage" modules_install
release=$(make -s -C "$src" O="$out" kernelrelease)
install -m644 "$out/arch/x86/boot/bzImage" "$stage/boot/vmlinuz-$release"
install -m644 "$out/System.map" "$stage/boot/System.map-$release"
install -m644 "$out/.config" "$stage/boot/config-$release"
install -m644 "$out/.config" next/configs/kernel.config
