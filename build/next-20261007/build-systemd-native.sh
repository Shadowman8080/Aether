#!/bin/bash
set -euo pipefail
if [ "${AETHER_NEXT_NS:-}" != 1 ]; then exec unshare --mount --propagation private env AETHER_NEXT_NS=1 bash "$0" "$@"; fi
root=/opt/aether/build/apt-root
mkdir -p "$root/next"
cleanup() { for m in next run sys proc dev; do if mountpoint -q "$root/$m"; then umount -R "$root/$m"; fi; done; }
trap cleanup EXIT
mount --rbind /dev "$root/dev"; mount --make-rslave "$root/dev"
mount -t proc proc "$root/proc"; mount -t sysfs sysfs "$root/sys"
mount -t tmpfs tmpfs "$root/run"
mount --bind /opt/aether/build/next-20261007 "$root/next"
chroot "$root" /usr/bin/python3 /next/build-systemd.py "$@"
