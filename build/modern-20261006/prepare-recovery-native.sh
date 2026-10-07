#!/bin/bash
set -euo pipefail
if [ "${RECOVERY_NS:-}" != 1 ]; then exec unshare --mount --propagation private env RECOVERY_NS=1 bash "$0"; fi
b=/opt/aether/build/modern-20261006
q="$b/native-recovery-test-$(date +%Y%m%dT%H%M%S)"
mkdir -p "$q/root"
r="$q/root"
test ! -e /sys/block/nbd7/pid
qemu-img create -f qcow2 -F vmdk -b "$b/aether-0.3.2-dev-20261006-x86_64.vmdk" "$q/test.qcow2"
qemu-nbd --cache=writeback --connect=/dev/nbd7 --format=qcow2 "$q/test.qcow2"
cleanup() {
 for m in "$r/dev" "$r/proc" "$r/sys" "$r/run" "$r"; do
  if mountpoint -q "$m"; then umount -R "$m" || return 1; fi
 done
 qemu-nbd --disconnect /dev/nbd7
}
trap cleanup EXIT
partprobe /dev/nbd7; udevadm settle
for i in $(seq 1 20); do [ -b /dev/nbd7p3 ] && break; sleep 1; done
mount /dev/nbd7p3 "$r"
grep -qx ID=aether "$r/etc/os-release"
mount --rbind /dev "$r/dev"; mount --make-rslave "$r/dev"
mount -t proc proc "$r/proc"; mount -t sysfs sysfs "$r/sys"; mount -t tmpfs tmpfs "$r/run"
chroot "$r" python3 - > "$q/create.log" 2>&1 <<'PY'
from pathlib import Path
import sys
sys.path.insert(0,'/usr/lib/aether-updates')
import slots
Path('/etc/aether-checkpoint-proof').write_text('before')
Path('/home/aether/aether-checkpoint-proof').write_text('shared')
with slots.lock():
 p,m=slots.create();slots.register(p,m)
 (p/'root/etc/systemd/system/graphical.target.wants/aether-system-health.service').unlink()
 Path('/etc/aether-checkpoint-proof').write_text('after')
 slots.activate(m['id']);Path('/tmp/native-checkpoint-id').write_text(m['id'])
print('NATIVE_CHECKPOINT_PASS',m['id'],flush=True)
PY
cp "$r/tmp/native-checkpoint-id" "$q/slot-id"
sync
cleanup
trap - EXIT
qemu-img check "$q/test.qcow2"
printf '%s\n' "$q" > "$b/native-recovery-latest"
echo NATIVE_RECOVERY_PREPARED "$q"
