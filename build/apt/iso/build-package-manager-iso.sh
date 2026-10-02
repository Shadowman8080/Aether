#!/bin/bash
# Rebuild the x86_64 live ISO from the apt-root chroot.
#
# apt-root is the Aether desktop rootfs (plasmashell, Plasma Discover) plus the
# package-manager chain built in it. The existing desktop ISO already contains
# the GRUB/EFI boot machinery and an initrd whose live-init locates
# /live/rootfs.squashfs and /live/aether-release == "0.3"; so we extract that
# ISO, replace rootfs.squashfs with one built from apt-root, and reassemble.
#
# Excluded from the squashfs: the mounted pseudo-filesystems, build scratch
# (src/, tmp/) and the 2 GiB rootfs /swapfile which must never ship.
#
# Output: $BASE/images/aether-0.3-x86_64.iso
# Result on the 0.3 tree: 1,358,888,960 bytes, 422 packages, no proof stubs.
set -euo pipefail

BASE=/opt/aether
ROOT=$BASE/build/apt-root
OLD=$BASE/images/aether-0.3-x86_64-desktop.iso
STAGE=$BASE/build/unified-iso
OUT=$BASE/images/aether-0.3-x86_64.iso
LOG=$BASE/logs/apt/120-unified-iso.log

exec >"$LOG" 2>&1
echo "=== x86_64 ISO with the package manager ==="
echo "START $(date -u +%FT%TZ)"

test -x "$ROOT/usr/bin/plasmashell"      || { echo "missing plasmashell"; exit 1; }
test -x "$ROOT/usr/bin/plasma-discover"  || { echo "missing plasma-discover"; exit 1; }
test -f "$ROOT/var/lib/dpkg/status"      || { echo "missing synthetic dpkg status"; exit 1; }
test -f "$OLD"                           || { echo "missing source desktop ISO"; exit 1; }

df -h / | sed 's/^/  /'
echo "apt-root size: $(du -sh "$ROOT" | cut -f1)"

echo
echo "--- preparing stage from $OLD ---"
rm -rf "$STAGE"
mkdir -p "$STAGE"
xorriso -osirrox on -indev "$OLD" -extract / "$STAGE" 2>/dev/null
test -f "$STAGE/boot/vmlinuz"
test -f "$STAGE/boot/initrd.img"
test -f "$STAGE/boot/grub/grub.cfg"
test -f "$STAGE/live/aether-release"
cat "$STAGE/live/aether-release"
# drop the old rootfs so two copies never coexist on disk
rm -f "$STAGE/live/rootfs.squashfs"
echo "stage ready; free space:"
df -h / | sed 's/^/  /'

echo
echo "--- building rootfs.squashfs from apt-root ---"
time mksquashfs "$ROOT" "$STAGE/live/rootfs.squashfs" \
  -noappend -comp xz -processors "$(nproc)" -one-file-system -wildcards \
  -e 'dev/*' 'proc/*' 'sys/*' 'run/*' 'tmp/*' \
     'swapfile' 'src/*' 'build/*' 'sources/*' 'recipes/*' 'lost+found'
ls -l "$STAGE/live/rootfs.squashfs"

echo
echo "--- assembling ISO ---"
rm -f "$OUT" "$OUT.partial"
grub-mkrescue --fonts= --themes= --locales= -o "$OUT.partial" "$STAGE" -volid AETHER_0_3
mv "$OUT.partial" "$OUT"
echo "sha256:"
sha256sum "$OUT"
ls -l "$OUT"
echo "DONE $(date -u +%FT%TZ)"
