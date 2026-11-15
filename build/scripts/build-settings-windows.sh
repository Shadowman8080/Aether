#!/bin/bash
# Build and optionally start Aether Settings on a Windows machine that has the
# Qt 6 MinGW kit installed. This is a developer convenience for looking at the
# first-party UI on Windows: it compiles src/controlcenter only.
#
# It does not build Aether. The distribution is a Linux system built on a Linux
# build host from pinned upstream sources; see docs/build.md. Nothing here
# changes a Linux image.
#
#   bash build/scripts/build-settings-windows.sh          # build
#   bash build/scripts/build-settings-windows.sh --run    # build and start
#
# Overrides: AETHER_QT_ROOT (default /c/Qt), AETHER_BUILD_DIR.
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
qt_root=${AETHER_QT_ROOT:-/c/Qt}
kit=$(ls -d "$qt_root"/[0-9]*/mingw_64 2>/dev/null | sort -V | tail -1 || true)
tools=$qt_root/Tools
cmake=${AETHER_CMAKE:-$(command -v cmake || ls "$tools"/CMake_*/bin/cmake.exe 2>/dev/null | head -1 || true)}
ninja=$(ls "$tools"/Ninja/ninja.exe 2>/dev/null | head -1 || true)
mingw=$(ls -d "$tools"/mingw*_64 2>/dev/null | sort -V | tail -1 || true)
for pair in "Qt MinGW kit:$kit" "cmake:$cmake" "MinGW compiler:$mingw"; do
  [ -n "${pair#*:}" ] || { echo "Missing ${pair%%:*}. Install it with the Qt Maintenance Tool." >&2; exit 2; }
done
export PATH="$mingw/bin:$kit/bin:$PATH"
build=${AETHER_BUILD_DIR:-$root/build-local/settings}
settings=(-G Ninja -DCMAKE_BUILD_TYPE=Release
  -DCMAKE_PREFIX_PATH="$(cygpath -m "$kit")"
  -DCMAKE_CXX_COMPILER="$(cygpath -m "$mingw/bin/g++.exe")")
[ -n "$ninja" ] && settings+=(-DCMAKE_MAKE_PROGRAM="$(cygpath -m "$ninja")") || settings=(-DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="$(cygpath -m "$kit")")
"$cmake" -S "$root/src/controlcenter" -B "$build" "${settings[@]}"
"$cmake" --build "$build"
echo "Built $build/aether-settings.exe"
if [ "${1:-}" = "--run" ]; then exec "$build/aether-settings.exe"; fi
