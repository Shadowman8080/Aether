#!/bin/bash
set -euo pipefail
cd /opt/aether
export AETHER_AI_MANIFEST=/opt/aether/next/assistant/model.json
export XDG_DATA_HOME=/opt/aether/build/assistant-test-data
mkdir -p logs/next
date -u '+STARTED %FT%TZ' > logs/next/ai.status
trap 'result=$?; echo "EXIT $result" >> /opt/aether/logs/next/ai.status' EXIT
python3 next/assistant/aether-ai.py download > logs/next/model-download.log
cmake -S sources/llama.cpp -B build/llama-host -DCMAKE_BUILD_TYPE=Release \
  -DGGML_NATIVE=OFF -DGGML_SSE42=OFF -DGGML_AVX=OFF -DGGML_AVX2=OFF \
  -DGGML_BMI2=OFF -DGGML_FMA=OFF -DGGML_F16C=OFF -DGGML_AVX512=OFF \
  -DGGML_OPENMP=ON -DLLAMA_OPENSSL=OFF -DLLAMA_BUILD_TESTS=OFF \
  -DLLAMA_BUILD_UI=OFF -DLLAMA_USE_PREBUILT_UI=OFF \
  -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_BUILD_SERVER=ON \
  -DCMAKE_C_FLAGS='-march=x86-64 -mtune=generic' \
  -DCMAKE_CXX_FLAGS='-march=x86-64 -mtune=generic'
cmake --build build/llama-host --target llama-server -j "$(nproc)"
export AETHER_LLAMA_SERVER=/opt/aether/build/llama-host/bin/llama-server
printf '%s\n' '{"text":"In one sentence, what is a Linux kernel?"}' | \
  python3 next/assistant/aether-ai.py session > logs/next/ai-inference.jsonl
python3 - <<'PY'
import json
from pathlib import Path
rows = [json.loads(line) for line in Path('logs/next/ai-inference.jsonl').read_text().splitlines()]
assert not any(r['type'] == 'error' for r in rows), rows
assert any(r['type'] == 'answer' and r.get('text', '').strip() for r in rows), rows
print('Local model download, load, and answer passed.')
PY
