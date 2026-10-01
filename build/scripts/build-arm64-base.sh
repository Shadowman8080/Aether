#!/bin/bash
set -euo pipefail
cd /opt/aether
export PATH="/opt/aether/host-tools:$PATH" LC_ALL=C SOURCE_DATE_EPOCH=1788476400
date -u '+STARTED %FT%TZ' > logs/build-arm64.status
trap 'result=$?; echo "EXIT $result" >> /opt/aether/logs/build-arm64.status' EXIT
make -C sources/buildroot-2026.08 O=/opt/aether/build/prototype-arm64 \
  BR2_DEFCONFIG=/opt/aether/configs/aether_arm64_defconfig defconfig
make -C sources/buildroot-2026.08 O=/opt/aether/build/prototype-arm64 \
  BR2_JLEVEL="$(nproc)" -j"$(nproc)"
