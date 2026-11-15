#!/bin/bash
# Keeps the Aether desktop pipeline from becoming an unattended outage.
#
# Retrying an identical failure forever is useless, so this supervisor:
#   * restarts after a transient stop (no configure failures recorded), capped;
#   * restarts after a blocked stop only when the build inputs changed, which is
#     what happens after a missing dependency is added;
#   * never spins on the same failure signature;
#   * writes build/desktop/BUILD_STATUS.txt and raises a Windows popup so a
#     block is visible without polling;
#   * reports a run that is alive but has stopped producing output.
set -uo pipefail
base=${AETHER_BASE:-/opt/aether}
repo=${AETHER_REPO:-/mnt/c/Users/donjf/.freebuff/worktrees/a961bd2a/73e754ab2fd33fd3dc142b8136e7062ff700598b1d356e63/build/desktop}
status=$base/logs/desktop/pipeline.status
failures=$base/build/native-desktop/failures.txt
marker=$repo/BUILD_STATUS.txt
log=$base/logs/desktop/supervisor.log
stamps=$base/build/native-desktop/done
logs=$base/build/native-desktop/logs
interval=${AETHER_SUPERVISOR_INTERVAL:-45}
stall=${AETHER_STALL_SECONDS:-1800}
max_transient=${AETHER_MAX_TRANSIENT:-2}
once=${1:-}
dry=${AETHER_SUPERVISOR_DRY:-0}

say() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" >>"$log"; }
running() { pgrep -f 'continue-desktop-build\.sh' >/dev/null 2>&1; }
notify() {
    say "notify: $1"
    command -v powershell.exe >/dev/null 2>&1 || return 0
    powershell.exe -NoProfile -NonInteractive -Command \
        "(New-Object -ComObject WScript.Shell).Popup('$2',30,'$1',48)" >/dev/null 2>&1 &
}
newest() {
    { find "$stamps" -maxdepth 1 -type f -printf '%T@\n' 2>/dev/null
      find "$logs" -maxdepth 1 -type f -printf '%T@\n' 2>/dev/null
      find "$base/logs/desktop" -maxdepth 1 -type f -printf '%T@\n' 2>/dev/null
    } | sort -n | tail -1 | cut -d. -f1
}
age_seconds() { local n; n=$(newest); [ -n "${n:-}" ] || { echo 0; return; }; echo $(( $(date +%s) - n )); }
signature() {
    { cat "$failures" 2>/dev/null
      stat -c '%n %Y' "$base/desktop/scripts"/*.py "$base/desktop/configs/sources.json" 2>/dev/null
    } | sha256sum | cut -c1-16
}
marker_write() {
    { echo "state: $1"
      echo "time:  $(date -u +%FT%TZ)"
      echo "stage: $(grep -E '^STAGE ' "$status" 2>/dev/null | tail -1)"
      echo
      if [ -s "$failures" ]; then
          echo "packages that failed to configure (package<TAB>log):"
          sed 's/^/  /' "$failures"
          echo
          echo "The supervisor restarts automatically once the build inputs change."
      else
          echo "No configure failures recorded; the stop looks transient."
      fi
    } >"$marker"
}

say "supervisor start (interval ${interval}s, stall ${stall}s)"
last_sig=$(cat "$base/logs/desktop/supervisor.sig" 2>/dev/null || true); transient=0; last_state=""
while :; do
    if running; then
        [ "$last_state" != running ] && { say "pipeline running"; last_state=running; }
        a=$(age_seconds)
        stage_now=$(grep -E '^STAGE ' "$status" 2>/dev/null | tail -1)
        if [ "${a:-0}" -ge "$stall" ] && [ "$(cat "$base/logs/desktop/supervisor.stall" 2>/dev/null)" != "$stage_now" ]; then
            printf '%s\n' "$stage_now" >"$base/logs/desktop/supervisor.stall"
            marker_write "running, no progress for ${a}s"
            notify "Aether build may be stalled" "No new package or log output for $((a/60)) minutes."
        fi
        [ -n "$once" ] && exit 0
        sleep "$interval"; continue
    fi
    if grep -q 'PACKAGES_COMPLETE' "$status" 2>/dev/null; then
        say "packages complete"
        if [ ! -f "$base/images/aether-0.3-x86_64-desktop.iso" ]; then
            say "running finish phases (kernel, boot install, ISO)"
            notify "Aether packages complete" "Building the release kernel, installing boot and assembling the ISO."
            bash "$base/desktop/scripts/finish-desktop.sh" >>"$base/logs/desktop/finish.log" 2>&1 || true
        fi
        if [ -f "$base/images/aether-0.3-x86_64-desktop.iso" ]; then
            marker_write "ISO built"
            notify "Aether ISO built" "aether-0.3-x86_64-desktop.iso is ready for boot testing."
            exit 0
        fi
        marker_write "finish phases failed"
        notify "Aether finish phases failed" "See /opt/aether/logs/desktop/finish.log"
        exit 1
    fi
    if [ ! -s "$status" ]; then [ -n "$once" ] && exit 0; sleep "$interval"; continue; fi
    sig=$(signature)
    if [ -s "$failures" ]; then
        if [ "$sig" = "$last_sig" ]; then
            [ "$last_state" != blocked ] && {
                say "blocked on identical failure set $sig; waiting for changed inputs"
                marker_write "blocked"
                notify "Aether build blocked" "See build/desktop/BUILD_STATUS.txt"
                last_state=blocked
            }
            [ -n "$once" ] && exit 0
            sleep "$interval"; continue
        fi
        last_sig=$sig; printf '%s
' "$sig" >"$base/logs/desktop/supervisor.sig"; transient=0; last_state=blocked
        marker_write "blocked on configure failure"
        notify "Aether build blocked" "Fix recorded in build/desktop/BUILD_STATUS.txt."
        say "new failure set $sig; restarting in 10s"
        [ -n "$once" ] && exit 0
        sleep 10
    else
        transient=$((transient+1)); last_state=transient
        if [ "$transient" -gt "$max_transient" ]; then
            say "repeated transient stops ($transient); waiting"
            marker_write "repeated transient stop x$transient"
            [ -n "$once" ] && exit 0
            sleep "$interval"; continue
        fi
        say "transient stop ($transient/$max_transient); restarting"
        [ -n "$once" ] && exit 0
    fi
    running && continue
    [ "$dry" = 1 ] && { say "dry run: would restart the pipeline now"; exit 0; }
    : >"$failures"
    say "starting pipeline"
    setsid nohup bash "$base/desktop/scripts/continue-desktop-build.sh" >>"$base/logs/desktop/pipeline-run.log" 2>&1 </dev/null &
    sleep "$interval"
done
