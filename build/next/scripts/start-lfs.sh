#!/bin/bash
set -euo pipefail
cd /opt/aether/sources/jhalfs
# The base build does not need Git (which pulls in a Rust/LLVM bootstrap).
# Pinned book sources are supplied by the host. Build native Git separately.
sed -i 's/^DEP_GIT=y/# DEP_GIT is not set/' configuration
printf 'yes\nyes\n' | ./jhalfs run
sed -i 's/--with-gcc-arch=native/--with-gcc-arch=x86-64/' /opt/aether/system/jhalfs/lfs-commands/chapter08/849-libffi
cp configuration /opt/aether/next/configs/jhalfs.configuration
cd /opt/aether/system/jhalfs
make
