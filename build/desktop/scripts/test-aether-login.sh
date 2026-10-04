#!/bin/bash
# Exercise aether-login's file handling against a throwaway root.
#
# AETHER_LOGIN_ROOT points every managed path at a scratch directory, so this
# runs offline and touches nothing on the real system. Permission bits cannot
# be checked on filesystems that ignore chmod (Windows/MSYS), so those checks
# are reported as skipped rather than silently passed.
#
# Usage: sh build/desktop/scripts/test-aether-login.sh
set -u
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
TOOL=$(CDPATH= cd -- "$here/../assets/usr/bin" 2>/dev/null && pwd)/aether-login
if [ ! -f "$TOOL" ]; then
    echo "cannot find aether-login next to $here" >&2
    exit 2
fi

R=${AETHER_LOGIN_TEST_ROOT:-/tmp/aether-login-test}
PASS=0
FAIL=0
SKIP=0

ok()   { PASS=$((PASS+1)); printf '  ok   %s\n' "$1"; }
bad()  { FAIL=$((FAIL+1)); printf '  FAIL %s\n' "$1"; }
skip() { SKIP=$((SKIP+1)); printf '  SKIP %s\n' "$1"; }
check(){ if [ "$2" = "$3" ]; then ok "$1"; else bad "$1 (want '$3' got '$2')"; fi; }
has()  { if printf '%s' "$2" | grep -qF -- "$3"; then ok "$1"; else bad "$1 (missing '$3' in: $2)"; fi; }
hasnt(){ if printf '%s' "$2" | grep -qF -- "$3"; then bad "$1 (unexpected '$3')"; else ok "$1"; fi; }

# Does this filesystem actually remember chmod? If not, mode assertions are
# meaningless here and must not be reported as passing.
probe=$(mktemp); chmod 600 "$probe"
CHMOD_WORKS=no
[ "$(stat -c '%a' "$probe" 2>/dev/null)" = "600" ] && CHMOD_WORKS=yes
rm -f "$probe"

rm -rf "$R"
mkdir -p "$R/etc/aether" "$R/etc/lightdm/lightdm.conf.d" "$R/etc/sssd" "$R/usr/sbin" "$R/usr/bin"
cat > "$R/etc/passwd" <<'EOF'
root:x:0:0::/root:/bin/sh
aether:x:1000:1000::/home/aether:/bin/bash
EOF
printf 'aether' > "$R/etc/aether/default-user"
cat > "$R/etc/lightdm/lightdm.conf" <<'EOF'
[Seat:*]
user-session=plasma
EOF
cat > "$R/etc/nsswitch.conf" <<'EOF'
passwd: files systemd
group:  files systemd
shadow: files systemd
hosts:  files myhostname dns mdns4_minimal [NOTFOUND=return]
netgroup: files
EOF

run() { AETHER_LOGIN_ROOT="$R" sh "$TOOL" "$@" 2>&1; }
nsl()  { grep "^$1:" "$R/etc/nsswitch.conf" | tr -s ' '; }

echo "root=$R chmod_honoured=$CHMOD_WORKS"

echo "== 1. status on a fresh root =="
out=$(run status); rc=$?
check "exit 0" "$rc" "0"
has "automatic login disabled" "$out" "disabled"
has "sssd absent" "$out" "sssd:           not installed"

echo "== 2. check passes with nothing configured =="
out=$(run check); rc=$?
check "exit 0" "$rc" "0"
has "reports disabled" "$out" "automatic login: disabled"
has "reports sssd missing" "$out" "Active Directory: sssd not installed"

echo "== 3. autologin on rejects a user that does not exist =="
out=$(run autologin on nosuchuser); rc=$?
check "exit 1" "$rc" "1"
has "explains why" "$out" "no such local user"

echo "== 4. autologin on rejects an invalid name =="
out=$(run autologin on 'Bad Name'); rc=$?
check "exit 1" "$rc" "1"
has "explains why" "$out" "invalid local user name"

echo "== 5. autologin on writes the drop-in =="
out=$(run autologin on); rc=$?
check "exit 0" "$rc" "0"
conf="$R/etc/lightdm/lightdm.conf.d/70-aether-autologin.conf"
if [ -f "$conf" ]; then ok "drop-in exists"; else bad "drop-in missing"; fi
body=$(cat "$conf" 2>/dev/null)
has "seat section" "$body" "[Seat:*]"
has "user is the default user" "$body" "autologin-user=aether"
has "timeout is immediate" "$body" "autologin-user-timeout=0"
has "session follows user-session" "$body" "autologin-session=plasma"
check "state recorded" "$(grep '^AUTOLOGIN_USER=' "$R/etc/aether/login.conf")" "AUTOLOGIN_USER=aether"

echo "== 6. status and check reflect it =="
out=$(run status); has "reports enabled" "$out" "enabled for user: aether"
out=$(run check); rc=$?
check "check exit 0" "$rc" "0"
has "check passes" "$out" "PASS:"

echo "== 7. a missing user is caught by check =="
printf '[Seat:*]\nautologin-user=ghost\n' > "$conf"
out=$(run check); rc=$?
check "check fails" "$rc" "1"
has "names the failure" "$out" "FAIL: automatic login points at a user that does not exist"

echo "== 8. autologin off removes the drop-in =="
rm -f "$conf"
run autologin on >/dev/null
out=$(run autologin off); rc=$?
check "off exit 0" "$rc" "0"
if [ -f "$conf" ]; then bad "drop-in still present"; else ok "drop-in removed"; fi
out=$(run status); has "back to disabled" "$out" "disabled"

echo "== 9. ad join without sssd fails clearly =="
out=$(run ad join EXAMPLE.COM --user 'DOMAIN\j'); rc=$?
check "exit 1" "$rc" "1"
has "explains sssd missing" "$out" "sssd is not installed"

echo "== 10. ad join with stub sssd and adcli =="
printf '#!/bin/sh\necho "stub adcli: $*" >> %s/adcli.log\nexit 0\n' "$R" > "$R/usr/bin/adcli"
chmod 755 "$R/usr/bin/adcli"
printf '#!/bin/sh\nexit 0\n' > "$R/usr/sbin/sssd"
chmod 755 "$R/usr/sbin/sssd"
out=$(run ad join EXAMPLE.COM --user 'DOMAIN\joiner'); rc=$?
check "exit 0" "$rc" "0"
has "reports the realm" "$out" "Joined EXAMPLE.COM"
has "tells the user how to sign in" "$out" 'user@example.com'
if [ -f "$R/etc/sssd/sssd.conf" ]; then ok "sssd.conf written"; else bad "sssd.conf missing"; fi
sssdbody=$(cat "$R/etc/sssd/sssd.conf")
has "services" "$sssdbody" "services = nss, pam"
has "domain listed" "$sssdbody" "domains = EXAMPLE.COM"
has "ad provider" "$sssdbody" "id_provider = ad"
has "default suffix" "$sssdbody" "default_domain_suffix = example.com"
krb=$(cat "$R/etc/krb5.conf")
has "krb5 default realm" "$krb" "default_realm = EXAMPLE.COM"
has "krb5 realm block" "$krb" "EXAMPLE.COM = {"
has "krb5 domain realm" "$krb" ".example.com = EXAMPLE.COM"
if [ -f "$R/etc/aether/domain-login" ]; then ok "domain marker written"; else bad "domain marker missing"; fi
if [ "$CHMOD_WORKS" = yes ]; then
    check "sssd.conf is 0600" "$(stat -c '%a' "$R/etc/sssd/sssd.conf")" "600"
else
    skip "sssd.conf mode (this filesystem ignores chmod; verify on Linux)"
fi

echo "== 11. nsswitch gained sss in the right place =="
ns=$(cat "$R/etc/nsswitch.conf")
check "passwd line" "$(nsl passwd)" "passwd: files sss systemd"
check "group line"  "$(nsl group)"  "group: files sss systemd"
check "hosts line keeps the trailing action last" \
      "$(nsl hosts)" \
      "hosts: files sss myhostname dns mdns4_minimal [NOTFOUND=return]"
has "unrelated lines untouched" "$ns" "netgroup: files"
hasnt "netgroup untouched" "$(nsl netgroup)" "sss"

echo "== 12. ad join is idempotent about sss =="
run ad join EXAMPLE.COM --user 'DOMAIN\joiner' >/dev/null
check "passwd has one sss" "$(nsl passwd)" "passwd: files sss systemd"
check "hosts has one sss" "$(nsl hosts)" \
      "hosts: files sss myhostname dns mdns4_minimal [NOTFOUND=return]"
has "adcli was actually invoked" "$(cat "$R/adcli.log" 2>/dev/null)" \
    "domain join --user DOMAIN\joiner EXAMPLE.COM"

echo "== 13. ad leave reverses everything =="
out=$(run ad leave); rc=$?
check "exit 0" "$rc" "0"
if [ -f "$R/etc/sssd/sssd.conf" ]; then bad "sssd.conf still present"; else ok "sssd.conf removed"; fi
if [ -f "$R/etc/aether/domain-login" ]; then bad "marker still present"; else ok "marker removed"; fi
check "passwd restored" "$(nsl passwd)" "passwd: files systemd"
check "hosts restored" "$(nsl hosts)" \
      "hosts: files myhostname dns mdns4_minimal [NOTFOUND=return]"
check "state cleared" "$(grep '^AD_ENABLED=' "$R/etc/aether/login.conf")" "AD_ENABLED=0"

echo "== 14. ad status =="
out=$(run ad status)
has "reports sssd installed" "$out" "sssd:           installed"
has "reports not joined" "$out" "sssd.conf:      absent (not joined)"
# The join tool is reported separately from sssd: sssd signs a joined machine
# in, adcli is what joins one in the first place.
has "reports join tool present" "$out" "adcli:          installed (domain join available)"
rm -f "$R/usr/bin/adcli"
out=$(run ad status)
has "reports join tool absent" "$out" "adcli:          not installed"
has "explains the join is unavailable" "$out" "Aether does not build yet"
has "says a joined machine still signs in" "$out" "joined machine still signs in through sssd"

echo "== 15. unknown verbs are rejected =="
out=$(run bogus); rc=$?
check "unknown top verb fails" "$rc" "1"
out=$(run autologin bogus); rc=$?
check "unknown sub verb fails" "$rc" "1"
has "shows usage" "$out" "usage: aether-login autologin"

echo
printf 'PASS=%d FAIL=%d SKIP=%d\n' "$PASS" "$FAIL" "$SKIP"
[ "$FAIL" -eq 0 ]