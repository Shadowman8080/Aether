#!/bin/bash
set -eu
target=$1
grep -q '^ttyS0::' "$target/etc/inittab" || printf '\nttyS0::respawn:/sbin/getty -L ttyS0 115200 vt100\n' >> "$target/etc/inittab"
cat > "$BUILD_DIR/aether-toolchain-check.c" <<'SRC'
#include <stdio.h>
#include <gnu/libc-version.h>
int main(void) { printf("Aether target toolchain OK; glibc %s\n", gnu_get_libc_version()); return sizeof(void*) == 4 ? 0 : 1; }
SRC
"$HOST_DIR/bin/i686-aether-linux-gnu-gcc" -O2 -march=i686 -mtune=generic "$BUILD_DIR/aether-toolchain-check.c" -o "$target/usr/bin/aether-toolchain-check"
