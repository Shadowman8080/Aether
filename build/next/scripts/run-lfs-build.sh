#!/bin/bash
set -euo pipefail
export TERM=xterm
cd /opt/aether/system/jhalfs
date -u '+STARTED %FT%TZ' > /opt/aether/logs/next/base.status
set +e
script -q -e -c 'stty rows 40 cols 120; exec make' /dev/null
result=$?
printf 'EXIT %s\n' "$result" >> /opt/aether/logs/next/base.status
date -u '+FINISHED %FT%TZ' >> /opt/aether/logs/next/base.status
exit "$result"
