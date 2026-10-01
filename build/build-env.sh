# Source this file in the aetherbuild account before building.
export AETHER=/opt/aether
export AETHER_TARGET=x86_64-aether-linux-gnu
export LC_ALL=POSIX
export TZ=UTC
export MAKEFLAGS="-j$(nproc)"
# Generic x86-64 baseline: do not use -march=native for release artifacts.
export AETHER_CFLAGS='-O2 -march=x86-64 -mtune=generic'
