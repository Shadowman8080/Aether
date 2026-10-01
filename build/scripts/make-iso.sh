#!/bin/bash
set -euo pipefail
cd /opt/aether
src=build/prototype/images
stage=build/iso-stage
mkdir -p "$stage/boot/grub/i386-pc" images
install -m 644 "$src/bzImage" "$stage/boot/vmlinuz"
install -m 644 "$src/rootfs.cpio.gz" "$stage/boot/initramfs.gz"
install -m 644 "$src/grub-eltorito.img" "$stage/boot/grub/i386-pc/eltorito.img"
printf 'Aether Linux 0.1-dev\n' > "$stage/boot/aether-marker"
cat > "$stage/boot/grub/grub.cfg" <<'CFG'
serial --unit=0 --speed=115200
terminal_input console serial
terminal_output console serial
set default=0
set timeout=3
menuentry 'Aether Linux 0.1 - First Light' {
    linux /boot/vmlinuz console=tty0 console=ttyS0,115200 rdinit=/init
    initrd /boot/initramfs.gz
}
menuentry 'Aether Linux - boot self-test (powers off)' {
    linux /boot/vmlinuz console=tty0 console=ttyS0,115200 rdinit=/init aether.selftest=1
    initrd /boot/initramfs.gz
}
CFG
# Only create filesystem images in the build directory; never format VM disks.
truncate -s 16M "$stage/boot/efi.img"
mkfs.vfat "$stage/boot/efi.img"
mmd -i "$stage/boot/efi.img" ::/EFI ::/EFI/BOOT
mcopy -o -i "$stage/boot/efi.img" "$src/efi-part/EFI/BOOT/bootx64.efi" ::/EFI/BOOT/BOOTX64.EFI
mkdir -p "$stage/EFI/BOOT"
install -m 644 "$src/efi-part/EFI/BOOT/bootx64.efi" "$stage/EFI/BOOT/BOOTX64.EFI"
xorriso -as mkisofs -R -J -V AETHER_01 \
    -b boot/grub/i386-pc/eltorito.img -no-emul-boot -boot-load-size 4 -boot-info-table \
    -eltorito-alt-boot -e boot/efi.img -no-emul-boot \
    -o images/aether-0.1-x86_64.iso "$stage"
cp "$src/bzImage" images/vmlinuz-aether
cp "$src/rootfs.cpio.gz" images/initramfs-aether.cpio.gz
(cd images; sha256sum aether-0.1-x86_64.iso vmlinuz-aether initramfs-aether.cpio.gz > SHA256SUMS)
