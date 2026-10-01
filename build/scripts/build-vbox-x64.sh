#!/bin/bash
set -euo pipefail
base=/opt/aether
status=$base/logs/vbox-x64.status
printf 'STARTED %s\n' "$(date -u +%FT%TZ)" > "$status"
trap 'rc=$?; printf "EXIT %s\nFINISHED %s\n" "$rc" "$(date -u +%FT%TZ)" >> "$status"' EXIT
cd "$base/sources/VirtualBox-7.2.20"
tc=$base/build/prototype/host/bin/x86_64-aether-linux-gnu
mkdir -p "$base/build/vbox-x64"
./configure --only-additions --build-headless --disable-docs --disable-kmods \
  --disable-opengl --disable-qt --disable-python --disable-java --disable-dbus \
  --disable-devmapper --disable-hardening --target-arch=amd64 \
  --with-gcc="$tc-gcc" --with-g++="$tc-g++" --with-kbuild=/usr/share/kBuild \
  --with-nasm=/usr/bin/nasm --with-yasm=/usr/bin/yasm --with-makeself=/usr/bin/echo \
  --out-base-dir="$base/build/vbox-x64"
cat > LocalConfig.kmk <<'CFG'
VBOX_WITHOUT_ADDITIONS_ISO = 1
VBOX_WITHOUT_LINUX_GUEST_PACKAGE = 1
VBOX_WITH_X11_ADDITIONS =
VBOX_WITH_DBUS =
VBOX_WITH_PAM =
IPRT_WITHOUT_PAM = 1
VBOX_WITH_LIBCURL =
VBOX_WITH_TESTCASES =
VBOX_WITH_TESTSUITE =
VBOX_WITH_VALIDATIONKIT =
VBOX_WITH_ADDITIONS_SHIPPING_AUDIO_TEST =
VBOX_WITH_HOST_SHIPPING_AUDIO_TEST =
VBOX_GCC_WERR =
CFG
source "$base/build/vbox-x64/env.sh"
# The release tarball sits inside Aether's Git repository; use its documented
# fallback revision instead of interpreting Aether commits as VirtualBox SVN.
kmk -j"$(nproc)" VBOX_OSE=1 VBOX_SVN_REV=175154 VBOX_ONLY_ADDITIONS=1 VBOX_ONLY_ADDITIONS_WITHOUT_RTISOMAKER=1
