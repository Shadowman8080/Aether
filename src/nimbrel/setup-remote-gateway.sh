#!/bin/bash
set -euo pipefail
base=/opt/aether/build/nimbrel
test -s "$base/server.py"
id nimbrel >/dev/null 2>&1 || useradd --system --home-dir /var/lib/nimbrel --shell /usr/sbin/nologin nimbrel
install -d -m755 /opt/nimbrel /opt/nimbrel/engine
install -d -o nimbrel -g nimbrel -m700 /var/lib/nimbrel
install -m644 "$base/server.py" /opt/nimbrel/server.py
install -m755 "$base/admin.py" /opt/nimbrel/admin.py
for file in /opt/aether/build/llama-host/bin/*; do cp -a "$file" /opt/nimbrel/engine/; done
python3 - <<'PY'
from pathlib import Path
import hashlib,json,shutil,os,pwd
m=json.loads(Path('/opt/aether/next/assistant/model.json').read_text())
source=Path('/opt/aether/build/assistant-test-data/aether-assistant/models')/m['filename']
h=hashlib.sha256()
with source.open('rb') as f:
 for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
assert h.hexdigest()==m['sha256']
dest=Path('/var/lib/nimbrel/model.gguf')
if not dest.exists():shutil.copyfile(source,dest)
assert dest.stat().st_size==m['bytes']
user=pwd.getpwnam('nimbrel');os.chown(dest,user.pw_uid,user.pw_gid);dest.chmod(0o600)
Path('/var/lib/nimbrel/model.json').write_text(json.dumps(m,indent=2))
os.chown('/var/lib/nimbrel/model.json',user.pw_uid,user.pw_gid)
PY
if [ ! -f /var/lib/nimbrel/server.key ]; then
 openssl req -x509 -newkey rsa:3072 -sha256 -nodes -days 365 \
  -keyout /var/lib/nimbrel/server.key -out /var/lib/nimbrel/server.crt \
  -subj /CN=Nimbrel-Test-Server -addext subjectAltName=IP:192.168.48.135,IP:127.0.0.1 >/dev/null 2>&1
 chown nimbrel:nimbrel /var/lib/nimbrel/server.{key,crt}
 chmod 600 /var/lib/nimbrel/server.key
 chmod 644 /var/lib/nimbrel/server.crt
fi
cat >/usr/local/sbin/nimbrel-server-admin <<'EOF'
#!/bin/sh
exec /usr/bin/python3 /opt/nimbrel/admin.py "$@"
EOF
chmod 755 /usr/local/sbin/nimbrel-server-admin
cat >/etc/systemd/system/nimbrel-engine.service <<'EOF'
[Unit]
Description=Nimbrel private CPU inference engine
After=network.target
[Service]
User=nimbrel
Group=nimbrel
Environment=LD_LIBRARY_PATH=/opt/nimbrel/engine
ExecStart=/opt/nimbrel/engine/llama-server --model /var/lib/nimbrel/model.gguf --alias nimbrel-small --host 127.0.0.1 --port 8088 --ctx-size 8192 --threads 8 --threads-batch 16 --parallel 1 --n-gpu-layers 0 --log-disable
Restart=on-failure
RestartSec=5
NoNewPrivileges=yes
PrivateTmp=yes
PrivateDevices=yes
ProtectSystem=strict
ProtectHome=yes
ProtectKernelTunables=yes
ProtectControlGroups=yes
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
MemoryMax=4G
TasksMax=128
UMask=0077
[Install]
WantedBy=multi-user.target
EOF
cat >/etc/systemd/system/nimbrel-gateway.service <<'EOF'
[Unit]
Description=Nimbrel authenticated private AI gateway
After=network-online.target nimbrel-engine.service
Wants=network-online.target nimbrel-engine.service
[Service]
User=nimbrel
Group=nimbrel
ExecStart=/usr/bin/python3 /opt/nimbrel/server.py --state /var/lib/nimbrel --certificate /var/lib/nimbrel/server.crt --key /var/lib/nimbrel/server.key --host 192.168.48.135 --port 9443 --model nimbrel-small
Restart=on-failure
RestartSec=5
NoNewPrivileges=yes
PrivateTmp=yes
PrivateDevices=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/var/lib/nimbrel
ProtectKernelTunables=yes
ProtectControlGroups=yes
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
IPAddressDeny=any
IPAddressAllow=localhost
IPAddressAllow=192.168.48.0/24
MemoryMax=256M
TasksMax=64
UMask=0077
[Install]
WantedBy=multi-user.target
EOF
python3 -m py_compile /opt/nimbrel/server.py /opt/nimbrel/admin.py
systemd-analyze verify /etc/systemd/system/nimbrel-engine.service /etc/systemd/system/nimbrel-gateway.service
systemctl daemon-reload
systemctl enable --now nimbrel-engine.service nimbrel-gateway.service
systemctl is-active nimbrel-engine.service nimbrel-gateway.service
