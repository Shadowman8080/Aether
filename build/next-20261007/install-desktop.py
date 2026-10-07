#!/usr/bin/env python3
"""Update the complete experience package in the disposable candidate."""
import hashlib,json,subprocess
from pathlib import Path
b=Path('/opt/aether/build/next-20261007');root=b/'root';source=b/'project/src'
assert (b/'candidate-copy-complete').exists()
package=b/'packages/tree-aether-experience';package.mkdir(exist_ok=True)
subprocess.run(['rsync','-a','--delete','/opt/aether/build/modern-20261006/packages/aether-experience/',str(package)+'/'],check=True)
def put(origin,name,mode=0o755):
 target=package/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(origin.read_bytes().replace(b'\r\n',b'\n'));target.chmod(mode)
# ELF bytes must not undergo text newline normalization.
import shutil
shutil.copy2(b/'stage/controlcenter/usr/bin/aether-settings',package/'usr/bin/aether-settings')
for origin,name in [('controlcenter/diagnostics.py','usr/bin/aether-diagnostics'),('controlcenter/aether-system-admin','usr/libexec/aether-system-admin'),('security/aether-firewall','usr/bin/aether-firewall'),('security/90-aether-network-profile','etc/NetworkManager/dispatcher.d/90-aether-network-profile')]:put(source/origin,name)
for directory in ('pre-up.d','pre-down.d'):
 link=package/'etc/NetworkManager/dispatcher.d'/directory/'90-aether-network-profile';link.parent.mkdir(exist_ok=True);link.symlink_to('../90-aether-network-profile')
control=package/'DEBIAN/control';control.write_text(control.read_text().replace('0.3.2~dev20261006-1','0.3.3~dev20261007-1'))
configs=package/'DEBIAN/conffiles';configs.write_text(configs.read_text()+'/etc/NetworkManager/dispatcher.d/90-aether-network-profile\n')
archive=b/'packages/aether-experience_0.3.3~dev20261007-1_amd64.deb'
subprocess.run(['dpkg-deb','--build','--root-owner-group',str(package),str(archive)],check=True)
subprocess.run(['dpkg','--root='+str(root),'--force-confdef','--force-confold','--install',str(archive)],check=True)
(b/'experience-package.json').write_text(json.dumps({'archive':archive.name,'sha256':hashlib.file_digest(archive.open('rb'),'sha256').hexdigest()},indent=2)+'\n')
