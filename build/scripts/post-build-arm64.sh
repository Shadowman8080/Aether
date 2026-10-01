#!/bin/bash
set -eu
target=$1
grep -q '^ttyAMA0::' "$target/etc/inittab" || printf '\nttyAMA0::respawn:/sbin/getty -L ttyAMA0 115200 vt100\n' >> "$target/etc/inittab"
cat > "$BUILD_DIR/aether-toolchain-check.c" <<'SRC'
#include <stdio.h>
#include <gnu/libc-version.h>
int main(void) { printf("Aether target toolchain OK; glibc %s\n", gnu_get_libc_version()); return sizeof(void*) == 8 ? 0 : 1; }
SRC
"$HOST_DIR/bin/aarch64-aether-linux-gnu-gcc" -O2 -march=armv8-a "$BUILD_DIR/aether-toolchain-check.c" -o "$target/usr/bin/aether-toolchain-check"
