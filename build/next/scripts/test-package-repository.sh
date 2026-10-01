#!/bin/bash
# Exercise real libalpm operations in a disposable root, never the host root.
set -euo pipefail
prefix=/opt/aether/build/pacman-host-install
export PATH="$prefix/bin:$PATH"
export LD_LIBRARY_PATH="$prefix/lib/x86_64-linux-gnu:$prefix/lib"
testdir=/opt/aether/build/repository-test
root="$testdir/root"
verify="$testdir/verification-keyring"
[[ "$root" == /opt/aether/build/repository-test/root ]] || exit 1
mkdir -p "$root/var/lib/pacman" "$root/var/cache/pacman/pkg" "$verify"
chmod 700 "$verify"
touch "$verify/pubring.gpg"
gpg --homedir "$verify" --batch --import "$testdir/repo/test-public-key.asc"
fingerprint=$(gpg --homedir "$verify" --with-colons --list-keys | awk -F: '$1=="fpr" {print $10; exit}')
[[ "$fingerprint" =~ ^[A-F0-9]{40}$ ]] || exit 1
printf '%s:6:\n' "$fingerprint" | gpg --homedir "$verify" --import-ownertrust
cat > "$testdir/pacman.conf" <<EOF
[options]
RootDir = $root
DBPath = $root/var/lib/pacman
CacheDir = $root/var/cache/pacman/pkg
GPGDir = $verify
LogFile = $testdir/pacman.log
Architecture = x86_64
SigLevel = Required DatabaseRequired
LocalFileSigLevel = Required

[aether-test]
Server = file://$testdir/repo
EOF
pacman --config "$testdir/pacman.conf" -Sy --noconfirm aether-wallpaper
test -s "$root/usr/share/wallpapers/Aether/contents/images/aether.svg"
pacman --config "$testdir/pacman.conf" -Q aether-wallpaper
original="$testdir/repo/aether-wallpaper-0.2-1-any.pkg.tar.zst"
tampered="$testdir/tampered.pkg.tar.zst"
cp "$original" "$tampered"
cp "$original.sig" "$tampered.sig"
printf 'tampered' >> "$tampered"
if pacman --config "$testdir/pacman.conf" -U --noconfirm "$tampered" > "$testdir/tamper.log" 2>&1; then
  echo 'FAIL: tampered package accepted'; exit 1
fi
grep -qi 'PGP signature' "$testdir/tamper.log"
cp "$original" "$testdir/unsigned.pkg.tar.zst"
if pacman --config "$testdir/pacman.conf" -U --noconfirm "$testdir/unsigned.pkg.tar.zst" > "$testdir/unsigned.log" 2>&1; then
  echo 'FAIL: unsigned package accepted'; exit 1
fi
cmp /opt/aether/next/desktop/usr/share/wallpapers/Aether/contents/images/aether.svg \
  "$root/usr/share/wallpapers/Aether/contents/images/aether.svg"
pacman --config "$testdir/pacman.conf" -R --noconfirm aether-wallpaper
test ! -e "$root/usr/share/wallpapers/Aether/contents/images/aether.svg"
database="$testdir/repo/aether-test.db.tar.gz"
cp "$database" "$testdir/valid-db.backup"
trap 'cp "$testdir/valid-db.backup" "$database"' EXIT
printf 'tampered' >> "$database"
if pacman --config "$testdir/pacman.conf" -Syy --noconfirm > "$testdir/database-tamper.log" 2>&1; then
  echo 'FAIL: tampered repository database accepted'; exit 1
fi
grep -qi 'PGP signature' "$testdir/database-tamper.log"
echo 'PASS: signed repository install/removal; unsigned package, tampered package and database rejected'
