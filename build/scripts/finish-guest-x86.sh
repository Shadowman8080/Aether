#!/bin/bash
set -euo pipefail
cd /opt/aether
export PATH="/opt/aether/host-tools:$PATH" LC_ALL=C SOURCE_DATE_EPOCH=1788476400
status=logs/guest-x86.status
date -u '+STARTED %FT%TZ' > "$status"
trap 'result=$?; echo "EXIT $result" >> /opt/aether/logs/guest-x86.status' EXIT
for component in vmtools-x86; do
    deadline=$((SECONDS+3600))
    while ! grep -q '^EXIT ' "logs/$component.status"; do
        (( SECONDS < deadline )) || { echo "Timed out waiting for $component"; exit 1; }
        sleep 5
    done
    grep -qx 'EXIT 0' "logs/$component.status" || { echo "$component failed"; exit 1; }
done
bash scripts/build-vbox.sh x86
bash scripts/install-vbox.sh x86
make -C sources/buildroot-2026.08 O=/opt/aether/build/prototype-x86 BR2_JLEVEL="$(nproc)" -j"$(nproc)" linux-reconfigure
make -C sources/buildroot-2026.08 O=/opt/aether/build/prototype-x86 BR2_JLEVEL="$(nproc)" -j"$(nproc)"
for option in CONFIG_VBOXGUEST CONFIG_VBOXSF_FS CONFIG_FUSE_FS CONFIG_VMWARE_VMCI CONFIG_VMXNET3 CONFIG_VMWARE_PVSCSI; do
    grep -qx "$option=y" build/prototype-x86/build/linux-6.18.7/.config
done
bash scripts/make-guest-x86-iso.sh
python3 scripts/test-guest-x86.py bios
sha256sum images/aether-0.1.1-x86.iso > images/aether-0.1.1-x86.iso.sha256
