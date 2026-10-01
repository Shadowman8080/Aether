#!/bin/bash
# Run as root. Mount namespace guarantees chroot helper mounts cannot leak.
set -euo pipefail
if [ "${AETHER_MOUNT_NS:-}" != 1 ]; then
  exec unshare --mount --propagation private env AETHER_MOUNT_NS=1 bash "$0"
fi
root=/opt/aether/system
image=/opt/aether/build/aether-system.raw
source=$(findmnt -n -o SOURCE --mountpoint "$root")
[[ "$source" == /dev/loop*p3 ]]
loop=${source%p3}
[[ "$(readlink -f "$(losetup -n -O BACK-FILE "$loop")")" == "$image" ]]
grep -qx 'EXIT 0' /opt/aether/logs/next/persistent-kernel.status
cp -a /opt/aether/build/kernel-stage/boot/. "$root/boot/"
cp -a /opt/aether/build/kernel-stage/lib/modules/. "$root/usr/lib/modules/"
mount --rbind /dev "$root/dev"
mount --make-rslave "$root/dev"
mount -t proc proc "$root/proc"
mount -t sysfs sysfs "$root/sys"
mount -t tmpfs tmpfs "$root/run"
release=$(cat /opt/aether/logs/next/kernel.release)
chroot "$root" /usr/sbin/depmod "$release"
rootuuid=$(blkid -s UUID -o value "$source")
partuuid=$(blkid -s PARTUUID -o value "$source")
chroot "$root" /usr/sbin/grub-install --target=i386-pc --recheck "$loop"
chroot "$root" /usr/sbin/grub-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=Aether --removable --no-nvram
cat > "$root/boot/grub/grub.cfg" <<EOF
set default=0
set timeout=3
serial --unit=0 --speed=115200
terminal_input console serial
terminal_output console serial
insmod part_gpt
insmod ext2
search --no-floppy --fs-uuid --set=root $rootuuid
menuentry 'Aether Linux 0.2 - persistent console' {
  linux /boot/vmlinuz-$release root=PARTUUID=$partuuid rootwait rw console=tty0 console=ttyS0,115200n8 quiet loglevel=3
}
menuentry 'Aether Linux 0.2 - boot diagnostics' {
  linux /boot/vmlinuz-$release root=PARTUUID=$partuuid rootwait rw console=tty0 console=ttyS0,115200n8 systemd.show_status=yes
}
EOF
chroot "$root" /usr/bin/grub-script-check /boot/grub/grub.cfg
chroot "$root" /usr/bin/systemd-tmpfiles --create --boot
sync
echo 'Installed source-built kernel and BIOS/UEFI GRUB onto the verified Aether image.'
