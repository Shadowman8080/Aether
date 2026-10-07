#!/usr/bin/env python3
"""Install guest-tested USB packages into the disposable candidate only."""
import hashlib,json,subprocess
from pathlib import Path
b=Path('/opt/aether/build/next-20261007');root=b/'root'
assert (b/'candidate-copy-complete').is_file()
assert 'ID=aether' in (root/'etc/os-release').read_text().splitlines()
assert (b/'test-usb-guest-precision/PASS').is_file(), 'USB guest test has not passed'
payload=b/'usb-payload';records=json.loads((payload/'packages.json').read_text())
archives=[]
for item in records:
 name=item['archive'];assert Path(name).name==name
 archive=payload/name
 assert hashlib.file_digest(archive.open('rb'),'sha256').hexdigest()==item['sha256']
 archives.append(str(archive))
subprocess.run(['dpkg','--root='+str(root),'--force-confdef','--force-confold','--install',*archives],check=True)
subprocess.run(['chroot',str(root),'ldconfig'],check=True)
result=subprocess.run(['systemctl','--root='+str(root),'is-enabled','--quiet','usbguard.service'])
assert result.returncode==1, 'USBGuard must remain disabled by default'
(b/'usb-candidate-packages.json').write_text(json.dumps(records,indent=2)+'\n')
print('USB packages installed in disposable candidate; protection disabled')
