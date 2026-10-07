#!/bin/bash
set -euo pipefail
b=/opt/aether/build/release-20261006
exec >"$b/build-iso.log" 2>&1
trap 'echo EXIT:$?' EXIT
chown -R 1000:1000 "$b/root/home/aether/.config"
chroot "$b/root" /bin/sh -n /usr/libexec/aether-guest-display-setup
if chroot "$b/root" /usr/bin/ldd /usr/bin/vector | grep -q 'not found'; then exit 1; fi
mksquashfs "$b/root" "$b/stage/live/rootfs.squashfs" -noappend -comp xz -processors "$(nproc)" -wildcards -e 'dev/*' 'proc/*' 'sys/*' 'run/*' 'tmp/*' 'lost+found'
test "$(stat -c %s "$b/stage/live/rootfs.squashfs")" -gt 1000000000
unsquashfs -cat "$b/stage/live/rootfs.squashfs" etc/os-release | grep -q 'BUILD_ID="20261006.1"'
grub-mkrescue --fonts= --themes= --locales= -o "$b/aether-0.3.1-dev-20261006-x86_64.iso.partial" "$b/stage" -volid AETHER_0_3_1
mv "$b/aether-0.3.1-dev-20261006-x86_64.iso.partial" "$b/aether-0.3.1-dev-20261006-x86_64.iso"
sha256sum "$b/aether-0.3.1-dev-20261006-x86_64.iso" > "$b/iso.sha256"
stat -c '%s' "$b/aether-0.3.1-dev-20261006-x86_64.iso"
