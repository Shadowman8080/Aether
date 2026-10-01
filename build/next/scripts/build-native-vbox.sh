#!/bin/bash
set -euo pipefail
test ! -f /build/done/virtualbox-additions || exit 0
archive=/sources/VirtualBox-7.2.20.tar.bz2
echo "5c2138213b72f36c129b92c2c267f2a40e9c98513f4c86a584327f09f9be706d  $archive" | sha256sum -c -
if [ ! -d /build/VirtualBox-7.2.20 ]; then tar -xf "$archive" -C /build; fi
cd /build/VirtualBox-7.2.20
export KBUILD_PATH=/build/host-tools/kBuild PATH_KBUILD=/build/host-tools/kBuild
export KBUILD_BIN_PATH=/build/host-tools
mkdir -p /build/vbox-native
./configure --only-additions --disable-docs --disable-kmods --disable-sdl --disable-sdl-ttf \
 --disable-opengl --disable-qt --disable-python --disable-java --disable-dbus \
 --disable-devmapper --disable-hardening --target-arch=amd64 \
 --with-gcc=/usr/bin/gcc --with-g++=/usr/bin/g++ \
 --with-kbuild=/build/host-tools/kBuild --with-nasm=/build/host-tools/nasm \
 --with-yasm=/build/host-tools/yasm --with-makeself=/usr/bin/echo \
 --out-base-dir=/build/vbox-native
cat >LocalConfig.kmk <<'EOF'
VBOX_WITHOUT_ADDITIONS_ISO = 1
VBOX_WITHOUT_LINUX_GUEST_PACKAGE = 1
VBOX_WITH_X11_ADDITIONS = 1
VBOX_NO_LEGACY_XORG_X11 = 1
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
EOF
source /build/vbox-native/env.sh
kmk -j"$(nproc)" VBOX_OSE=1 VBOX_SVN_REV=175154 VBOX_ONLY_ADDITIONS=1 VBOX_ONLY_ADDITIONS_WITHOUT_RTISOMAKER=1
out=/build/vbox-native/linux.amd64/release/bin/additions
for exe in VBoxService VBoxControl VBoxClient; do install -m755 "$out/$exe" /usr/bin/; done
install -m755 "$out/mount.vboxsf" /usr/sbin/
install -m755 "$out/VBoxDRMClient" /usr/bin/
install -Dm644 COPYING /usr/share/licenses/virtualbox-additions/COPYING
ldconfig
VBoxService --version
VBoxControl --version
VBoxClient --version
touch /build/done/virtualbox-additions
