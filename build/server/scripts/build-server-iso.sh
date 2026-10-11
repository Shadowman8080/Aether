#!/bin/bash
# Assemble the Aether Server live ISO from a prepared server rootfs.
#
# Mirrors build-desktop-iso.sh but for the console-first server: no Plasma, no
# Plymouth splash, and a grub menu that leads with the installer + live console.
# The squashfs keeps the machine small so the same ISO can be used for "try"
# and "install". Graphical install works on the framebuffer, EGLFS or an
# existing session via aether-server-setup.
set -euo pipefail
if [ "${AETHER_SERVER_ISO_NS:-}" != 1 ]; then
    exec unshare --mount --propagation private env AETHER_SERVER_ISO_NS=1 bash "$0"
fi

base=${AETHER_BASE:-/opt/aether}
root=$base/server-system
stage=$base/build/server-iso
initrd=$base/build/server-initrd
out=$base/images/aether-server-0.1-x86_64.iso
release=6.18.54-aether4

exec 9>"$base/build/native-server/build.lock"
flock -n 9 || { echo 'A server build is still running.' >&2; exit 1; }

source=$(findmnt -n -o SOURCE --mountpoint "$root")
[[ "$source" == /dev/loop*p3 ]]
[[ "$(losetup -n -O BACK-FILE "${source%p3}")" == "$base/build/aether-server-0.1-system.raw" ]]
test -x "$root/usr/bin/aether-server-setup"
test -f "$root/usr/share/aether/server/roles.json"
test -f "$root/usr/libexec/aether-server-install-backend"
command -v mksquashfs >/dev/null && command -v xorriso >/dev/null
command -v cpio >/dev/null && command -v gzip >/dev/null
test ! -e "$out" && test ! -e "$out.partial"

mkdir -p "$stage/live" "$stage/boot/grub" "$initrd"/{bin,lib,usr,dev,proc,sys,run,newroot}
install -m755 "$base/build/prototype/target/bin/busybox" "$initrd/bin/busybox"
ln -sfn busybox "$initrd/bin/sh"
ln -sfn lib "$initrd/lib64"
ln -sfn ../lib "$initrd/usr/lib"
for library in libc.so.6 libresolv.so.2 ld-linux-x86-64.so.2; do
    install -m755 "$root/usr/lib/$library" "$initrd/lib/$library"
done
install -m755 "$base/desktop/scripts/live-init" "$initrd/init"
install -m755 "$base/desktop/scripts/live-shutdown" "$initrd/shutdown"
chroot "$initrd" /bin/busybox true
chroot "$initrd" /bin/sh -n /init
chroot "$initrd" /bin/sh -n /shutdown
(cd "$initrd" && find . -print0 | cpio --null --quiet -o --format=newc --owner=0:0 | gzip -9) >"$stage/boot/initrd.img"

install -m644 "$root/boot/vmlinuz-$release" "$stage/boot/vmlinuz"
printf '0.1\n' >"$stage/live/aether-server-release"

mksquashfs "$root" "$stage/live/rootfs.squashfs" -noappend -comp xz \
    -processors "$(nproc)" -one-file-system -wildcards \
    -e 'dev/*' 'proc/*' 'sys/*' 'run/*' 'tmp/*' 'build/*' 'sources/*' 'recipes/*'

cat >"$stage/boot/grub/grub.cfg" <<'EOF'
set default=0
set timeout=8
serial --unit=0 --speed=115200
terminal_input console serial
terminal_output console serial
menuentry 'Install / Try Aether Server' {
    linux /boot/vmlinuz console=tty0 console=ttyS0,115200n8 systemd.unit=multi-user.target
    initrd /boot/initrd.img
}
menuentry 'Aether Server live diagnostics' {
    linux /boot/vmlinuz console=tty0 console=ttyS0,115200n8 systemd.show_status=yes loglevel=7
    initrd /boot/initrd.img
}
if [ "$grub_platform" = efi ]; then
    menuentry 'UEFI firmware settings' { fwsetup }
fi
EOF

# Only this private mount namespace sees the native GRUB modules.
mount --bind "$root/usr/lib/grub" /usr/lib/grub
mount -o remount,bind,ro /usr/lib/grub
"$root/usr/bin/grub-mkrescue" --fonts= --themes= --locales= -o "$out.partial" "$stage" -volid AETHER_SERVER_01
mv "$out.partial" "$out"
sha256sum "$out"
echo 'Server ISO assembled. BIOS and UEFI boot checks are required before release.'