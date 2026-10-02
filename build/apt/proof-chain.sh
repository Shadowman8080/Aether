#!/bin/sh
# Proof that the apt chain is functional on the source-built base, run inside
# the disposable chroot rootfs. Covers:
#   1. build real .deb packages with dpkg-deb
#   2. dpkg -i / -s / -L / -(run)
#   3. dpkg -V detecting an intentionally modified file
#   4. dpkg refusing to overwrite a file owned by another package
#   5. dpkg -r removal
#   6. a local file: apt repository with apt-get update/install/remove
#   7. cleanup of the transient source
set -u
R=/tmp/proof
fail=0
pass() { echo "PASS: $1"; }
bad()  { echo "FAIL: $1"; fail=1; }
note() { echo; echo "### $1"; }

APT="apt-get -o APT::Sandbox::User=root"

rm -rf "$R" /tmp/verify.* /tmp/conflict.out /tmp/ftp.err /tmp/apt*.out
mkdir -p "$R/repo" "$R/build"

build_deb() {
  name="$1"; ver="$2"; path="$3"; content="$4"
  d="$R/build/$name"
  mkdir -p "$d/DEBIAN" "$d$(dirname "$path")"
  {
    echo "Package: $name"
    echo "Version: $ver"
    echo "Architecture: amd64"
    echo "Maintainer: Aether Proof <noreply@aether.invalid>"
    echo "Section: test"
    echo "Priority: optional"
    echo "Description: Aether package-manager proof package"
  } > "$d/DEBIAN/control"
  printf '%s\n' "$content" > "$d$path"
  chmod 755 "$d$path"
  dpkg-deb --build --root-owner-group "$d" "$R/repo/${name}_${ver}_amd64.deb" >/dev/null 2>&1
}

note "1. build real .deb packages with dpkg-deb"
build_deb aether-proof-hello 1.0 /usr/bin/aether-proof-hello '#!/bin/sh
echo hello-aether-v1'
build_deb aether-proof-conflict 1.0 /usr/bin/aether-proof-hello '#!/bin/sh
echo conflict-aether'
build_deb aether-proof-apt 1.0 /usr/bin/aether-proof-apt '#!/bin/sh
echo apt-aether-v1'
build_deb aether-proof-apt 2.0 /usr/bin/aether-proof-apt '#!/bin/sh
echo apt-aether-v2'
ls -l "$R/repo" | sed 's/^/  /'
echo "  --- dpkg-deb --info aether-proof-hello ---"
dpkg-deb --info "$R/repo/aether-proof-hello_1.0_amd64.deb" | sed 's/^/  /'
echo "  --- dpkg-deb --contents ---"
dpkg-deb --contents "$R/repo/aether-proof-hello_1.0_amd64.deb" | sed 's/^/  /'

note "2. dpkg install / query / run"
if dpkg -i "$R/repo/aether-proof-hello_1.0_amd64.deb" >/dev/null 2>&1; then pass "dpkg -i hello"; else bad "dpkg -i hello"; fi
dpkg -s aether-proof-hello 2>/dev/null | grep -q '^Status: install ok installed' && pass "dpkg -s status installed" || bad "dpkg -s status"
dpkg -L aether-proof-hello 2>/dev/null | grep -qx /usr/bin/aether-proof-hello && pass "dpkg -L lists the file" || bad "dpkg -L"
[ "$(/usr/bin/aether-proof-hello 2>/dev/null)" = "hello-aether-v1" ] && pass "installed binary runs" || bad "installed binary run"

note "3. dpkg -V detects an intentionally modified file"
dpkg -V aether-proof-hello >/tmp/verify.clean 2>&1
if [ -s /tmp/verify.clean ]; then bad "dpkg -V reported a change on a clean install"; sed 's/^/    /' /tmp/verify.clean; else pass "dpkg -V silent before tampering"; fi
printf '#!/bin/sh\necho TAMPERED\n' > /usr/bin/aether-proof-hello
dpkg -V aether-proof-hello >/tmp/verify.tampered 2>&1
if grep -q '/usr/bin/aether-proof-hello' /tmp/verify.tampered; then pass "dpkg -V detected the modification"; else bad "dpkg -V missed the modification"; fi
sed 's/^/    /' /tmp/verify.tampered
dpkg -i "$R/repo/aether-proof-hello_1.0_amd64.deb" >/dev/null 2>&1
[ "$(/usr/bin/aether-proof-hello 2>/dev/null)" = "hello-aether-v1" ] && pass "reinstall restored the file" || bad "reinstall"

note "4. dpkg refuses to overwrite another package's file"
if dpkg -i "$R/repo/aether-proof-conflict_1.0_amd64.deb" >/tmp/conflict.out 2>&1; then
  bad "dpkg installed a package that overwrites an owned file"
else
  pass "dpkg refused the conflicting package"
fi
grep -i 'trying to overwrite' /tmp/conflict.out | sed 's/^/    /'
[ "$(/usr/bin/aether-proof-hello 2>/dev/null)" = "hello-aether-v1" ] && pass "original file intact after refusal" || bad "original file clobbered"

note "5. dpkg remove"
if dpkg -r aether-proof-hello >/dev/null 2>&1; then pass "dpkg -r hello"; else bad "dpkg -r"; fi
[ -e /usr/bin/aether-proof-hello ] && bad "file still present after remove" || pass "file removed"
if dpkg -s aether-proof-hello >/dev/null 2>&1; then bad "package still known to dpkg"; else pass "package no longer installed"; fi

note "6. local file: apt repository -- update / install / remove"
if command -v apt-ftparchive >/dev/null 2>&1; then
  ( cd "$R/repo" && apt-ftparchive packages . > Packages 2>/tmp/ftp.err \
      && apt-ftparchive release . > Release 2>>/tmp/ftp.err )
  echo "  index generated with apt-ftparchive"
else
  : > "$R/repo/Packages"
  for deb in "$R"/repo/*.deb; do
    [ -e "$deb" ] || continue
    bn=$(basename "$deb")
    {
      echo "Package: $(dpkg-deb -f "$deb" Package)"
      echo "Version: $(dpkg-deb -f "$deb" Version)"
      echo "Architecture: $(dpkg-deb -f "$deb" Architecture)"
      echo "Maintainer: Aether Proof <noreply@aether.invalid>"
      echo "Filename: $bn"
      echo "Size: $(stat -c %s "$deb")"
      echo "SHA256: $(sha256sum "$deb" | awk '{print $1}')"
      echo "Description: Aether package-manager proof package"
      echo
    } >> "$R/repo/Packages"
  done
  echo "  index generated with a fallback (apt-ftparchive absent)"
fi
echo "  --- Packages (first 16 lines) ---"
head -16 "$R/repo/Packages" | sed 's/^/    /'
printf 'deb [trusted=yes] file:%s ./\n' "$R/repo" > /etc/apt/sources.list.d/aether-proof.list
echo "  --- sources entry ---"
sed 's/^/    /' /etc/apt/sources.list.d/aether-proof.list
if $APT update >/tmp/aptupdate.out 2>&1; then pass "apt-get update"; else bad "apt-get update"; sed 's/^/    /' /tmp/aptupdate.out; fi
echo "  --- apt-cache policy before install ---"
apt-cache policy aether-proof-apt 2>/dev/null | sed 's/^/    /'
if $APT install -y aether-proof-apt >/tmp/aptinstall.out 2>&1; then pass "apt-get install"; else bad "apt-get install"; tail -20 /tmp/aptinstall.out | sed 's/^/    /'; fi
dpkg -s aether-proof-apt 2>/dev/null | grep -q '^Status: install ok installed' && pass "apt-installed package is registered" || bad "apt install status"
apt-cache policy aether-proof-apt 2>/dev/null | grep -q 'Installed: 2.0' && pass "apt selected the newest version (2.0)" || bad "apt version selection"
[ -x /usr/bin/aether-proof-apt ] && pass "apt-installed binary present" || bad "binary missing"
echo "  running /usr/bin/aether-proof-apt:"; /usr/bin/aether-proof-apt 2>/dev/null | sed 's/^/    /'
if $APT remove -y aether-proof-apt >/tmp/aptremove.out 2>&1; then pass "apt-get remove"; else bad "apt-get remove"; fi
[ -e /usr/bin/aether-proof-apt ] && bad "binary still present after apt remove" || pass "apt remove deleted the file"

note "7. cleanup of the transient source"
rm -f /etc/apt/sources.list.d/aether-proof.list
if $APT update >/tmp/aptupdate2.out 2>&1; then pass "apt-get update after removing the source"; else bad "final apt-get update"; fi
dpkg --purge aether-proof-conflict >/dev/null 2>&1 || true
rm -rf "$R" /tmp/verify.clean /tmp/verify.tampered /tmp/conflict.out /tmp/ftp.err /tmp/aptupdate.out /tmp/aptinstall.out /tmp/aptremove.out /tmp/aptupdate2.out
pass "transient repo and proof packages removed"
[ -f /etc/apt/sources.list.d/aether-proof.list ] && bad "source entry left behind" || pass "no proof source entry remains"

echo
if [ "$fail" -eq 0 ]; then
  echo "PROOF-CHAIN RESULT: ALL CHECKS PASSED"
else
  echo "PROOF-CHAIN RESULT: FAILURES PRESENT"
fi
exit "$fail"
