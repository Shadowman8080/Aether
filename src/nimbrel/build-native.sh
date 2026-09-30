#!/bin/bash
set -euo pipefail
if [ "${AETHER_NIMBREL_NS:-}" != 1 ]; then exec unshare --mount --propagation private env AETHER_NIMBREL_NS=1 bash "$0"; fi
root=/opt/aether/experience-system
test "$(findmnt -n -o SOURCE --mountpoint "$root")" = /dev/nbd3p3
mount --rbind /dev "$root/dev"; mount --make-rslave "$root/dev"
mount -t proc proc "$root/proc"; mount -t sysfs sysfs "$root/sys"
mount -t tmpfs tmpfs "$root/run"
mkdir -p "$root/recipes-nimbrel" "$root/build"
mount --bind /opt/aether/build/nimbrel "$root/recipes-nimbrel"
mount --bind /opt/aether/build/native-desktop "$root/build"
chroot "$root" /usr/bin/cmake -S /recipes-nimbrel -B /build/nimbrel -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr
chroot "$root" /usr/bin/cmake --build /build/nimbrel --parallel "$(nproc)"
chroot "$root" /usr/bin/cmake --install /build/nimbrel
chroot "$root" /usr/bin/python3 -m py_compile /usr/bin/nimbrel-client
sync
