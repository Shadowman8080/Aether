#!/bin/bash
set -euo pipefail
cd /opt/aether
src=build/prototype-arm64/images
stage=build/iso-stage-arm64
mkdir -p "$stage/boot/grub" "$stage/EFI/BOOT" images
install -m 644 "$src/Image" "$stage/boot/vmlinuz"
install -m 644 "$src/rootfs.cpio.gz" "$stage/boot/initramfs.gz"
printf 'Aether Linux ARM64 VM prototype\n' > "$stage/boot/aether-marker"
cat > "$stage/boot/grub/grub.cfg" <<'CFG'
set default=0
set timeout=3
menuentry 'Aether Linux ARM64 VM - console prototype' {
    linux /boot/vmlinuz console=tty0 console=ttyAMA0,115200 rdinit=/init quiet loglevel=3
    initrd /boot/initramfs.gz
}
menuentry 'Aether Linux ARM64 VM - boot self-test' {
    linux /boot/vmlinuz console=tty0 console=ttyAMA0,115200 rdinit=/init aether.selftest=1
    initrd /boot/initramfs.gz
}
CFG
truncate -s 16M "$stage/boot/efi.img"
mkfs.vfat "$stage/boot/efi.img"
mmd -i "$stage/boot/efi.img" ::/EFI ::/EFI/BOOT
mcopy -o -i "$stage/boot/efi.img" "$src/efi-part/EFI/BOOT/bootaa64.efi" ::/EFI/BOOT/BOOTAA64.EFI
install -m 644 "$src/efi-part/EFI/BOOT/bootaa64.efi" "$stage/EFI/BOOT/BOOTAA64.EFI"
xorriso -as mkisofs -R -J -V AETHER_ARM64 \
    -e boot/efi.img -no-emul-boot -o images/aether-0.1.1-arm64-vm.iso "$stage"
sha256sum images/aether-0.1.1-arm64-vm.iso > images/aether-0.1.1-arm64-vm.iso.sha256
