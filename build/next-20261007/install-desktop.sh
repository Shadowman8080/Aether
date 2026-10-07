#!/bin/bash
set -euo pipefail
if [ "${AETHER_DESKTOP_NS:-}" != 1 ]; then exec unshare --mount --propagation private env AETHER_DESKTOP_NS=1 bash "$0"; fi
b=/opt/aether/build/next-20261007
cleanup() { for directory in run sys proc dev; do if mountpoint -q "$b/root/$directory"; then umount -R "$b/root/$directory"; fi; done; }
trap cleanup EXIT
mount --rbind /dev "$b/root/dev"; mount --make-rslave "$b/root/dev"
mount -t proc proc "$b/root/proc"; mount -t sysfs sysfs "$b/root/sys"
mount -t tmpfs tmpfs "$b/root/run"
python3 "$b/project/build/next-20261007/install-usb.py"
python3 "$b/project/build/next-20261007/install-desktop.py"
chroot "$b/root" /usr/lib/systemd/systemd --version
chroot "$b/root" dpkg --audit
