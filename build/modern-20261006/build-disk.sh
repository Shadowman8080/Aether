#!/bin/bash
set -euo pipefail
b=/opt/aether/build/modern-20261006
out="$b/aether-0.3.2-dev-20261006-x86_64.vmdk"
root="$b/disk-root"
exec >"$b/build-disk.log" 2>&1
trap 'echo EXIT:$?' EXIT
modprobe nbd max_part=16
test ! -e /sys/block/nbd6/pid
test ! -e "$out"
qemu-img create -f vmdk -o subformat=monolithicSparse,adapter_type=ide,hwversion=22 "$out" 32G
qemu-nbd --cache=writeback --connect=/dev/nbd6 --format=vmdk "$out"
cleanup() {
    for mount in "$root/dev" "$root/proc" "$root/sys" "$root/boot/efi" "$root"; do
        if mountpoint -q "$mount"; then
            umount "$mount" || { echo "Cannot unmount $mount; leaving NBD attached" >&2; return 1; }
        fi
    done
    qemu-nbd --disconnect /dev/nbd6
}
trap cleanup EXIT
parted -s /dev/nbd6 mklabel gpt mkpart BIOS 1MiB 3MiB set 1 bios_grub on mkpart EFI fat32 3MiB 515MiB set 2 esp on mkpart AETHER ext4 515MiB 100%
udevadm settle
mkfs.vfat -F32 -n AETHER_EFI /dev/nbd6p2
mkfs.ext4 -F -L AETHER_ROOT /dev/nbd6p3
mkdir -p "$root"
mount /dev/nbd6p3 "$root"
# Source is the clean release overlay, never the user's personal VM.
rsync -aHAX --numeric-ids --exclude=/dev/ --exclude=/proc/ --exclude=/sys/ --exclude=/run/ --exclude=/tmp/ --exclude=/lost+found/ --exclude=/modern-tests/ "$b/root/" "$root/"
mkdir -p "$root"/{dev,proc,sys,run,tmp,boot/efi}
chmod 1777 "$root/tmp"
mount /dev/nbd6p2 "$root/boot/efi"
uuid=$(blkid -s UUID -o value /dev/nbd6p3)
python3 - "$root/boot/grub/grub.cfg" "$uuid" <<'PY'
from pathlib import Path
import re,sys
p=Path(sys.argv[1]);s=p.read_text()
s=re.sub(r'(--set=root\s+)[a-fA-F0-9-]+',lambda m:m[1]+sys.argv[2],s)
s=re.sub(r'root=UUID=[a-fA-F0-9-]+','root=UUID='+sys.argv[2],s)
p.write_text(s)
PY
mount --bind /dev "$root/dev"
mount -t proc proc "$root/proc"
mount --bind /sys "$root/sys"
chroot "$root" /usr/sbin/grub-install --target=i386-pc --boot-directory=/boot --recheck /dev/nbd6
chroot "$root" /usr/sbin/grub-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=Aether --removable --no-nvram
chroot "$root" /usr/bin/grub-script-check /boot/grub/grub.cfg
sync
cleanup
trap - EXIT
qemu-img check "$out"
sha256sum "$out" > "$b/vmdk.sha256"
echo BUILD_DISK_PASS
