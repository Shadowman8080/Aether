#!/usr/bin/env python3
"""Produce a metadata-preserving system delta; omit machine/account identities."""
from pathlib import Path
import hashlib, json, os, stat, subprocess

old=Path('/opt/aether/security-original')
new=Path('/opt/aether/security-system')
out=Path('/opt/aether/build/security-system-delta')
out.mkdir(exist_ok=True)
excluded={'etc/passwd','etc/passwd-','etc/group','etc/group-','etc/shadow','etc/shadow-',
 'etc/gshadow','etc/gshadow-','etc/machine-id','etc/hostname','etc/fstab','etc/crypttab',
 'boot/grub/grub.cfg','etc/adjtime'}
def skip(p):
 return p in excluded or p.startswith(('etc/NetworkManager/system-connections/', 'etc/ssh/ssh_host_'))
def signature(p):
 try:s=p.lstat()
 except FileNotFoundError:return None
 result={'mode':stat.S_IMODE(s.st_mode),'uid':s.st_uid,'gid':s.st_gid}
 if stat.S_ISLNK(s.st_mode):result.update(type='link',target=os.readlink(p))
 elif stat.S_ISREG(s.st_mode):
  h=hashlib.sha256()
  with p.open('rb') as f:
   for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
  result.update(type='file',sha256=h.hexdigest())
 elif stat.S_ISDIR(s.st_mode):result.update(type='dir')
 else:raise RuntimeError('Unexpected special system file: '+str(p))
 return result
def inventory(root):
 result={}
 for top in ('usr','etc','boot'):
  for parent,dirs,files in os.walk(root/top,followlinks=False):
   for name in dirs+files:
    p=Path(parent)/name;rel=p.relative_to(root).as_posix()
    if not skip(rel):result[rel]=signature(p)
 return result
assert old.is_mount() and new.is_mount()
a,b=inventory(old),inventory(new)
changes={p:{'before':a.get(p),'after':b.get(p)} for p in sorted(a.keys()|b.keys()) if a.get(p)!=b.get(p)}
(out/'manifest.json').write_text(json.dumps(changes,indent=2)+'\n')
(out/'files.list').write_bytes(b''.join(p.encode()+b'\0' for p,v in changes.items() if v['after'] is not None))
subprocess.run(['tar','--xattrs','--acls','--numeric-owner','--no-recursion','-C',str(new),'--null','-T',str(out/'files.list'),'-cf',str(out/'files.tar')],check=True)
print(json.dumps({'changed_paths':len(changes),'deleted_paths':[p for p,v in changes.items() if v['after'] is None],'archive_bytes':(out/'files.tar').stat().st_size}),flush=True)
