#!/bin/bash
set -euo pipefail
if [ "${AETHER_GUEST_NS:-}" != 1 ]; then
 exec unshare --mount --propagation private env AETHER_GUEST_NS=1 bash "$0" "$@"
fi
root=/opt/aether/guest-system
source=$(findmnt -n -o SOURCE --mountpoint "$root")
[[ "$source" == /dev/loop*p3 ]]
[[ "$(losetup -n -O BACK-FILE "${source%p3}")" == /opt/aether/build/aether-0.2.1-system.raw ]]
mount --rbind /dev "$root/dev"
mount --make-rslave "$root/dev"
mount -t proc proc "$root/proc"
mount -t sysfs sysfs "$root/sys"
mount -t tmpfs tmpfs "$root/run"
mount --bind /opt/aether/build/native-guest "$root/build"
mount --bind /opt/aether/sources "$root/sources"
mount -o remount,bind,ro "$root/sources"
mount --bind /opt/aether/next "$root/recipes"
mount -o remount,bind,ro "$root/recipes"
date -u '+STARTED %FT%TZ' >/opt/aether/logs/next/native-guest-build.status
trap 'echo "EXIT $?" >>/opt/aether/logs/next/native-guest-build.status' EXIT
chroot "$root" /usr/bin/env -i HOME=/root TERM=dumb PATH=/usr/bin:/usr/sbin:/bin:/sbin:/build/host-tools LC_ALL=C.UTF-8 MAKEFLAGS="-j$(nproc)" CMAKE_BUILD_PARALLEL_LEVEL="$(nproc)" bash /recipes/scripts/build-native-guest.sh "$@"
