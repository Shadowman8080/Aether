#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,subprocess
base=Path('/opt/aether')
cache=base/'sources/native-guest-cache'
specs=[
 ('dejavu-fonts-ttf-2.37.tar.bz2','https://downloads.sourceforge.net/dejavu/dejavu-fonts-ttf-2.37.tar.bz2','fa9ca4d13871dd122f61258a80d01751d603b4d3ee14095d65453b4e846e17d7'),
 ('efivar-39-upstream_fixes-1.patch','https://www.linuxfromscratch.org/blfs/downloads/13.1-systemd/patches/efivar-39-upstream_fixes-1.patch',None),
]
result=[]
for name,url,digest in specs:
 dest=cache/name
 if not dest.exists():
  subprocess.run(['curl','-fL','--retry','3','-o',str(dest)+'.partial',url],check=True)
  Path(str(dest)+'.partial').rename(dest)
 actual=hashlib.sha256(dest.read_bytes()).hexdigest()
 if digest: assert actual==digest,name
 result.append(dict(filename=name,url=url,sha256=actual))
(base/'next/configs/native-guest-extras.json').write_text(json.dumps(result,indent=2)+'\n')
