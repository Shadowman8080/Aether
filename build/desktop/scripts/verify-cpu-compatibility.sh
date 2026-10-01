#!/bin/bash
set -euo pipefail
if [ "${AETHER_CPU_PROBE_NS:-}" != 1 ]; then
 exec unshare --mount --propagation private env AETHER_CPU_PROBE_NS=1 bash "$0"
fi
root=/opt/aether/desktop-system
source=$(findmnt -n -o SOURCE --mountpoint "$root")
[[ "$source" == /dev/loop*p3 ]]
[[ "$(losetup -n -O BACK-FILE "${source%p3}")" == /opt/aether/build/aether-0.3-system.raw ]]
exec 9>/opt/aether/build/native-desktop/build.lock
flock -n 9
mount --rbind /dev "$root/dev"
mount --make-rslave "$root/dev"
mount -t proc proc "$root/proc"
mount -t tmpfs tmpfs "$root/tmp"
install -m755 /usr/bin/qemu-x86_64 "$root/tmp/aether-qemu"
install -d -m700 -o1000 -g1000 "$root/tmp/cpu-probe-home" "$root/tmp/cpu-probe-runtime"
probe() {
 chroot --userspec=1000:1000 "$root" env -i HOME=/tmp/cpu-probe-home PATH=/usr/bin:/bin XDG_RUNTIME_DIR=/tmp/cpu-probe-runtime QT_QPA_PLATFORM=offscreen /usr/bin/dbus-run-session -- /tmp/aether-qemu -cpu qemu64 "$@"
}
probe /usr/bin/qalc -t '2+2' >/opt/aether/logs/desktop/cpu-qalc.log 2>&1
grep -qx '4' /opt/aether/logs/desktop/cpu-qalc.log
for app in kcalc okular; do
 set +e
 timeout 25 bash -c 'chroot --userspec=1000:1000 "$1" env -i HOME=/tmp/cpu-probe-home PATH=/usr/bin:/bin XDG_RUNTIME_DIR=/tmp/cpu-probe-runtime QT_QPA_PLATFORM=offscreen /usr/bin/dbus-run-session -- /tmp/aether-qemu -cpu qemu64 "/usr/bin/$2"' bash "$root" "$app" >"/opt/aether/logs/desktop/cpu-$app.log" 2>&1
 result=$?
 set -e
 [[ "$result" == 124 ]] || { cat "/opt/aether/logs/desktop/cpu-$app.log"; echo "$app exited unexpectedly: $result"; exit 1; }
 if grep -iE 'uncaught target signal|Illegal instruction|symbol lookup error' "/opt/aether/logs/desktop/cpu-$app.log"; then exit 1; fi
 echo "PASS: $app stayed running on qemu64 CPU for 25 seconds (offscreen startup probe)."
done
echo 'PASS: calculator arithmetic and selected application startup on qemu64. This does not replace graphical boot tests.'

