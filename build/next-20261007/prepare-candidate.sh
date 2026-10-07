#!/bin/bash
set -euo pipefail
if [ "${AETHER_CANDIDATE_NS:-}" != 1 ]; then exec unshare --mount --propagation private env AETHER_CANDIDATE_NS=1 bash "$0"; fi
b=/opt/aether/build/next-20261007
test -f /opt/aether/build/modern-20261006/root/etc/os-release
mkdir -p "$b/root"
if mountpoint -q "$b/root"; then echo 'Refusing to modify an overlay candidate; preserve it and unmount first.' >&2; exit 1; fi
if [ ! -f "$b/candidate-copy-complete" ]; then
 # Materialize once: reusing overlay upperdirs as lowerdirs can invalidate inode origins.
 rsync -aHAXx --numeric-ids /opt/aether/build/modern-20261006/root/ "$b/root/"
 touch "$b/candidate-copy-complete"
fi
grep -qx 'ID=aether' "$b/root/etc/os-release"
cleanup() { for directory in run sys proc dev; do if mountpoint -q "$b/root/$directory"; then umount -R "$b/root/$directory"; fi; done; }
trap cleanup EXIT
mount --rbind /dev "$b/root/dev"; mount --make-rslave "$b/root/dev"
mount -t proc proc "$b/root/proc"; mount -t sysfs sysfs "$b/root/sys"
mount -t tmpfs tmpfs "$b/root/run"
python3 "$b/project/build/next-20261007/package-foundation.py"
