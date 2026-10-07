#!/bin/bash
set -euo pipefail
b=/opt/aether/build/next-20261007
test -f "$b/foundation-packages.json"
test -f "$b/experience-package.json"
test ! -e "$b/aether-next-20261007-test.iso"
mkdir -p "$b/iso-stage"
rsync -a --exclude=rootfs.squashfs /opt/aether/build/release-20261006/stage/ "$b/iso-stage/"
# This is an internal candidate, not a completed release of the twelve-item scope.
python3 - "$b/root/etc/os-release" <<'PY'
from pathlib import Path
import re,sys
p=Path(sys.argv[1]);text=p.read_text();text=re.sub(r'^BUILD_ID=.*$', 'BUILD_ID="20261007.candidate"',text,flags=re.M);p.write_text(text)
PY
mksquashfs "$b/root" "$b/iso-stage/live/rootfs.squashfs" -noappend -comp xz -processors "$(nproc)" -wildcards -e 'dev/*' 'proc/*' 'sys/*' 'run/*' 'tmp/*' 'modern-tests' 'lost+found'
unsquashfs -cat "$b/iso-stage/live/rootfs.squashfs" etc/os-release | grep -qx 'BUILD_ID="20261007.candidate"'
grub-mkrescue --fonts= --themes= --locales= -o "$b/aether-next-20261007-test.iso.partial" "$b/iso-stage" -volid AETHER_NEXT_TEST
mv "$b/aether-next-20261007-test.iso.partial" "$b/aether-next-20261007-test.iso"
sha256sum "$b/aether-next-20261007-test.iso" > "$b/candidate-iso.sha256"
