#!/bin/bash
# Assemble the native Aether root and source-built GRUB into a live desktop ISO.
set -euo pipefail
if [ "${AETHER_ISO_NS:-}" != 1 ]; then
 exec unshare --mount --propagation private env AETHER_ISO_NS=1 bash "$0"
fi
base=/opt/aether
root=$base/security-system
stage=$base/build/security-iso
initrd=$base/build/security-initrd
out=${AETHER_ISO_OUTPUT:-$base/images/aether-0.3-x86_64-security-preview.iso}
[[ "$out" == "$base/images/"*.iso ]]
exec 9>"$base/build/native-desktop/build.lock"
flock -n 9 || { echo 'A native build is still running.' >&2; exit 1; }
source=$(findmnt -n -o SOURCE --mountpoint "$root")
[[ "$source" == /dev/nbd2p3 ]]
test -f "$base/build/aether-security.qcow2"
test -x "$root/usr/bin/plasmashell"
test -e "$root/etc/systemd/system/default.target"
test -d /usr/lib/grub
for program in mksquashfs xorriso mformat cpio gzip; do command -v "$program" >/dev/null; done
test ! -e "$out"
test ! -e "$out.partial"
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
release=$(cat "$base/build/security-kernel-stage/kernel-release")
install -m644 "$root/boot/vmlinuz-$release" "$stage/boot/vmlinuz"
printf '0.3\n' >"$stage/live/aether-release"
mksquashfs "$root" "$stage/live/rootfs.squashfs" -noappend -comp xz -processors "$(nproc)" -one-file-system -wildcards -e 'dev/*' 'proc/*' 'sys/*' 'run/*' 'tmp/*' 'build/*' 'sources/*' 'recipes/*'
cat >"$stage/boot/grub/grub.cfg" <<'EOF'
set default=0
set timeout=5
serial --unit=0 --speed=115200
terminal_input console serial
terminal_output console serial
menuentry 'Try Aether Linux 0.3 Desktop' {
 linux /boot/vmlinuz console=tty0 console=ttyS0,115200n8 quiet loglevel=3
 initrd /boot/initrd.img
}
menuentry 'Aether live boot diagnostics' {
 linux /boot/vmlinuz console=tty0 console=ttyS0,115200n8 systemd.show_status=yes
 initrd /boot/initrd.img
}
if [ "$grub_platform" = efi ]; then
 menuentry 'UEFI firmware settings' { fwsetup }
fi
EOF
# Only this private mount namespace sees the native GRUB modules at their prefix.
# Host image-assembly tools do not become part of the installed operating system.
mount --bind "$root/usr/lib/grub" /usr/lib/grub
mount -o remount,bind,ro /usr/lib/grub
"$root/usr/bin/grub-mkrescue" --fonts= --themes= --locales= -o "$out.partial" "$stage" -volid AETHER_0_3
mv "$out.partial" "$out"
sha256sum "$out"
echo 'Live ISO assembled; BIOS and UEFI desktop boot verification is required before release.'
