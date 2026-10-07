#!/usr/bin/env python3
"""Package USB components for disposable guest testing, without daemon activation."""
import hashlib,json,shutil,subprocess
from pathlib import Path
b=Path('/opt/aether/build/next-20261007');payload=b/'usb-payload';payload.mkdir(exist_ok=True)
records=[]
for key,version,depends in [('abseil','20250512.1-1aether1','glibc, gcc'),('libqb','2.0.10-1aether1','glibc'),('protobuf','36.2-1aether1','glibc, gcc, abseil'),('usbguard','1.1.4-1aether1','glibc, gcc, libqb, protobuf')]:
 tree=b/'packages'/('tree-'+key);tree.mkdir(exist_ok=True)
 subprocess.run(['rsync','-a','--delete',str(b/'stage'/key)+'/',str(tree)+'/'],check=True)
 control=tree/'DEBIAN';control.mkdir()
 (control/'control').write_text(f'Package: {key}\nVersion: {version}\nArchitecture: amd64\nMaintainer: Aether Linux developers\nDepends: {depends}\nDescription: Source-built Aether USB authorization component ({key})\n')
 configs=sorted('/'+str(p.relative_to(tree)) for p in (tree/'etc').rglob('*') if p.is_file() and not p.is_symlink()) if (tree/'etc').exists() else []
 if configs:(control/'conffiles').write_text('\n'.join(configs)+'\n')
 archive=payload/f'{key}_{version}_amd64.deb';subprocess.run(['dpkg-deb','--build','--root-owner-group',str(tree),str(archive)],check=True)
 records.append({'archive':archive.name,'sha256':hashlib.file_digest(archive.open('rb'),'sha256').hexdigest()})
tree=b/'packages/tree-aether-usb-protection';tree.mkdir(exist_ok=True)
def put(source,dest,mode):
 target=tree/dest;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((b/'project/src/security'/source).read_bytes().replace(b'\r\n',b'\n'));target.chmod(mode)
put('aether-usbguard','usr/bin/aether-usbguard',0o755)
put('aether-usbguard-recover.service','usr/lib/systemd/system/aether-usbguard-recover.service',0o644)
put('usbguard-aether.conf','usr/lib/systemd/system/usbguard.service.d/10-aether-recovery.conf',0o644)
control=tree/'DEBIAN';control.mkdir(exist_ok=True)
(control/'control').write_text('Package: aether-usb-protection\nVersion: 0.3.3~dev20261007-1\nArchitecture: amd64\nMaintainer: Aether Linux developers\nDepends: usbguard, python, systemd\nDescription: Opt-in Aether USB policy trial and interrupted-trial recovery\n')
(control/'postinst').write_text('''#!/bin/sh
set -eu
[ "$1" = configure ] || exit 0
mkdir -p /etc/systemd/system/multi-user.target.wants
ln -sfn /usr/lib/systemd/system/aether-usbguard-recover.service /etc/systemd/system/multi-user.target.wants/aether-usbguard-recover.service
# USBGuard itself is never enabled or started by package installation.
''');(control/'postinst').chmod(0o755)
archive=payload/'aether-usb-protection_0.3.3~dev20261007-1_amd64.deb'
subprocess.run(['dpkg-deb','--build','--root-owner-group',str(tree),str(archive)],check=True)
records.append({'archive':archive.name,'sha256':hashlib.file_digest(archive.open('rb'),'sha256').hexdigest()})
(payload/'packages.json').write_text(json.dumps(records,indent=2)+'\n')
print('USB test packages prepared; candidate root unchanged')
