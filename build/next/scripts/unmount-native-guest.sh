#!/bin/bash
set -euo pipefail
root=/opt/aether/guest-system
source=$(findmnt -n -o SOURCE --mountpoint "$root")
[[ "$source" == /dev/loop*p3 ]]
loop=${source%p3}
[[ "$(losetup -n -O BACK-FILE "$loop")" == /opt/aether/build/aether-0.2.1-system.raw ]]
sync
umount "$root/boot/efi"
umount "$root"
losetup -d "$loop"
test -z "$(losetup -j /opt/aether/build/aether-0.2.1-system.raw)"
echo 'New guest image detached; ready for boot tests or export.'
