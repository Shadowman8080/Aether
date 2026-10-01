#!/bin/bash
set -euo pipefail
export CFLAGS='-O2 -pipe -march=x86-64' CXXFLAGS='-O2 -pipe -march=x86-64'
export PKG_CONFIG_PATH=/usr/lib/pkgconfig:/usr/share/pkgconfig
python3 /recipes/scripts/build-native-bindings.py
python3 /recipes/scripts/build-native-efi-fonts.py > /build/logs/efi-fonts.log 2>&1
bash /recipes/scripts/build-native-vmtools.sh > /build/logs/open-vm-tools.log 2>&1
bash /recipes/scripts/build-native-vbox.sh > /build/logs/virtualbox-additions.log 2>&1
python3 /recipes/scripts/configure-guest-integration.py > /build/logs/guest-integration-config.log 2>&1
echo 'Native EFI and graphical guest tools complete.'
