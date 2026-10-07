#!/bin/bash
set -euo pipefail
if [ "${AETHER_ENGINE_NS:-}" != 1 ]; then exec unshare --mount --propagation private env AETHER_ENGINE_NS=1 bash "$0"; fi
b=/opt/aether/build/modern-20261006
root=/opt/aether/build/apt-root
source=/opt/aether/sources/llama.cpp
test "$(git -c safe.directory="$source" -C "$source" rev-parse HEAD)" = 2145525a4081d66ff1a87cf43ef809f95a85ac0c
test -z "$(git -c safe.directory="$source" -C "$source" status --porcelain)"
mount --rbind /dev "$root/dev"; mount --make-rslave "$root/dev"
mount -t proc proc "$root/proc"; mount -t sysfs sysfs "$root/sys"
mount -t tmpfs tmpfs "$root/run"
mkdir -p "$root/modern" "$root/llama-source"
mount --bind "$b" "$root/modern"
mount --bind "$source" "$root/llama-source"
chroot "$root" cmake -S /llama-source -B /modern/obj/nimbrel-engine -G Ninja -DCMAKE_BUILD_TYPE=Release \
 -DGGML_NATIVE=OFF -DGGML_BMI2=OFF -DGGML_AVX=OFF -DGGML_AVX2=OFF -DGGML_AVX512=OFF \
 -DGGML_FMA=OFF -DGGML_F16C=OFF -DGGML_SSE42=OFF -DGGML_OPENMP=OFF \
 -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_CURL=OFF \
 -DCMAKE_C_FLAGS='-O2 -march=x86-64 -mtune=generic' -DCMAKE_CXX_FLAGS='-O2 -march=x86-64 -mtune=generic'
chroot "$root" cmake --build /modern/obj/nimbrel-engine --target llama-server --parallel "$(nproc)"
mkdir -p "$b/stage/opt/nimbrel/engine"
cp -a "$b/obj/nimbrel-engine/bin/llama-server" "$b/obj/nimbrel-engine/bin/"*.so* "$b/stage/opt/nimbrel/engine/"
git -c safe.directory="$source" -C "$source" archive --format=tar --prefix=llama.cpp/ HEAD | gzip -n > "$b/sources/llama.cpp-2145525a.tar.gz"
sha256sum "$b/sources/llama.cpp-2145525a.tar.gz" > "$b/engine-source.sha256"
echo BASELINE_ENGINE_BUILD_PASS
