#!/bin/bash
set -euo pipefail
if [ "${AETHER_BOOT_NS:-}" != 1 ]; then
 exec unshare --mount --propagation private env AETHER_BOOT_NS=1 bash "$0"
fi
root=/opt/aether/guest-system
source=$(findmnt -n -o SOURCE --mountpoint "$root")
[[ "$source" == /dev/loop*p3 ]]
loop=${source%p3}
[[ "$(losetup -n -O BACK-FILE "$loop")" == /opt/aether/build/aether-0.2.1-system.raw ]]
grep -qx 'EXIT 0' /opt/aether/logs/next/guest-kernel.status
test -f /opt/aether/build/native-guest/done/open-vm-tools
test -f /opt/aether/build/native-guest/done/virtualbox-additions
test -x "$root/usr/bin/aether-guest-panel"
cp -a /opt/aether/build/guest-kernel-stage/boot/. "$root/boot/"
cp -a /opt/aether/build/guest-kernel-stage/lib/modules/. "$root/usr/lib/modules/"
mount --rbind /dev "$root/dev"
mount --make-rslave "$root/dev"
mount -t proc proc "$root/proc"
mount -t sysfs sysfs "$root/sys"
mount -t tmpfs tmpfs "$root/run"
release=6.18.54-aether
chroot "$root" depmod "$release"
chroot "$root" grub-install --target=i386-pc --recheck "$loop"
chroot "$root" grub-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=Aether --no-nvram
chroot "$root" grub-install --target=x86_64-efi --efi-directory=/boot/efi --removable --no-nvram
uuid=$(blkid -s UUID -o value "$source")
partuuid=$(blkid -s PARTUUID -o value "$source")
cat >"$root/boot/grub/grub.cfg" <<EOF
set default=0
set timeout=3
serial --unit=0 --speed=115200
terminal_input console serial
terminal_output console serial
insmod part_gpt
insmod ext2
search --no-floppy --fs-uuid --set=root $uuid
menuentry 'Aether Linux 0.2.1 - guest integration' {
 linux /boot/vmlinuz-$release root=PARTUUID=$partuuid rootwait rw console=tty0 console=ttyS0,115200n8 quiet loglevel=3
}
menuentry 'Aether Linux 0.2.1 - boot diagnostics' {
 linux /boot/vmlinuz-$release root=PARTUUID=$partuuid rootwait rw console=tty0 console=ttyS0,115200n8 systemd.show_status=yes
}
if [ "\$grub_platform" = efi ]; then
 menuentry 'UEFI firmware settings' { fwsetup }
fi
EOF
chroot "$root" grub-script-check /boot/grub/grub.cfg
truncate -s0 "$root/etc/machine-id"
rm -f "$root/var/lib/systemd/random-seed" "$root/var/lib/dbus/machine-id"
for file in shadow- gshadow- passwd- group-; do rm -f "$root/etc/$file"; done
sync
echo 'Installed BIOS and UEFI loaders; EFI-only firmware menu is guarded.'
