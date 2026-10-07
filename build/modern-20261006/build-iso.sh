#!/bin/bash
set -euo pipefail
b=/opt/aether/build/modern-20261006
mkdir -p "$b/iso-stage"
rsync -a --exclude=rootfs.squashfs /opt/aether/build/release-20261006/stage/ "$b/iso-stage/"
python3 - "$b/root/etc/os-release" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text().replace('BUILD_ID="20261006.1"','BUILD_ID="20261006.2"');p.write_text(s)
PY
# Never include the validation workspace or disposable signing keys.
mksquashfs "$b/root" "$b/iso-stage/live/rootfs.squashfs" -noappend -comp xz -processors "$(nproc)" -wildcards -e 'dev/*' 'proc/*' 'sys/*' 'run/*' 'tmp/*' 'modern-tests' 'lost+found'
unsquashfs -cat "$b/iso-stage/live/rootfs.squashfs" etc/os-release | grep -q 'BUILD_ID="20261006.2"'
grub-mkrescue --fonts= --themes= --locales= -o "$b/aether-0.3.2-dev-20261006-x86_64.iso.partial" "$b/iso-stage" -volid AETHER_0_3_2
mv "$b/aether-0.3.2-dev-20261006-x86_64.iso.partial" "$b/aether-0.3.2-dev-20261006-x86_64.iso"
sha256sum "$b/aether-0.3.2-dev-20261006-x86_64.iso" > "$b/iso.sha256"
