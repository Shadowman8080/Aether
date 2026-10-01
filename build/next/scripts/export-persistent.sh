#!/bin/bash
set -euo pipefail
cd /opt/aether
exec >logs/next/persistent-export.log 2>&1
date -u '+STARTED %FT%TZ' >logs/next/persistent-export.status
trap 'echo "EXIT $?" >>/opt/aether/logs/next/persistent-export.status' EXIT
image=/opt/aether/build/aether-system.raw
test -z "$(losetup -j "$image")"
grep -q '^PASS: bios ' logs/next/persistent-bios.log
grep -q '^PASS: uefi ' logs/next/persistent-uefi.log
grep -q '^PASS: sata ' logs/next/persistent-sata.log
mkdir -p images
out=/opt/aether/images/aether-0.2-x86_64.vmdk
test ! -e "$out"
qemu-img convert -p -m 16 -f raw -O vmdk -o subformat=monolithicSparse,adapter_type=lsilogic "$image" "$out.partial"
qemu-img check -f vmdk "$out.partial"
qemu-img compare -f raw -F vmdk "$image" "$out.partial"
mv "$out.partial" "$out"
sha256sum "$out" > images/aether-0.2-x86_64.vmdk.sha256
ls -lh "$out"
