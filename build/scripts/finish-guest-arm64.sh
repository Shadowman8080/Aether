#!/bin/bash
set -euo pipefail
cd /opt/aether
export PATH="/opt/aether/host-tools:$PATH" LC_ALL=C SOURCE_DATE_EPOCH=1788476400
status=logs/guest-arm64.status
date -u '+STARTED %FT%TZ' > "$status"
trap 'result=$?; echo "EXIT $result" >> /opt/aether/logs/guest-arm64.status' EXIT
deadline=$((SECONDS+7200))
while ! grep -q '^EXIT ' logs/build-arm64.status; do
    (( SECONDS < deadline )) || { echo 'Timed out waiting for ARM64 base'; exit 1; }
    sleep 5
done
grep -qx 'EXIT 0' logs/build-arm64.status || { echo 'ARM64 base failed'; exit 1; }
cp configs/aether_arm64_defconfig configs/aether_vm_arm64_defconfig
echo BR2_PACKAGE_AETHER_VMTOOLS=y >> configs/aether_vm_arm64_defconfig
make -C sources/buildroot-2026.08 O=/opt/aether/build/prototype-arm64 \
    BR2_EXTERNAL=/opt/aether/aether-external BR2_DEFCONFIG=/opt/aether/configs/aether_vm_arm64_defconfig defconfig
make -C sources/buildroot-2026.08 O=/opt/aether/build/prototype-arm64 BR2_JLEVEL="$(nproc)" -j"$(nproc)" aether-vmtools
bash scripts/build-vbox.sh arm64
bash scripts/install-vbox.sh arm64
make -C sources/buildroot-2026.08 O=/opt/aether/build/prototype-arm64 BR2_JLEVEL="$(nproc)" -j"$(nproc)"
for option in CONFIG_VBOXGUEST CONFIG_VBOXSF_FS CONFIG_FUSE_FS CONFIG_VMWARE_VMCI CONFIG_VMXNET3 CONFIG_BLK_DEV_NVME CONFIG_SATA_AHCI; do
    grep -qx "$option=y" build/prototype-arm64/build/linux-6.18.7/.config
done
bash scripts/make-arm64-iso.sh
python3 scripts/test-boot-arm64.py
