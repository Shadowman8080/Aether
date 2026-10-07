#!/bin/bash
set -euo pipefail
if [ "${PACKAGE_NS:-}" != 1 ]; then exec unshare --mount --propagation private env PACKAGE_NS=1 bash "$0"; fi
root=/opt/aether/build/apt-root
mount --rbind /dev "$root/dev"; mount --make-rslave "$root/dev"
mount -t proc proc "$root/proc"; mount -t sysfs sysfs "$root/sys"
mount -t tmpfs tmpfs "$root/run"
mount --bind /opt/aether/build/modern-20261006 "$root/modern"
chroot "$root" python3 /modern/project/build/modern-20261006/package-native.py
