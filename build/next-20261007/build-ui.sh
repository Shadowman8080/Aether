#!/bin/bash
set -euo pipefail
if [ "${AETHER_NEXT_UI_NS:-}" != 1 ]; then exec unshare --mount --propagation private env AETHER_NEXT_UI_NS=1 bash "$0"; fi
root=/opt/aether/build/apt-root
mkdir -p "$root/next"
cleanup() { for m in next run sys proc dev; do if mountpoint -q "$root/$m"; then umount -R "$root/$m"; fi; done; }
trap cleanup EXIT
mount --rbind /dev "$root/dev"; mount --make-rslave "$root/dev"
mount -t proc proc "$root/proc"; mount -t sysfs sysfs "$root/sys"
mount -t tmpfs tmpfs "$root/run"
mount --bind /opt/aether/build/next-20261007 "$root/next"
chroot "$root" env LD_LIBRARY_PATH=/next/stage/systemd/usr/lib/systemd:/next/stage/systemd/usr/lib /next/stage/systemd/usr/lib/systemd/systemd --version
chroot "$root" cmake -S /next/project/src/controlcenter -B /next/obj/controlcenter -G Ninja -DCMAKE_INSTALL_PREFIX=/usr -DCMAKE_BUILD_TYPE=Release
chroot "$root" cmake --build /next/obj/controlcenter --parallel "$(nproc)"
chroot "$root" env DESTDIR=/next/stage/controlcenter cmake --install /next/obj/controlcenter
chroot "$root" env QT_QPA_PLATFORM=offscreen /next/stage/controlcenter/usr/bin/aether-settings --capture-dir /next/ui-captures
echo CONTROL_CENTER_STAGED
