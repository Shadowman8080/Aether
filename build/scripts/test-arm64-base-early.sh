#!/bin/bash
set -euo pipefail
cd /opt/aether
while ! grep -q '^EXIT ' logs/build-arm64.status; do sleep 5; done
grep -qx 'EXIT 0' logs/build-arm64.status
bash scripts/make-arm64-iso.sh
sed 's@boot-arm64-uefi.log@boot-arm64-base-uefi.log@' scripts/test-boot-arm64.py > build/test-boot-arm64-base.py
python3 build/test-boot-arm64-base.py
