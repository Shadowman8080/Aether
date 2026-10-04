#!/bin/sh
# Offline tests for aether-apt-check.
#
# AETHER_APT_ROOT points every path at a throwaway tree, so the checks can be
# exercised without a chroot and without dpkg or apt installed. Each case builds
# a fake root containing just enough for the branch under test.
#
# Run: sh build/scripts/test-apt-check.sh
set -u

here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
CHECK=$(CDPATH= cd -- "$here/.." && pwd)/overlay/usr/bin/aether-apt-check

pass=0
fail=0
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

ok() { pass=$((pass + 1)); printf '  ok   %s\n' "$1"; }
no() { fail=$((fail + 1)); printf '  FAIL %s\n' "$1"; }

# Run the check against a root, echoing its exit status.
run() {
    AETHER_APT_ROOT=$1 "$CHECK" >"$work/out" 2>&1
    echo $?
}

# A root that passes every check. The dpkg stub reads the status file, so
# emptying that file really does make the root unhealthy.
healthy() {
    R=$1
    mkdir -p "$R/usr/bin" "$R/var/lib/dpkg" "$R/usr/lib/systemd/system" \
             "$R/usr/share/dbus-1/system-services" "$R/usr/lib/packagekit-backend" \
             "$R/etc/apt"
    cat > "$R/var/lib/dpkg/status" <<'EOF'
Package: dpkg
Status: install ok installed
Version: 1.23.11

Package: apt
Status: install ok installed
Version: 3.3.3
EOF
    cat > "$R/usr/bin/dpkg" <<EOF
#!/bin/sh
STATUS=$R/var/lib/dpkg/status
case "\$1" in
  --version) echo "Debian dpkg 1.23.11"; exit 0 ;;
  --audit) exit 0 ;;
  -l)
    printf 'Desired=Unknown/Install/Remove/Purge/Hold\n'
    printf '||/ Name  Version  Architecture  Description\n'
    n=\$(grep -c '^Package: ' "\$STATUS" 2>/dev/null || echo 0)
    i=0
    while [ "\$i" -lt "\$n" ]; do
      printf 'ii  pkg%d  1.0  amd64  test\n' "\$i"
      i=\$((i + 1))
    done
    exit 0 ;;
esac
exit 1
EOF
    cat > "$R/usr/bin/apt-get" <<'EOF'
#!/bin/sh
[ "$1" = --version ] && { echo "apt 3.3.3"; exit 0; }
exit 1
EOF
    cat > "$R/usr/bin/apt-cache" <<'EOF'
#!/bin/sh
[ "$1" = stats ] && exit 0
exit 1
EOF
    : > "$R/usr/lib/systemd/system/packagekit.service"
    : > "$R/usr/share/dbus-1/system-services/org.freedesktop.PackageKit.service"
    : > "$R/usr/lib/packagekit-backend/libpk_backend_apt.so"
    printf '#!/bin/sh\nexit 0\n' > "$R/usr/bin/plasma-discover"
    chmod 755 "$R/usr/bin/dpkg" "$R/usr/bin/apt-get" "$R/usr/bin/apt-cache" \
               "$R/usr/bin/plasma-discover"
}

echo "== 1. a profile with no package chain =="
R=$work/none; mkdir -p "$R"
rc=$(run "$R")
[ "$rc" = 2 ] && ok "absent chain exits 2" || no "absent chain exits 2 (got $rc)"
grep -q 'no package chain' "$work/out" && ok "says why" || no "says why"

echo "== 2. a healthy chain =="
R=$work/good; healthy "$R"
rc=$(run "$R")
[ "$rc" = 0 ] && ok "healthy chain exits 0" || { no "healthy chain exits 0 (got $rc)"; cat "$work/out"; }
grep -q '2 installed packages' "$work/out" && ok "counts installed packages" || no "counts installed packages"
grep -q 'no package repository is attached' "$work/out" && ok "reports no repository" || no "reports no repository"
grep -q 'D-Bus activatable' "$work/out" && ok "reports D-Bus activation" || no "reports D-Bus activation"

echo "== 3. apt-get present but not runnable (the ldconfig trap) =="
R=$work/broken-loader; healthy "$R"
printf '#!/bin/sh\nif [ "$1" = --version ]; then\n  echo "apt-get: error while loading shared libraries: libapt-private.so.0.0" >&2\n  exit 127\nfi\nexit 0\n' > "$R/usr/bin/apt-get"
rc=$(run "$R")
[ "$rc" = 1 ] && ok "broken loader fails" || no "broken loader fails (got $rc)"
grep -q 'FAIL.*apt-get' "$work/out" && ok "names apt-get" || no "names apt-get"

echo "== 4. empty dpkg database =="
R=$work/emptydb; healthy "$R"
printf '' > "$R/var/lib/dpkg/status"
rc=$(run "$R")
[ "$rc" = 1 ] && ok "empty database fails" || no "empty database fails (got $rc)"

echo "== 5. dpkg --audit reports damage =="
R=$work/audit; healthy "$R"
printf '#!/bin/sh\ncase "$1" in\n  --version) echo v; exit 0 ;;\n  --audit) echo "aether-widgets: reinstreq"; exit 0 ;;\nesac\nexit 1\n' > "$R/usr/bin/dpkg"
rc=$(run "$R")
[ "$rc" = 1 ] && ok "audit damage fails" || no "audit damage fails (got $rc)"
grep -q 'reinstreq' "$work/out" && ok "shows the audit output" || no "shows the audit output"

echo "== 6. a repository is attached =="
R=$work/repo; healthy "$R"
printf 'deb http://archive.ubuntu.com/ubuntu jammy main\n' > "$R/etc/apt/sources.list"
rc=$(run "$R")
[ "$rc" = 1 ] && ok "attached repository fails" || no "attached repository fails (got $rc)"
grep -q 'by policy' "$work/out" && ok "explains the policy" || no "explains the policy"

echo "== 7. sources.list.d is inspected too =="
R=$work/repodir; healthy "$R"
mkdir -p "$R/etc/apt/sources.list.d"
printf 'deb [trusted=yes] file:/tmp/repo ./\n' > "$R/etc/apt/sources.list.d/local.list"
rc=$(run "$R")
[ "$rc" = 1 ] && ok "sources.list.d entry fails" || no "sources.list.d entry fails (got $rc)"

echo "== 8. comments and blanks are not a repository =="
R=$work/comments; healthy "$R"
printf '# no repositories here\n\n   \n' > "$R/etc/apt/sources.list"
rc=$(run "$R")
[ "$rc" = 0 ] && ok "comment-only file passes" || { no "comment-only file passes (got $rc)"; cat "$work/out"; }

echo "== 9. PackageKit pieces missing =="
R=$work/nopk; healthy "$R"
rm -f "$R/usr/lib/systemd/system/packagekit.service"
rm -f "$R/usr/share/dbus-1/system-services/org.freedesktop.PackageKit.service"
rm -f "$R/usr/lib/packagekit-backend/libpk_backend_apt.so"
rc=$(run "$R")
[ "$rc" = 1 ] && ok "missing PackageKit fails" || no "missing PackageKit fails (got $rc)"
grep -q 'libpk_backend_apt.so' "$work/out" && ok "names the apt backend" || no "names the apt backend"

echo "== 10. discover missing =="
R=$work/nodiscover; healthy "$R"
rm -f "$R/usr/bin/plasma-discover"
rc=$(run "$R")
[ "$rc" = 1 ] && ok "missing discover fails" || no "missing discover fails (got $rc)"

echo "== 11. the script is POSIX sh and executable in the repo =="
sh -n "$CHECK" && ok "parses with sh -n" || no "parses with sh -n"
[ -x "$CHECK" ] && ok "is executable" || no "is executable"

printf '\nPASS=%d FAIL=%d\n' "$pass" "$fail"
[ "$fail" = 0 ]