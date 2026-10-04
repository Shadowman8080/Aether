#!/bin/bash
set -euo pipefail
if [ "${AETHER_DESKTOP_NS:-}" != 1 ]; then
 exec unshare --mount --propagation private env AETHER_DESKTOP_NS=1 bash "$0" "$@"
fi
script=${1:-build-desktop-foundation.py}
case "$script" in
 build-desktop-foundation.py|build-desktop-dependencies.py|build-desktop-frameworks.py|build-desktop-plasma.py|build-desktop-apps.py|build-desktop-domain.py) ;;
 *) echo 'Unknown desktop build stage' >&2; exit 1 ;;
esac
exec 9>/opt/aether/build/native-desktop/build.lock
flock -n 9 || { echo 'Another desktop build is running.' >&2; exit 1; }
root=/opt/aether/desktop-system
source=$(findmnt -n -o SOURCE --mountpoint "$root")
[[ "$source" == /dev/loop*p3 ]]
[[ "$(losetup -n -O BACK-FILE "${source%p3}")" == /opt/aether/build/aether-0.3-system.raw ]]
mount --rbind /dev "$root/dev"
mount --make-rslave "$root/dev"
mount -t proc proc "$root/proc"
mount -t sysfs sysfs "$root/sys"
mount -t tmpfs tmpfs "$root/run"
mount --bind /opt/aether/build/native-desktop "$root/build"
mount --bind /opt/aether/sources "$root/sources"
mount -o remount,bind,ro "$root/sources"
mount --bind /opt/aether/desktop "$root/recipes"
mount -o remount,bind,ro "$root/recipes"
label=${AETHER_BUILD_LABEL:-build}
[[ "$label" =~ ^[a-z0-9-]+$ ]] || exit 1
statusfile=/opt/aether/logs/desktop/$label.status
date -u '+STARTED %FT%TZ' >"$statusfile"
trap 'echo "EXIT $?" >>"$statusfile"' EXIT
chroot "$root" /usr/bin/env -i HOME=/root USER=root TERM=dumb PATH=/usr/bin:/usr/sbin:/bin:/sbin LC_ALL=C.UTF-8 SYSTEMD_OFFLINE=1 AETHER_BUILD_ONLY="${AETHER_BUILD_ONLY:-}" CFLAGS='-O2 -pipe -march=x86-64' CXXFLAGS='-O2 -pipe -march=x86-64' MAKEFLAGS="-j$(nproc)" CMAKE_BUILD_PARALLEL_LEVEL="$(nproc)" python3 "/recipes/scripts/$script"
