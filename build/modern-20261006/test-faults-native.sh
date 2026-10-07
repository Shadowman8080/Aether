#!/bin/bash
set -euo pipefail
if [ "${FAULT_NS:-}" != 1 ]; then exec unshare --mount --propagation private env FAULT_NS=1 bash "$0"; fi
b=/opt/aether/build/modern-20261006
q="$b/native-fault-test-$(date +%Y%m%dT%H%M%S)"
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
grep -qx CONFIG_NET_NS=y "$r/boot/config-6.18.54-aether4"
mount --rbind /dev "$r/dev"; mount --make-rslave "$r/dev"
mount -t proc proc "$r/proc"; mount -t sysfs sysfs "$r/sys"; mount -t tmpfs tmpfs "$r/run"
printf 'modern-20261006\n' > "$r/run/aether-disposable-test"
cp "$b/project/build/modern-20261006/failed-update-fixture.py" "$r/tmp/failed-update-fixture.py"
chroot "$r" python3 /tmp/failed-update-fixture.py > "$q/fixture.log" 2>&1
cp "$r/tmp/update-fault-fixture-PASS" "$q/PASS"
sync
cleanup
trap - EXIT
qemu-img check "$q/test.qcow2"
echo NATIVE_FAULT_PASS "$q"
