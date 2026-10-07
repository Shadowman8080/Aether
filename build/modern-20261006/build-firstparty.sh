#!/bin/bash
set -euo pipefail
if [ "${AETHER_UI_NS:-}" != 1 ]; then exec unshare --mount --propagation private env AETHER_UI_NS=1 bash "$0"; fi
root=/opt/aether/build/apt-root
mount --rbind /dev "$root/dev"; mount --make-rslave "$root/dev"
mount -t proc proc "$root/proc"; mount -t sysfs sysfs "$root/sys"
mount -t tmpfs tmpfs "$root/run"
mount --bind /opt/aether/build/modern-20261006 "$root/modern"
for app in controlcenter nimbrel; do
 chroot "$root" cmake -S "/modern/project/src/$app" -B "/modern/obj/$app" -G Ninja -DCMAKE_INSTALL_PREFIX=/usr -DCMAKE_BUILD_TYPE=Release
 chroot "$root" cmake --build "/modern/obj/$app" --parallel "$(nproc)"
 chroot "$root" env DESTDIR=/modern/stage cmake --install "/modern/obj/$app"
done
