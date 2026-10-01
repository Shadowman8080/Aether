#!/bin/bash
set -euo pipefail
cd /opt/aether
jobs=$(nproc)
export LC_ALL=C
export PATH="/opt/aether/host-tools:$PATH"
export SOURCE_DATE_EPOCH=1788476400
make -C sources/buildroot-2026.08 O=/opt/aether/build/prototype BR2_DEFCONFIG=/opt/aether/configs/aether_defconfig defconfig
for required in BR2_x86_64 BR2_x86_x86_64 BR2_TOOLCHAIN_BUILDROOT_GLIBC BR2_PACKAGE_BASH BR2_PACKAGE_COREUTILS BR2_LINUX_KERNEL BR2_TARGET_GRUB2_I386_PC BR2_TARGET_GRUB2_X86_64_EFI; do
    grep -qx "${required}=y" build/prototype/.config || { echo "Missing required configuration: $required" >&2; exit 1; }
done
make -C sources/buildroot-2026.08 O=/opt/aether/build/prototype BR2_JLEVEL="$jobs" -j"$jobs"
