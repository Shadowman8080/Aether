#!/bin/bash
# Continue the active foundation build; stop on any failed native stage.
set -euo pipefail
base=/opt/aether
exec 8>"$base/build/native-desktop/pipeline.lock"
flock -n 8 || { echo 'The desktop pipeline is already running.' >&2; exit 1; }
status="$base/logs/desktop/pipeline.status"
date -u '+STARTED %FT%TZ' >"$status"
trap 'echo "EXIT $?" >>"$status"' EXIT
echo 'Waiting for the active foundation build.'
flock "$base/build/native-desktop/build.lock" true
grep -qx 'EXIT 0' "$base/logs/desktop/build.status" || {
    echo 'Foundation did not complete successfully; inspect its package log.' >&2
    exit 1
}
for stage in dependencies frameworks plasma apps; do
    echo "STAGE $stage" | tee -a "$status"
    AETHER_BUILD_LABEL="$stage" bash "$base/desktop/scripts/run-desktop-build.sh" "build-desktop-$stage.py"
done
echo 'PACKAGES_COMPLETE: session configuration, kernel integration and boot tests still required.' | tee -a "$status"
