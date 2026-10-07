#!/bin/bash
set -euo pipefail
if [ "${AETHER_MODERN_NS:-}" != 1 ]; then exec unshare --mount --propagation private env AETHER_MODERN_NS=1 bash "$0" "$@"; fi
root=/opt/aether/build/apt-root
mount --rbind /dev "$root/dev"; mount --make-rslave "$root/dev"
mount -t proc proc "$root/proc"; mount -t sysfs sysfs "$root/sys"
mount -t tmpfs tmpfs "$root/run"
mkdir -p "$root/modern"
mount --bind /opt/aether/build/modern-20261006 "$root/modern"
chroot "$root" /usr/bin/python3 /modern/project/build/modern-20261006/build-packages.py "$@"
