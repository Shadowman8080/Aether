#!/usr/bin/env python3
"""Package staged native builds and install only into the disposable candidate."""
import hashlib,json,os,shutil,subprocess
from pathlib import Path
b=Path('/opt/aether/build/next-20261007');root=b/'root'
assert (b/'candidate-copy-complete').is_file() and 'ID=aether' in (root/'etc/os-release').read_text().splitlines()
packages=[('libcbor','libcbor','0.14.0-1aether1','glibc'),('libfido2','libfido2','1.17.0-1aether1','glibc, libcbor'),('tpm2-tss','tpm2-tss','4.2.0-1aether1','glibc'),('apparmor','libapparmor','4.1.8-1aether1','glibc'),('devmapper','device-mapper','2.03.42-1aether1','glibc'),('cryptsetup','cryptsetup','2.8.7-2aether1','glibc, device-mapper'),('boot-python','aether-boot-python','20261007-1','python'),('systemd','systemd','261.2-2aether1','glibc, libfido2, tpm2-tss, libapparmor, cryptsetup')]
receipt=[]
for stage,name,version,depends in packages:
 source=b/'stage'/stage;dest=b/'packages'/('tree-'+name)
 assert source.is_dir()
 dest.mkdir(exist_ok=True)
 subprocess.run(['rsync','-a','--delete',str(source)+'/',str(dest)+'/'],check=True)
 if name=='systemd':
  # Aether's separate hwdata package owns this database; do not seize its files.
  hwdb=dest/'usr/lib/udev/hwdb.d'
  if hwdb.exists():shutil.rmtree(hwdb)
  depends+=', hwdata'
 control=dest/'DEBIAN';control.mkdir(exist_ok=True)
 (control/'control').write_text(f'Package: {name}\nVersion: {version}\nArchitecture: amd64\nMaintainer: Aether Linux developers\nDepends: {depends}\nDescription: Source-built Aether security foundation ({name})\n')
 configs=sorted('/'+str(p.relative_to(dest)) for p in (dest/'etc').rglob('*') if p.is_file() and not p.is_symlink()) if (dest/'etc').exists() else []
 if configs:(control/'conffiles').write_text('\n'.join(configs)+'\n')
 archive=b/'packages'/f'{name}_{version}_amd64.deb'
 subprocess.run(['dpkg-deb','--build','--root-owner-group',str(dest),str(archive)],check=True)
 subprocess.run(['dpkg','--root='+str(root),'--force-confdef','--force-confold','--install',str(archive)],check=True)
 receipt.append({'package':name,'version':version,'archive':archive.name,'sha256':hashlib.file_digest(archive.open('rb'),'sha256').hexdigest()})
subprocess.run(['chroot',str(root),'ldconfig'],check=True)
version=subprocess.check_output(['chroot',str(root),'/usr/lib/systemd/systemd','--version'],text=True)
for feature in ('+APPARMOR','+SECCOMP','+FIDO2','+TPM2','+LIBCRYPTSETUP','+LIBCRYPTSETUP_PLUGINS'):assert feature in version,feature
(b/'foundation-packages.json').write_text(json.dumps({'packages':receipt,'systemd':version,'boot_verified':False},indent=2)+'\n')
print('CANDIDATE_FOUNDATION_INSTALLED; BOOT_VERIFICATION_PENDING')
