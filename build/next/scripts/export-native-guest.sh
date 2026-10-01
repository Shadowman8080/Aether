#!/bin/bash
set -euo pipefail
image=/opt/aether/build/aether-0.2.1-system.raw
out=/opt/aether/images/aether-0.2.1-x86_64.vmdk
test -z "$(losetup -j "$image")"
grep -q '^PASS: uefi' /opt/aether/logs/next/guest-integration-uefi.log
grep -q '^PASS: bios' /opt/aether/logs/next/guest-integration-bios.log
test ! -e "$out"
test ! -e "$out.partial"
qemu-img convert -m "$(nproc)" -f raw -O vmdk -o subformat=monolithicSparse,adapter_type=lsilogic "$image" "$out.partial"
qemu-img check -f vmdk "$out.partial"
qemu-img compare -f raw -F vmdk "$image" "$out.partial"
mv "$out.partial" "$out"
sha256sum "$out"
stat -c 'BYTES %s' "$out"
