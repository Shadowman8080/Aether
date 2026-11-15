#!/bin/bash
# Assemble the native Aether root and source-built GRUB into a live desktop ISO.
set -euo pipefail
if [ "${AETHER_ISO_NS:-}" != 1 ]; then
 exec unshare --mount --propagation private env AETHER_ISO_NS=1 bash "$0"
fi
base=/opt/aether
root=$base/desktop-system
stage=$base/build/desktop-iso
initrd=$base/build/desktop-initrd
out=$base/images/aether-0.3-x86_64-desktop.iso
sbassets=${AETHER_SB_ASSETS:-$base/desktop/assets/usr/share/aether/secureboot}
sbkeys=${AETHER_SB_KEYDIR:-$base/secureboot/keys}
exec 9>"$base/build/native-desktop/build.lock"
flock -n 9 || { echo 'A native build is still running.' >&2; exit 1; }
source=$(findmnt -n -o SOURCE --mountpoint "$root")
[[ "$source" == /dev/loop*p3 ]]
[[ "$(losetup -n -O BACK-FILE "${source%p3}")" == "$base/build/aether-0.3-system.raw" ]]
test -x "$root/usr/bin/plasmashell"
test -x "$root/usr/bin/aether-installer"
test -e "$root/etc/systemd/system/default.target"
test -d /usr/lib/grub
test -f "$sbassets/shimx64.efi"
test -f "$sbassets/grubx64.efi"
test -f "$sbkeys/db.key"
test -f "$sbkeys/db.crt"
for program in mksquashfs xorriso mformat mcopy mmd cpio gzip ukify; do command -v "$program" >/dev/null; done
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
release=$(cat "$base/build/desktop-kernel-stage/kernel-release")
install -m644 "$root/boot/vmlinuz-$release" "$stage/boot/vmlinuz"
ukify build \
  --linux "$stage/boot/vmlinuz" \
  --initrd "$stage/boot/initrd.img" \
  --cmdline 'console=tty0 console=ttyS0,115200n8 quiet loglevel=3 rdinit=/init' \
  --uname "$release" \
  --output "$stage/boot/aether-live.efi" \
  --secureboot-private-key "$sbkeys/db.key" \
  --secureboot-certificate "$sbkeys/db.crt"
printf '0.3\n' >"$stage/live/aether-release"
# Windows-style hardware database: merge hwdata + systemd's udev hwdb files
# into the binary /usr/lib/udev/hwdb.bin so udev can name devices correctly
# in the offline live image. A failure warns instead of aborting the image.
if [ -x "$root/usr/bin/systemd-hwdb" ]; then
	chroot "$root" /usr/bin/systemd-hwdb update \
		|| echo 'WARNING: systemd-hwdb update failed inside the image root; device naming may be incomplete.' >&2
fi
mksquashfs "$root" "$stage/live/rootfs.squashfs" -noappend -comp xz -processors "$(nproc)" -one-file-system -wildcards -e 'dev/*' 'proc/*' 'sys/*' 'run/*' 'tmp/*' 'build/*' 'sources/*' 'recipes/*'
cat >"$stage/boot/grub/grub.cfg" <<'EOF'
set default=0
set timeout=0
serial --unit=0 --speed=115200
terminal_input console serial
terminal_output console serial
# UEFI boots a signed UKI, so firmware verifies shim, GRUB and kernel before
# the desktop starts. BIOS has no Secure Boot layer and boots the kernel and
# initramfs directly. The live account is disposable in both cases.
if [ "$grub_platform" = efi ]; then
menuentry 'Aether Linux 0.3 Desktop' {
 chainloader /boot/aether-live.efi
}
menuentry 'Aether live boot diagnostics' {
 chainloader /boot/aether-live.efi
}
menuentry 'UEFI firmware settings' { fwsetup }
else
menuentry 'Aether Linux 0.3 Desktop' {
 linux /boot/vmlinuz console=tty0 console=ttyS0,115200n8 quiet loglevel=3
 initrd /boot/initrd.img
}
menuentry 'Aether live boot diagnostics' {
 linux /boot/vmlinuz console=tty0 console=ttyS0,115200n8 systemd.show_status=yes
 initrd /boot/initrd.img
}
fi
EOF
# Build a small signed EFI system image for the El Torito UEFI entry. The
# firmware verifies shim, shim verifies GRUB, and GRUB chainloads the signed
# live UKI. The same shim/GRUB are copied to the ISO root for USB writing.
dd if=/dev/zero of="$stage/efi.img" bs=1M count=16 status=none
mformat -i "$stage/efi.img" ::
mmd -i "$stage/efi.img" ::/EFI ::/EFI/BOOT
mcopy -i "$stage/efi.img" "$sbassets/shimx64.efi" ::/EFI/BOOT/BOOTX64.EFI
mcopy -i "$stage/efi.img" "$sbassets/grubx64.efi" ::/EFI/BOOT/grubx64.efi
install -D -m644 "$sbassets/shimx64.efi" "$stage/EFI/BOOT/BOOTX64.EFI"
install -D -m644 "$sbassets/grubx64.efi" "$stage/EFI/BOOT/grubx64.efi"
# BIOS chainloader and modules come from the same GRUB tree as the ISO.
mkdir -p "$stage/boot/grub/i386-pc"
cp -a /usr/lib/grub/i386-pc/. "$stage/boot/grub/i386-pc/"
xorriso -as mkisofs -o "$out.partial" -volid AETHER_0_3 \
  -b boot/grub/i386-pc/eltorito.img -no-emul-boot -boot-load-size 4 \
  -boot-info-table --grub2-boot-info \
  -eltorito-alt-boot -e efi.img -no-emul-boot \
  "$stage"
mv "$out.partial" "$out"
sha256sum "$out"
echo 'Live ISO assembled; BIOS and UEFI desktop boot verification is required before release.'
