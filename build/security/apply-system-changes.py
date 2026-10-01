#!/usr/bin/env python3
"""Apply verified system changes to the offline copy of the user's disk."""
from pathlib import Path
import hashlib, json, os, stat, subprocess, sys
root=Path('/opt/aether/security-user-system')
delta=Path('/opt/aether/build/security-system-delta')
assert root.is_mount()
assert 'ID=aether' in (root/'etc/os-release').read_text().splitlines()
changes=json.loads((delta/'manifest.json').read_text())
def signature(p):
 try:s=p.lstat()
 except FileNotFoundError:return None
 r={'mode':stat.S_IMODE(s.st_mode),'uid':s.st_uid,'gid':s.st_gid}
 if stat.S_ISLNK(s.st_mode):r.update(type='link',target=os.readlink(p))
 elif stat.S_ISREG(s.st_mode):
  h=hashlib.sha256()
  with p.open('rb') as f:
   for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
  r.update(type='file',sha256=h.hexdigest())
 elif stat.S_ISDIR(s.st_mode):r.update(type='dir')
 else:raise RuntimeError('Special file '+str(p))
 return r
conflicts=[]
for name,v in changes.items():
 p=Path(name)
 assert not p.is_absolute() and '..' not in p.parts
 assert p.parts[0] in ('etc','usr','boot')
 for ancestor in p.parents:
  if ancestor==Path('.'):continue
  if (root/ancestor).is_symlink():raise RuntimeError('Symlink ancestor: '+str(ancestor))
 actual=signature(root/p)
 if actual not in (v['before'],v['after']):conflicts.append(name)
if conflicts:raise SystemExit('User changes require reconciliation: '+json.dumps(conflicts))
print('SYSTEM_DELTA_PREFLIGHT_PASS '+str(len(changes)),flush=True)
if '--apply' not in sys.argv:sys.exit(0)
identities={p:signature(root/p) for p in ('etc/passwd','etc/shadow','etc/machine-id','etc/hostname','etc/fstab')}
subprocess.run(['tar','--xattrs','--acls','--numeric-owner','-C',str(root),'-xpf',str(delta/'files.tar')],check=True)
for name,v in sorted(changes.items(),key=lambda item:len(Path(item[0]).parts),reverse=True):
 if v['after'] is None:
  p=root/name
  if p.is_dir() and not p.is_symlink():p.rmdir()
  else:p.unlink(missing_ok=True)
for name,v in changes.items():
 if signature(root/name)!=v['after']:raise RuntimeError('Post-copy mismatch: '+name)
for p,v in identities.items():assert signature(root/p)==v,'Identity unexpectedly changed: '+p
print('SYSTEM_DELTA_COPY_VERIFIED',flush=True)
