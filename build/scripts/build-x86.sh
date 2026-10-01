#!/bin/bash
set -euo pipefail
cd /opt/aether
export PATH="/opt/aether/host-tools:$PATH"
export LC_ALL=C SOURCE_DATE_EPOCH=1788476400
date -u '+STARTED %FT%TZ' > logs/build-x86.status
trap 'result=$?; echo "EXIT $result" >> /opt/aether/logs/build-x86.status' EXIT
make -C sources/buildroot-2026.08 O=/opt/aether/build/prototype-x86 \
  BR2_DEFCONFIG=/opt/aether/configs/aether_x86_defconfig defconfig
for option in BR2_i386 BR2_x86_i686 BR2_TOOLCHAIN_BUILDROOT_GLIBC BR2_TARGET_GRUB2_I386_PC; do
  grep -qx "$option=y" build/prototype-x86/.config
done
make -C sources/buildroot-2026.08 O=/opt/aether/build/prototype-x86 \
  BR2_JLEVEL="$(nproc)" -j"$(nproc)"
stage=build/iso-stage-x86
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
menuentry 'Aether Linux 0.1 - x86 (32-bit prototype)' {
    linux /boot/vmlinuz console=tty0 console=ttyS0,115200 rdinit=/init
    initrd /boot/initramfs.gz
}
EOF
xorriso -as mkisofs -R -J -V AETHER_01_X86 \
  -b boot/grub/i386-pc/eltorito.img -no-emul-boot -boot-load-size 4 -boot-info-table \
  -o images/aether-0.1-x86.iso "$stage"
python3 scripts/test-boot-x86.py
(cd images; sha256sum aether-0.1-x86.iso > aether-0.1-x86.iso.sha256)
