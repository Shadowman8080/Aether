#!/bin/bash
set -euo pipefail
cd /opt/aether
mkdir -p sources host-tools
if [ -x /usr/bin/gnuinstall ]; then ln -sf /usr/bin/gnuinstall host-tools/install; fi
cd sources
archive=buildroot-2026.08.tar.xz
if [ ! -f "$archive" ]; then
    curl -fL --retry 3 --connect-timeout 15 -o "$archive" "https://buildroot.org/downloads/$archive"
fi
echo '87aaca4164ea9d5c8085854953018263f7963f07c22e73a2a2185cc98c581c34  buildroot-2026.08.tar.xz' | sha256sum -c -
if [ ! -d buildroot-2026.08 ]; then tar -xf "$archive"; fi
