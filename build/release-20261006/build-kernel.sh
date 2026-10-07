#!/bin/bash
# Rebuild the release aether4 kernel with in-kernel VMware vmmouse.
#
# The build-tree .config already equals the released 6.18.54-aether4 config
# (verified byte-for-byte), so enabling CONFIG_MOUSE_PS2_VMMOUSE is the only
# change. CONFIG_MOUSE_PS2=y, so vmmouse is built into vmlinuz and no module
# or initramfs needs to change.
set -euo pipefail

src=/opt/aether/sources/linux-6.18.54
out=/opt/aether/build/kernel-6.18.54
stage=/opt/aether/build/vmmouse-kernel-stage
log=/opt/aether/logs/next/vmmouse-kernel.log
status=/opt/aether/logs/next/vmmouse-kernel.status

mkdir -p "$stage/boot" /opt/aether/logs/next
exec >"$log" 2>&1
date -u '+STARTED %FT%TZ' >"$status"
trap 'r=$?; echo "EXIT $r" >>"$status"' EXIT

echo "=== Aether VMMOUSE kernel build  $(date -u +%FT%TZ) ==="

# Make sure we are building the exact released config, not a stale one.
if ! diff -q /opt/aether/build/kernel-release-aether4.config "$out/.config" >/dev/null 2>&1; then
  echo "NOTE: restoring released aether4 config (tree .config had drifted)"
  cp /opt/aether/build/kernel-release-aether4.config "$out/.config"
fi
cp "$out/.config" "$stage/config-before"

"$src/scripts/config" --file "$out/.config" --enable MOUSE_PS2_VMMOUSE
make -C "$src" O="$out" olddefconfig

grep -qx 'CONFIG_MOUSE_PS2_VMMOUSE=y' "$out/.config" || { echo "VMMOUSE not enabled"; exit 1; }
grep -qx 'CONFIG_MOUSE_PS2=y'         "$out/.config" || { echo "MOUSE_PS2 not builtin"; exit 1; }
grep -qx 'CONFIG_LOCALVERSION="-aether4"' "$out/.config" || { echo "unexpected localversion"; exit 1; }

echo "--- building bzImage (only psmouse/vmmouse and the vmlinux link change) ---"
make -C "$src" O="$out" -j"$(nproc)" bzImage

release=$(make -s -C "$src" O="$out" kernelrelease)
test "$release" = 6.18.54-aether4 || { echo "unexpected release: $release"; exit 1; }

install -m644 "$out/arch/x86/boot/bzImage" "$stage/boot/vmlinuz-$release"
install -m644 "$out/.config"               "$stage/boot/config-$release"
install -m644 "$out/System.map"            "$stage/boot/System.map-$release"
printf '%s\n' "$release" >"$stage/kernel-release"

echo "--- proof: vmmouse linked into vmlinux ---"
nm "$out/vmlinux" | grep -i vmmouse | head -10 || { echo "no vmmouse symbols"; exit 1; }
sha256sum "$stage/boot/vmlinuz-$release" | tee "$stage/vmlinuz.sha256"
echo "AETHER_VMMOUSE_KERNEL_BUILD_PASS"
echo "DONE $(date -u +%FT%TZ)"
