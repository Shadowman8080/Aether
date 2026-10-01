#!/bin/bash
set -euo pipefail
cd /opt/aether
exec 9>build/persistent-finish.lock
flock -n 9
exec >logs/next/persistent-finish.log 2>&1
date -u '+STARTED %FT%TZ' >logs/next/persistent-finish.status
trap 'echo "EXIT $?" >>/opt/aether/logs/next/persistent-finish.status' EXIT
while ! grep -q '^EXIT ' logs/next/persistent-kernel.status; do sleep 5; done
grep -qx 'EXIT 0' logs/next/persistent-kernel.status
bash next/scripts/install-persistent-boot.sh
python3 next/scripts/clean-persistent-build-files.py
root=/opt/aether/system
source=$(findmnt -n -o SOURCE --mountpoint "$root")
[[ "$source" == /dev/loop*p3 ]]
loop=${source%p3}
[[ "$(readlink -f "$(losetup -n -O BACK-FILE "$loop")")" == /opt/aether/build/aether-system.raw ]]
sync
umount "$root/boot/efi"
umount "$root"
losetup -d "$loop"
python3 next/scripts/test-persistent.py bios
python3 next/scripts/test-persistent.py uefi
