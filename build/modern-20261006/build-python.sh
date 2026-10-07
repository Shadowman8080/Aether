#!/bin/bash
set -euo pipefail
if [ "${AETHER_MODERN_PY_NS:-}" != 1 ]; then exec unshare --mount --propagation private env AETHER_MODERN_PY_NS=1 bash "$0"; fi
root=/opt/aether/build/apt-root
mount --rbind /dev "$root/dev"; mount --make-rslave "$root/dev"
mount -t proc proc "$root/proc"; mount -t sysfs sysfs "$root/sys"
mount -t tmpfs tmpfs "$root/run"
mount --bind /opt/aether/build/modern-20261006 "$root/modern"
cp /etc/resolv.conf "$root/etc/resolv.conf"
chroot "$root" /usr/bin/env PATH=/opt/rust/bin:/usr/bin:/usr/sbin CARGO_BUILD_JOBS="$(nproc)" MAKEFLAGS="-j$(nproc)" CARGO_HOME=/modern/cargo /usr/bin/python3 -m pip install --no-binary=:all: --target /modern/python --report /modern/python-build-report.json tuf==7.0.1 'securesystemslib[crypto]==1.4.0' cryptography==50.0.1 urllib3==2.8.0
