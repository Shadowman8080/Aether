#!/bin/bash
# Exercise the real installer backend against a disposable 20 GiB disk image.
# The built desktop root plays the live root, so partitioning, copying, account
# setup, bootloader installation and unmounting all run exactly as on the ISO.
# AETHER_TEST_ENCRYPT=1 AETHER_TEST_UEFI=1 exercises LUKS2 plus LVM and writes
# root-only credentials for test-encrypted-boot.py.
set -euo pipefail
if [ "${AETHER_INSTALLER_TEST_NS:-}" != 1 ]; then
    exec unshare --mount --propagation private env AETHER_INSTALLER_TEST_NS=1 bash "$0"
fi
base=/opt/aether
root=${AETHER_TEST_ROOT:-$base/desktop-system}
work=${AETHER_TEST_WORK:-$base/build/installer-test}
disk_image=${AETHER_TEST_DISK:-$work/disk.raw}
log=$base/logs/desktop/installer-backend.log
uefi=${AETHER_TEST_UEFI:-0}
encrypt=${AETHER_TEST_ENCRYPT:-0}
exec >"$log" 2>&1
mkdir -p "$work"
[ -s "$disk_image" ] || truncate -s 20G "$disk_image"
test -x "$root/usr/libexec/aether-installer-backend" || { echo 'backend missing from image'; exit 1; }
disk=$(losetup --find --show --partscan "$disk_image")
echo "scratch disk: $disk"
cleanup() {
    umount -R "$root/mnt/aether-install" 2>/dev/null || true
    umount "$root/run/initramfs/live/lower" 2>/dev/null || true
    umount "$root/sys/firmware" 2>/dev/null || true
    umount "$root/dev" 2>/dev/null || true
    umount "$root/proc" 2>/dev/null || true
    umount "$root/sys" 2>/dev/null || true
    losetup -d "$disk" 2>/dev/null || true
}
trap cleanup EXIT
mkdir -p "$root/run/initramfs/live/lower" "$root/mnt/aether-install"
mountpoint -q "$root/run/initramfs/live/lower" || mount --bind "$root" "$root/run/initramfs/live/lower"
mountpoint -q "$root/dev" || mount --bind /dev "$root/dev"
mountpoint -q "$root/proc" || mount -t proc proc "$root/proc"
mountpoint -q "$root/sys" || mount -t sysfs sysfs "$root/sys"
if [ "$uefi" = 1 ]; then
    mountpoint -q "$root/sys/firmware" || mount -t tmpfs tmpfs "$root/sys/firmware"
    mkdir -p "$root/sys/firmware/efi/efivars"
    guid=8be4df61-93ca-11d2-aa0d-00e098032b8c
    printf '\006\000\000\000\001' >"$root/sys/firmware/efi/efivars/SecureBoot-$guid"
    printf '\006\000\000\000\000' >"$root/sys/firmware/efi/efivars/SetupMode-$guid"
    openssl x509 -in "$root/usr/share/aether/secureboot/db.crt" -outform DER -out "$work/db.der"
    { printf '\006\000\000\000'; cat "$work/db.der"; } >"$root/sys/firmware/efi/efivars/db-$guid"
fi
storage=''
recovery=''
if [ "$encrypt" = 1 ]; then
    [ "$uefi" = 1 ] || { echo 'encrypted backend tests require AETHER_TEST_UEFI=1'; exit 1; }
    [ -x "$root/usr/sbin/cryptsetup" ] && [ -x "$root/usr/sbin/lvm" ] || {
        echo 'encrypted backend tests require the source-built crypto runtime in the root'; exit 1;
    }
    storage=${AETHER_TEST_STORAGE_PASSPHRASE:-$(openssl rand -hex 16)}
    recovery=${AETHER_TEST_RECOVERY_PASSPHRASE:-$(openssl rand -hex 16)}
    credentials=$work/encrypted-credentials.json
    (umask 077; printf '{"storage":"%s","recovery":"%s"}\n' "$storage" "$recovery" >"$credentials")
    chmod 600 "$credentials"
    echo "encrypted credentials: $credentials (root-only)"
    json=$(printf '{"disk":"%s","username":"aether","password":"AetherTest12345","encrypt":true,"lvm":true,"storage_password":"%s","recovery_password":"%s","backup":"","confirmation":"ERASE %s","timezone":"UTC","keyboard":"us","language":"en_US.UTF-8"}' "$disk" "$storage" "$recovery" "$disk")
else
    json=$(printf '{"disk":"%s","username":"aether","password":"AetherTest12345","encrypt":false,"storage_password":"","recovery_password":"","backup":"","confirmation":"ERASE %s","timezone":"UTC","keyboard":"us","language":"en_US.UTF-8"}' "$disk" "$disk")
fi
printf '%s' "$json" | chroot "$root" /usr/libexec/aether-installer-backend --graphical
echo 'backend completed without error'
blkid "${disk}p2" "${disk}p3" "${disk}p4"
if [ "$encrypt" = 1 ]; then
    mountpoint -q "$root/dev" || mount --bind /dev "$root/dev"
    chroot "$root" /usr/sbin/cryptsetup isLuks "${disk}p4"
    chroot "$root" /usr/sbin/cryptsetup luksDump "${disk}p4" | grep -E 'Version:|Cipher:|Key:'
    printf '%s' "$storage" | chroot "$root" /usr/sbin/cryptsetup open --test-passphrase "${disk}p4"
    printf '%s' "$recovery" | chroot "$root" /usr/sbin/cryptsetup open --test-passphrase "${disk}p4"
    echo 'ENCRYPTED_BACKEND_PASS'
fi
if [ "$uefi" = 1 ]; then
    esp=$work/uefi-check
    mkdir -p "$esp"
    mount "${disk}p2" "$esp"
    for file in EFI/BOOT/BOOTX64.EFI EFI/BOOT/grubx64.efi EFI/aether/aether.efi boot/grub/grub.cfg; do
        test -f "$esp/$file" || { echo "missing signed asset: $file"; exit 1; }
    done
    grep -q 'chainloader /EFI/aether/aether.efi' "$esp/boot/grub/grub.cfg"
    cert=$root/usr/share/aether/secureboot/db.crt
    sbverify --cert "$cert" "$esp/EFI/BOOT/BOOTX64.EFI" >/dev/null
    sbverify --cert "$cert" "$esp/EFI/BOOT/grubx64.efi" >/dev/null
    sbverify --cert "$cert" "$esp/EFI/aether/aether.efi" >/dev/null
    umount "$esp"
    echo 'INSTALLER_UEFI_PASS'
fi
echo 'INSTALLER_BACKEND_PASS'
