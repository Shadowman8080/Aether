#!/bin/bash
# Build the single x86_64 live ISO: the full desktop image from
# aether-0.3-x86_64-local-ai.iso (Plasma + Nimbrel AI + Vector) with the
# package-manager chain (dpkg/apt -> AppStream/PackageKit -> plasma-discover)
# overlaid from the apt-root chroot.
#
# Why a union instead of a rebuild: the vector/nimbrel/local-ai build trees no
# longer exist, only their finished ISOs. local-ai is the most complete base
# (it is already desktop + AI); the only files apt-root has that it lacks are
# the package-manager chain, so we unsquash local-ai, add exactly the
# apt-root-only files (build/privacy junk filtered), and rebuild.
#
# The one non-obvious trap: regenerate the loader cache with the IMAGE's own
# ldconfig, not the host's `ldconfig -r`. The host omits the LFS /usr/lib64
# search path, so apt-get cannot find libapt-private.so.0.0 and fails.
#
# Output: $BASE/images/aether-0.3-x86_64-unified.iso
# Result on the 0.3 tree: 1,987,491,840 bytes (under GitHub's 2 GiB asset cap),
# 221,632 entries, 422 packages, boots BIOS and UEFI under -cpu qemu64.
set -euo pipefail

BASE=/opt/aether
ROOT=$BASE/build/apt-root
SRCISO=$BASE/images/aether-0.3-x86_64-local-ai.iso
STAGE=$BASE/build/unified-ai-stage
AIROOT=$BASE/build/unified-ai-root
OUT=$BASE/images/aether-0.3-x86_64-unified.iso
LOG=$BASE/logs/apt/130-unified-ai-iso.log
LIST=/tmp/aptroot-only.txt

exec >"$LOG" 2>&1
echo "=== unified (desktop + AI + package manager) x86_64 ISO ==="
echo "START $(date -u +%FT%TZ)"

test -x "$ROOT/usr/bin/plasma-discover" || { echo "missing plasma-discover in apt-root"; exit 1; }
test -f "$ROOT/var/lib/dpkg/status"     || { echo "missing synthetic dpkg status"; exit 1; }
test -f "$SRCISO"                        || { echo "missing local-ai ISO"; exit 1; }

# Free room: the 2 GiB chroot swapfile never ships, and the previous
# package-manager build stage is no longer needed (that ISO is already built).
rm -f "$ROOT/swapfile"
rm -rf "$BASE/build/unified-iso"
df -h / | sed 's/^/  /'

# Extract the local-ai ISO: its GRUB/EFI boot machinery and its rootfs.
rm -rf "$STAGE" "$AIROOT"
mkdir -p "$STAGE"
echo "--- extracting $SRCISO ---"
xorriso -osirrox on -indev "$SRCISO" -extract / "$STAGE" 2>/dev/null
test -f "$STAGE/boot/vmlinuz"
test -f "$STAGE/boot/initrd.img"
test -f "$STAGE/boot/grub/grub.cfg"
test -f "$STAGE/live/aether-release"
printf 'aether-release: '; cat "$STAGE/live/aether-release"; echo

echo "--- unsquashing local-ai rootfs ---"
unsquashfs -d "$AIROOT" "$STAGE/live/rootfs.squashfs" >/tmp/unsq.log 2>&1
tail -2 /tmp/unsq.log | sed 's/^/  /'

# The additions are exactly the files apt-root has that local-ai lacks.
echo "--- computing the apt-root-only additions ---"
( cd "$ROOT" && find . -xdev \
    \( -path ./dev -o -path ./proc -o -path ./sys -o -path ./run -o -path ./tmp \
       -o -path ./swapfile -o -path ./src -o -path ./build -o -path ./sources \
       -o -path ./recipes -o -path ./lost+found \) -prune -o -printf '%P\n' ) \
  | LC_ALL=C sort > /tmp/ar-list.txt
unsquashfs -l "$STAGE/live/rootfs.squashfs" 2>/dev/null \
  | sed -n 's#^squashfs-root/##p; s#^squashfs-root$##p' \
  | LC_ALL=C sort > /tmp/lai-norm.txt
comm -23 /tmp/ar-list.txt /tmp/lai-norm.txt > "$LIST"
echo "  apt-root entries: $(wc -l < /tmp/ar-list.txt)  local-ai entries: $(wc -l < /tmp/lai-norm.txt)  additions: $(wc -l < "$LIST")"

rm -f "$STAGE/live/rootfs.squashfs"
df -h / | sed 's/^/  /'

# Overlay the chain. Keep every apt-root-only file except caches, dev headers
# and anything that could carry operator secrets (root/.*).
echo "--- overlaying package-manager chain ---"
grep -vE '^(root/|var/cache/|var/log/|usr/include/|usr/cmake/|etc/systemd/)' "$LIST" \
  | grep -v '^$' > /tmp/add.txt
echo "  additions to copy: $(wc -l < /tmp/add.txt)"
# -a minus -r: copy exactly the listed entries, no recursive expansion.
rsync -lptgoDHAX --dirs --numeric-ids --ignore-existing \
  --files-from=/tmp/add.txt "$ROOT/" "$AIROOT/"
echo "  copied"
if [ -e "$AIROOT/root/.ssh" ] || [ -e "$AIROOT/root/.gnupg" ]; then
  echo "  WARNING: operator secret dirs present under AIROOT/root"; exit 1
fi

# Chroot sanity check (same arch, the image's own glibc).
echo "--- chroot sanity (chain + AI both present) ---"
for d in dev proc sys; do mount --bind "/$d" "$AIROOT/$d" 2>/dev/null || true; done
# Regenerate the loader cache with the IMAGE's own ldconfig. See the header.
echo "--- ldconfig (image) ---"
chroot "$AIROOT" /sbin/ldconfig && echo "  cache regenerated" \
  || { echo "  ldconfig failed"; exit 1; }
chroot "$AIROOT" /usr/bin/apt-get --version 2>&1 | head -1 | sed 's/^/  apt-get:   /' || true
printf '  dpkg ii:   '; chroot "$AIROOT" /usr/bin/dpkg -l 2>/dev/null | grep -c '^ii'
chroot "$AIROOT" /usr/bin/plasma-discover --version 2>&1 | head -1 | sed 's/^/  discover:  /' || true
chroot "$AIROOT" /usr/bin/plasmashell --version 2>&1 | head -1 | sed 's/^/  plasmashell: /' || true
chroot "$AIROOT" /usr/bin/nimbrel --help 2>&1 | head -1 | sed 's/^/  nimbrel:   /' || true
for d in dev proc sys; do umount "$AIROOT/$d" 2>/dev/null || true; done

# Rebuild the rootfs.
echo "--- building merged rootfs.squashfs ---"
time mksquashfs "$AIROOT" "$STAGE/live/rootfs.squashfs" \
  -noappend -comp xz -processors "$(nproc)" -one-file-system -wildcards \
  -e 'dev/*' 'proc/*' 'sys/*' 'run/*' 'tmp/*' 'lost+found'
ls -l "$STAGE/live/rootfs.squashfs"

# Assemble the ISO.
echo "--- assembling ISO ---"
rm -f "$OUT" "$OUT.partial"
grub-mkrescue --fonts= --themes= --locales= -o "$OUT.partial" "$STAGE" -volid AETHER_0_3
mv "$OUT.partial" "$OUT"
echo "sha256:"; sha256sum "$OUT"
ls -l "$OUT"
echo "free space:"; df -h / | tail -1 | sed 's/^/  /'
echo "DONE $(date -u +%FT%TZ)"
