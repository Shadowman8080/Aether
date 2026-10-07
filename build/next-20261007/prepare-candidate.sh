#!/bin/bash
set -euo pipefail
b=/opt/aether/build/next-20261007
test -f /opt/aether/build/modern-20261006/root/etc/os-release
mkdir -p "$b"/{root,upper,work}
if ! mountpoint -q "$b/root"; then
 mount -t overlay overlay -o "lowerdir=/opt/aether/build/modern-20261006/upper:/opt/aether/build/release-20261006/upper:/opt/aether/build/release-20261006/lower,upperdir=$b/upper,workdir=$b/work" "$b/root"
fi
grep -qx 'ID=aether' "$b/root/etc/os-release"
python3 "$b/project/build/next-20261007/package-foundation.py"
