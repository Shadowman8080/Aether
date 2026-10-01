#!/bin/bash
set -euo pipefail
cd /opt/aether
stage=build/iso-stage-guest-x86
mkdir -p "$stage/boot/grub/i386-pc"
install -m644 build/prototype-x86/images/bzImage "$stage/boot/vmlinuz"
install -m644 build/prototype-x86/images/rootfs.cpio.gz "$stage/boot/initramfs.gz"
install -m644 build/prototype-x86/images/grub-eltorito.img "$stage/boot/grub/i386-pc/eltorito.img"
printf 'Aether Linux 0.1 x86\n' > "$stage/boot/aether-marker"
cat > "$stage/boot/grub/grub.cfg" <<'EOF'
serial --unit=0 --speed=115200
terminal_input console serial
terminal_output console serial
set timeout=3
set default=0
menuentry 'Aether Linux 0.1.1 - x86 (32-bit prototype)' {
    linux /boot/vmlinuz console=tty0 console=ttyS0,115200 rdinit=/init quiet loglevel=3
    initrd /boot/initramfs.gz
}
EOF
xorriso -as mkisofs -R -J -V AETHER_011_X86 \
  -b boot/grub/i386-pc/eltorito.img -no-emul-boot -boot-load-size 4 -boot-info-table \
  -o images/aether-0.1.1-x86.iso "$stage"
