#!/bin/bash
set -euo pipefail
cd /opt/aether
export PATH="/opt/aether/host-tools:$PATH" LC_ALL=C SOURCE_DATE_EPOCH=1788476400
date -u '+STARTED %FT%TZ' > logs/vmtools-x86.status
trap 'result=$?; echo "EXIT $result" >> /opt/aether/logs/vmtools-x86.status' EXIT
make -C sources/buildroot-2026.08 O=/opt/aether/build/prototype-x86 \
  BR2_EXTERNAL=/opt/aether/aether-external \
  BR2_DEFCONFIG=/opt/aether/configs/aether_vm_x86_defconfig defconfig
grep -qx BR2_PACKAGE_AETHER_VMTOOLS=y build/prototype-x86/.config
make -C sources/buildroot-2026.08 O=/opt/aether/build/prototype-x86 \
  BR2_JLEVEL="$(nproc)" -j"$(nproc)" aether-vmtools
