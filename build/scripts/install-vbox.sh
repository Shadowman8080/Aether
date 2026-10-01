#!/bin/bash
set -euo pipefail
base=/opt/aether
case "${1:?architecture required}" in
  x86_64) output=prototype; vbox=vbox-x64; machine=amd64 ;;
  x86) output=prototype-x86; vbox=vbox-x86; machine=x86 ;;
  arm64) output=prototype-arm64; vbox=vbox-arm64; machine=arm64 ;;
  *) exit 2 ;;
esac
bin=$base/build/$vbox/linux.$machine/release/bin/additions
target=$base/build/$output/target
install -Dm755 "$bin/VBoxService" "$target/usr/sbin/VBoxService"
install -Dm755 "$bin/VBoxControl" "$target/usr/bin/VBoxControl"
install -Dm755 "$bin/mount.vboxsf" "$target/sbin/mount.vboxsf"
install -Dm644 "$base/sources/VirtualBox-7.2.20/COPYING" "$target/usr/share/licenses/virtualbox/COPYING"
install -Dm644 "$base/configs/guest-sources.json" "$target/usr/share/aether/guest-sources.json"
