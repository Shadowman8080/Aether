#!/bin/bash
set -euo pipefail
cd /opt/aether
prefix=/opt/aether/build/pacman-host-install
meson setup build/pacman-host sources/pacman-7.1.0 --prefix="$prefix" \
  --buildtype=release -Ddoc=disabled -Ddoxygen=disabled -Dgpgme=enabled \
  -Dcurl=enabled -Dpkg-ext=.pkg.tar.zst
meson compile -C build/pacman-host -j "$(nproc)"
DESTDIR=/opt/aether/build/pacman-host-stage meson install -C build/pacman-host
mkdir -p "$prefix"
cp -a "/opt/aether/build/pacman-host-stage$prefix/." "$prefix/"
mkdir -p "$prefix/etc"
cp /opt/aether/build/pacman-host-stage/etc/makepkg.conf "$prefix/etc/"
export PATH="$prefix/bin:$PATH"
export LD_LIBRARY_PATH="$prefix/lib/x86_64-linux-gnu:$prefix/lib"
testdir=/opt/aether/build/repository-test
mkdir -p "$testdir/package" "$testdir/repo" "$testdir/signing"
chmod 700 "$testdir/signing"
export GNUPGHOME="$testdir/signing"
if ! gpg --list-secret-keys 'Aether development repository test' >/dev/null 2>&1; then
  gpg --batch --passphrase '' --quick-generate-key 'Aether development repository test' ed25519 sign 30d
fi
gpg --armor --export 'Aether development repository test' > "$testdir/repo/test-public-key.asc"
cd "$testdir/package"
tar -czf aether-wallpaper.tar.gz -C /opt/aether/next/desktop/usr/share/wallpapers Aether
cat > PKGBUILD <<'EOF'
pkgname=aether-wallpaper
pkgver=0.2
pkgrel=1
pkgdesc='Original Aether First Light wallpaper'
arch=('any')
license=('CC0-1.0')
source=('aether-wallpaper.tar.gz')
package() {
  install -d "$pkgdir/usr/share/wallpapers"
  cp -a "$srcdir/Aether" "$pkgdir/usr/share/wallpapers/"
}
EOF
checksum=$(sha256sum aether-wallpaper.tar.gz | cut -d' ' -f1)
printf "sha256sums=('%s')\n" "$checksum" >> PKGBUILD
makepkg --config "$prefix/etc/makepkg.conf" --nodeps --force --sign --key 'Aether development repository test'
cp aether-wallpaper-0.2-1-any.pkg.tar.zst{,.sig} "$testdir/repo/"
repo-add --sign --key 'Aether development repository test' "$testdir/repo/aether-test.db.tar.gz" \
  "$testdir/repo/aether-wallpaper-0.2-1-any.pkg.tar.zst"
cp PKGBUILD /opt/aether/next/packages/wallpaper-test.PKGBUILD
printf 'EXIT 0\n' > /opt/aether/logs/next/package-tools.status
