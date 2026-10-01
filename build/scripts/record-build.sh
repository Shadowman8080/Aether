#!/bin/bash
set -euo pipefail
cd /opt/aether
mkdir -p images/build-record
cp build/prototype/.config images/build-record/buildroot.config
cp build/prototype/build/linux-6.18.7/.config images/build-record/linux.config
cp configs/aether_defconfig images/build-record/
cp README.md images/README.md
{
    printf 'Aether Linux 0.1-dev build record\n\n'
    date -u '+Recorded: %Y-%m-%dT%H:%M:%SZ'
    printf 'Target: generic x86-64 (baseline ISA)\n'
    printf 'Buildroot: 2026.08\nKernel: 6.18.7-aether\n'
    printf 'Parallel build jobs: '; nproc
    build/prototype/host/bin/x86_64-aether-linux-gnu-gcc --version | head -n 1
    build/prototype/host/bin/x86_64-aether-linux-gnu-ld --version | head -n 1
    grep '^GLIBC_VERSION = ' sources/buildroot-2026.08/package/glibc/glibc.mk
    grep '^BUSYBOX_VERSION = ' sources/buildroot-2026.08/package/busybox/busybox.mk
    grep '^BASH_VERSION = ' sources/buildroot-2026.08/package/bash/bash.mk
    grep '^COREUTILS_VERSION = ' sources/buildroot-2026.08/package/coreutils/coreutils.mk
    grep '^GRUB2_VERSION = ' sources/buildroot-2026.08/boot/grub2/grub2.mk
    printf '\nBoot test results:\n'
    grep -aE 'AETHER_FIRMWARE=|AETHER_SELFTEST_PASS' logs/boot-bios.log logs/boot-uefi.log
} > images/build-record/manifest.txt
find sources/buildroot-2026.08/dl -type f ! -name '*lock*' -print0 | sort -z | xargs -0 sha256sum > images/build-record/source-sha256sums.txt
cp logs/boot-bios.log logs/boot-uefi.log images/build-record/
tar --exclude=__pycache__ -czf images/aether-build-recipes.tar.gz README.md .gitignore build-env.sh configs overlay scripts
tar -czf images/aether-build-record.tar.gz -C images build-record
(cd images; sha256sum aether-0.1-x86_64.iso vmlinuz-aether initramfs-aether.cpio.gz aether-build-recipes.tar.gz aether-build-record.tar.gz > SHA256SUMS)
