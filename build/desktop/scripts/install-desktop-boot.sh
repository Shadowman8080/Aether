#!/bin/bash
set -euo pipefail
if [ "${AETHER_DESKTOP_BOOT_NS:-}" != 1 ]; then
 exec unshare --mount --propagation private env AETHER_DESKTOP_BOOT_NS=1 bash "$0"
fi
base=/opt/aether
root=$base/desktop-system
source=$(findmnt -n -o SOURCE --mountpoint "$root")
[[ "$source" == /dev/loop*p3 ]]
loop=${source%p3}
[[ "$(losetup -n -O BACK-FILE "$loop")" == "$base/build/aether-0.3-system.raw" ]]
grep -qx 'EXIT 0' "$base/logs/desktop/kernel.status"
for program in plasmashell krunner startplasma-wayland sddm dolphin konsole; do
 test -x "$root/usr/bin/$program"
done
stage=$base/build/desktop-kernel-stage
release=$(cat "$stage/kernel-release")
[[ "$release" == 6.18.54-aether3 ]]
cp -a "$stage/boot/." "$root/boot/"
cp -a "$stage/lib/modules/." "$root/usr/lib/modules/"
mount --rbind /dev "$root/dev"
mount --make-rslave "$root/dev"
mount -t proc proc "$root/proc"
mount -t sysfs sysfs "$root/sys"
mount -t tmpfs tmpfs "$root/run"
mount --bind "$base/desktop" "$root/recipes"
mount -o remount,bind,ro "$root/recipes"
chroot "$root" /usr/bin/env SYSTEMD_OFFLINE=1 python3 /recipes/scripts/configure-desktop-session.py
bash "$base/desktop/scripts/install-assets.sh" "$root"
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
menuentry 'Aether Linux 0.3 - desktop' {
 linux /boot/vmlinuz-$release root=PARTUUID=$partuuid rootwait rw console=tty0 console=ttyS0,115200n8 quiet loglevel=3
}
menuentry 'Aether Linux 0.3 - console recovery' {
 linux /boot/vmlinuz-$release root=PARTUUID=$partuuid rootwait rw console=tty0 console=ttyS0,115200n8 systemd.unit=multi-user.target
}
if [ "\$grub_platform" = efi ]; then
 menuentry 'UEFI firmware settings' { fwsetup }
fi
EOF
cat >"$root/etc/os-release" <<'EOF'
NAME="Aether Linux"
PRETTY_NAME="Aether Linux 0.3 Desktop Development"
ID=aether
VERSION="0.3"
VERSION_ID="0.3"
LOGO=aether-logo
EOF
printf 'Aether Linux 0.3 Desktop Development\n' >"$root/etc/issue"
chroot "$root" grub-script-check /boot/grub/grub.cfg
chroot "$root" ldconfig
truncate -s0 "$root/etc/machine-id"
rm -f "$root/var/lib/systemd/random-seed" "$root/var/lib/dbus/machine-id"
sync
echo 'Desktop startup and BIOS/UEFI boot loaders installed. Boot tests are still required.'
