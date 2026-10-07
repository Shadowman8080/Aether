#!/bin/bash
set -euo pipefail
if [ "${NATIVE_AI_NS:-}" != 1 ]; then exec unshare --mount --net --propagation private env NATIVE_AI_NS=1 bash "$0"; fi
b=/opt/aether/build/next-20261007
q="$b/native-ai-test-$(date +%Y%m%dT%H%M%S)"
mkdir -p "$q"/{upper,work,root}
r="$q/root"
mount -t overlay overlay -o "lowerdir=$b/root,upperdir=$q/upper,workdir=$q/work" "$r"
mount --rbind /dev "$r/dev"; mount --make-rslave "$r/dev"
mount -t proc proc "$r/proc"; mount -t sysfs sysfs "$r/sys"; mount -t tmpfs tmpfs "$r/run"
uid=$(awk -F: '$1=="nimbrel" {print $3}' "$r/etc/passwd")
gid=$(awk -F: '$1=="nimbrel" {print $4}' "$r/etc/passwd")
test -n "$uid"; test -n "$gid"
mkdir -p "$r/run/nimbrel" "$r/run/nimbrel-engine" "$r/var/lib/nimbrel"
chown "$uid:$gid" "$r/run/nimbrel" "$r/run/nimbrel-engine" "$r/var/lib/nimbrel"
chmod 755 "$r/run/nimbrel"; chmod 700 "$r/run/nimbrel-engine" "$r/var/lib/nimbrel"
chroot --userspec="$uid:$gid" "$r" /usr/libexec/nimbrel-engine-start > "$q/engine.log" 2>&1 & engine=$!
chroot --userspec="$uid:$gid" "$r" /usr/bin/python3 /opt/nimbrel/local_server.py > "$q/api.log" 2>&1 & api=$!
cleanup() { kill "$api" "$engine" 2>/dev/null || :; wait "$api" "$engine" 2>/dev/null || :; }
trap cleanup EXIT
python3 - "$r" "$q" <<'PY'
import json,subprocess,sys,time
from pathlib import Path
r,q=map(Path,sys.argv[1:]);start=time.monotonic()
def call(value):
 p=subprocess.run(['chroot','--userspec=1000:1000',str(r),'/usr/bin/nimbrel-client'],input=json.dumps(value),text=True,capture_output=True,timeout=330)
 assert p.returncode==0,p.stdout+p.stderr
 result=json.loads(p.stdout);assert result.get('ok'),result
 return result
for _ in range(90):
 if call({'action':'status'}).get('ready'):break
 time.sleep(2)
else:raise RuntimeError('Model did not become ready')
answer=call({'action':'ask','task':'chat','prompt':'Say hello in one short sentence.','history':[]})
assert answer.get('answer','').strip()
(q/'PASS.json').write_text(json.dumps({'test':'Unmodified native Aether engine/API/client with original 700-token cap; isolated network namespace; unprivileged local client','elapsed_seconds':round(time.monotonic()-start,2),'nonempty_answer':True},indent=2))
print('NATIVE_AI_PASS',q,flush=True)
PY
