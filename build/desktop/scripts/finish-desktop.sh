#!/bin/bash
# Post-package phases: release kernel, boot/session installation, ISO assembly.
# Each step is guarded by a completion marker so a rerun resumes, not repeats.
set -euo pipefail
base=/opt/aether
log=$base/logs/desktop/finish.log
mkdir -p "$base/build"
say() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" | tee -a "$log"; }

if [ -f "$base/build/desktop-kernel.complete" ] && [ -f "$base/build/desktop-kernel-stage/kernel-release" ] \
   && [ "$(cat "$base/build/desktop-kernel-stage/kernel-release")" = 6.18.54-aether3 ]; then
    say 'finish: kernel already complete'
else
    say 'finish: building kernel 6.18.54-aether3'
    bash "$base/desktop/scripts/build-desktop-kernel.sh"
    touch "$base/build/desktop-kernel.complete"
    say 'finish: kernel complete'
fi

if [ -f "$base/build/desktop-boot.complete" ]; then
    say 'finish: boot already installed'
else
    say 'finish: installing boot, session and assets'
    bash "$base/desktop/scripts/install-desktop-boot.sh"
    touch "$base/build/desktop-boot.complete"
    say 'finish: boot complete'
fi

if [ -f "$base/images/aether-0.3-x86_64-desktop.iso" ]; then
    say 'finish: ISO already present'
else
    say 'finish: assembling ISO'
    bash "$base/desktop/scripts/build-desktop-iso.sh"
    say 'finish: ISO complete'
fi
say 'finish: all phases complete'
