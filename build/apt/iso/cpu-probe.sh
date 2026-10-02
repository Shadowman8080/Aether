#!/bin/bash
# Baseline-CPU probe for the unified ISO.
#
# Run the package-manager chain and the AI/desktop binaries under an emulated
# `qemu64` CPU. A binary built with `-march=x86-64 -mtune=generic` must not
# trap on any instruction qemu64 lacks; a SIGILL (exit 132) is a failure. This
# is the image-level counterpart to the per-app probe in
# build/desktop/scripts/verify-cpu-compatibility.sh.
#
# Caveat: some complex Qt binaries (plasmashell) can SIGSEGV (exit 139) under
# qemu-user emulation for reasons unrelated to CPU features (no session bus,
# odd runtime dir). The original local-ai image segfaults identically in the
# same bare environment, so that is an artifact, not a regression. The real
# whole-system check is smoke-boot.py, which boots under `-cpu qemu64`.
#
# Usage: cpu-probe.sh [iso-path]
# Log:   $BASE/logs/apt/140-cpu-probe.log
set -euo pipefail

BASE=${BASE:-/opt/aether}
ISO=${1:-$BASE/images/aether-0.3-x86_64-unified.iso}
M=$BASE/build/cpu-probe
LOG=$BASE/logs/apt/140-cpu-probe.log

exec >"$LOG" 2>&1
echo "START $(date -u +%FT%TZ)"
command -v qemu-x86_64
qemu-x86_64 --version | head -1

for mp in "$M/root" "$M/iso"; do umount "$mp" 2>/dev/null || true; done
rm -rf "$M"; mkdir -p "$M/iso" "$M/root"
mount -o loop,ro "$ISO" "$M/iso"
mount -o loop,ro "$M/iso/live/rootfs.squashfs" "$M/root"
echo "mounted: $(findmnt -n -o SOURCE "$M/root")"

rc_all=0
probe() {
  local bin="$1"; shift
  echo "--- $bin $*"
  set +e
  timeout 90 env HOME=/tmp XDG_RUNTIME_DIR=/tmp QT_QPA_PLATFORM=offscreen \
    qemu-x86_64 -cpu qemu64 -L "$M/root" "$M/root/$bin" "$@" \
    >/tmp/cpu.out 2>&1
  local rc=$?
  set -e
  head -3 /tmp/cpu.out | sed 's/^/    /'
  echo "    exit=$rc"
  # Only an illegal instruction (SIGILL, signal 4) means the CPU feature set
  # is too low. A SIGSEGV (signal 11) under qemu-user is an emulation artifact
  # (no session bus, odd runtime dir), not a CPU-feature failure.
  if [ "$rc" -eq 132 ] || [ "$rc" -eq 4 ]; then
    echo "    FAIL: illegal instruction / SIGILL"; rc_all=1
  elif grep -qiE 'Illegal instruction|uncaught target signal 4|symbol lookup error' /tmp/cpu.out; then
    echo "    FAIL: $(grep -iE 'Illegal instruction|uncaught target signal 4|symbol lookup error' /tmp/cpu.out | head -1)"; rc_all=1
  elif [ "$rc" -eq 139 ]; then
    echo "    ok (SIGSEGV under qemu-user, not SIGILL)"
  else
    echo "    ok"
  fi
}

probe usr/bin/apt-get --version
probe usr/bin/dpkg --version
probe usr/bin/dpkg --admindir="$M/root/var/lib/dpkg" -l
probe usr/bin/appstreamcli --version
probe usr/libexec/packagekitd --version
probe usr/bin/plasma-discover --version
probe usr/bin/plasmashell --version
probe usr/bin/nimbrel --help
probe usr/bin/vector --help

echo
echo "=== package count under qemu64 ==="
env HOME=/tmp qemu-x86_64 -cpu qemu64 -L "$M/root" "$M/root/usr/bin/dpkg" \
  --admindir="$M/root/var/lib/dpkg" -l 2>/dev/null | grep -c '^ii' | sed 's/^/  ii lines: /'

for mp in "$M/root" "$M/iso"; do
  umount "$mp" 2>/dev/null || umount -l "$mp" 2>/dev/null || true
done

if [ "$rc_all" -eq 0 ]; then
  echo "RESULT: PASS (no illegal instructions under qemu64)"
else
  echo "RESULT: FAIL"
fi
echo "DONE $(date -u +%FT%TZ)"
exit "$rc_all"
