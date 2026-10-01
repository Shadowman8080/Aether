#!/bin/bash
set -euo pipefail
cd /opt/aether
exec 9> logs/next/components.lock
flock -n 9 || { echo 'Component verification is already running.'; exit 1; }
date -u '+STARTED %FT%TZ' > logs/next/components.status
trap 'result=$?; echo "EXIT $result" >> /opt/aether/logs/next/components.status' EXIT
runuser -u aetherbuild -- bash next/scripts/test-local-ai.sh > logs/next/ai-final-build.log 2>&1
unshare --net bash -c '
  set -e
  ip link set lo up
  exec runuser -u aetherbuild -- env \
    AETHER_AI_MANIFEST=/opt/aether/next/assistant/model.json \
    XDG_DATA_HOME=/opt/aether/build/assistant-test-data \
    AETHER_LLAMA_SERVER=/opt/aether/build/llama-host/bin/llama-server \
    python3 /opt/aether/next/assistant/test_inference.py
' > logs/next/ai-offline-test.log 2>&1
runuser -u aetherbuild -- bash next/scripts/build-next-kernel.sh > logs/next/kernel-build.log 2>&1
