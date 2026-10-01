#!/bin/bash
set -euo pipefail
test ! -f /build/done/open-vm-tools || exit 0
archive=/sources/open-vm-tools-13.1.0-25218885.tar.gz
echo "67a23d505aca77127b081445f758e269b1009e8824cf7f6f2d6efafb0b14d0fd  $archive" | sha256sum -c -
mkdir -p /build/vmtools
if [ ! -f /build/vmtools/.prepared ]; then
 tar -xf "$archive" -C /build/vmtools --strip-components=1
 cd /build/vmtools
 for patchfile in /recipes/patches/vmtools/*.patch; do patch -Np1 -i "$patchfile"; done
 sed -i 's/enable_vgauth = "no"/enable_vgauth="no"/g' configure
 touch .prepared
fi
cd /build/vmtools
export CFLAGS='-O2 -pipe -march=x86-64 -std=gnu11'
./configure --prefix=/usr --sysconfdir=/etc --localstatedir=/var \
 --with-gtk3 --without-gtk4 --without-icu --without-dnet --without-pam \
 --without-ssl --without-xml2 --without-xmlsec1 --disable-vgauth \
 --disable-containerinfo --disable-deploypkg --without-kernel-modules
make -j"$(nproc)"
make install
ldconfig
test -f /usr/lib/open-vm-tools/plugins/vmusr/libdndcp.so
test -x /usr/bin/vmware-user-suid-wrapper
test -x /usr/bin/vmhgfs-fuse
touch /build/done/open-vm-tools
