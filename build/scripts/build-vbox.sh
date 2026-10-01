#!/bin/bash
set -euo pipefail
base=/opt/aether
case "${1:-x86_64}" in
  x86_64) output=prototype; triple=x86_64-aether-linux-gnu; arch=amd64; suffix=x64 ;;
  x86) output=prototype-x86; triple=i686-aether-linux-gnu; arch=x86; suffix=x86 ;;
  arm64) output=prototype-arm64; triple=aarch64-aether-linux-gnu; arch=arm64; suffix=arm64 ;;
  *) exit 2 ;;
esac
exec 9>"$base/build/vbox-source.lock"
flock 9
status=$base/logs/vbox-$suffix.status
printf 'STARTED %s\n' "$(date -u +%FT%TZ)" > "$status"
trap 'rc=$?; printf "EXIT %s\nFINISHED %s\n" "$rc" "$(date -u +%FT%TZ)" >> "$status"' EXIT
cd "$base/sources/VirtualBox-7.2.20"
tc=$base/build/$output/host/bin/$triple
mkdir -p "$base/build/vbox-$suffix"
./configure --only-additions --build-headless --disable-docs --disable-kmods \
  --disable-opengl --disable-qt --disable-python --disable-java --disable-dbus \
  --disable-devmapper --disable-hardening --target-arch="$arch" \
  --with-gcc="$tc-gcc" --with-g++="$tc-g++" --with-kbuild=/usr/share/kBuild \
  --with-nasm=/usr/bin/nasm --with-yasm=/usr/bin/yasm --with-makeself=/usr/bin/echo \
  --out-base-dir="$base/build/vbox-$suffix"
cat > LocalConfig.kmk <<'CFG'
include /opt/aether/configs/kbuild-tools/GXX3HOST.kmk
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
DEFS.x86 += RT_WITH_OLD_CPU_SUPPORT
VBOX_GCC_WERR =
CFG
# Keep target archive/link/objcopy tools separate from native build generators.
for tool in GXX3 GCC3 GXX32 GCC32; do
    printf 'TOOL_%s_AR := %s-ar\n' "$tool" "$tc" >> LocalConfig.kmk
    printf 'TOOL_%s_RANLIB := %s-ranlib\n' "$tool" "$tc" >> LocalConfig.kmk
    printf 'TOOL_%s_LD_SYSMOD := %s-ld\n' "$tool" "$tc" >> LocalConfig.kmk
    printf 'TOOL_%s_OBJCOPY := %s-objcopy\n' "$tool" "$tc" >> LocalConfig.kmk
done
source "$base/build/vbox-$suffix/env.sh"
# The release tarball sits inside Aether's Git repository; use its documented
# fallback revision instead of interpreting Aether commits as VirtualBox SVN.
kmk -j"$(nproc)" TEMPLATE_VBoxBldProg_TOOL=GXX3HOST TEMPLATE_VBoxAdvBldProg_TOOL=GXX3HOST VBOX_OSE=1 VBOX_SVN_REV=175154 VBOX_ONLY_ADDITIONS=1 VBOX_ONLY_ADDITIONS_WITHOUT_RTISOMAKER=1
