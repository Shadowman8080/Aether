#!/bin/bash
set -euo pipefail
cd /opt/aether
export PATH="/opt/aether/host-tools:$PATH" LC_ALL=C SOURCE_DATE_EPOCH=1788476400
date -u '+STARTED %FT%TZ' > logs/guest-x64.status
trap 'result=$?; echo "EXIT $result" >> /opt/aether/logs/guest-x64.status' EXIT
make -C sources/buildroot-2026.08 O=/opt/aether/build/prototype BR2_JLEVEL="$(nproc)" -j"$(nproc)"
for option in CONFIG_VBOXGUEST CONFIG_VBOXSF_FS CONFIG_FUSE_FS CONFIG_VMWARE_VMCI CONFIG_VMXNET3 CONFIG_VMWARE_PVSCSI; do
    grep -qx "$option=y" build/prototype/build/linux-6.18.7/.config
done
bash scripts/make-guest-iso.sh
python3 scripts/test-guest-x86_64.py bios
python3 scripts/test-guest-x86_64.py uefi
sha256sum images/aether-0.1.1-x86_64.iso > images/aether-0.1.1-x86_64.iso.sha256
