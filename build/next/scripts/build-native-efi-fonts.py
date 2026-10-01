#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,os,subprocess,tarfile
manifest={i['key']:i for i in json.loads(Path('/recipes/configs/native-guest-sources.json').read_text())}
extra={i['filename']:i for i in json.loads(Path('/recipes/configs/native-guest-extras.json').read_text())}
cache=Path('/sources/native-guest-cache')
for name,item in extra.items():
 assert hashlib.sha256((cache/name).read_bytes()).hexdigest()==item['sha256']
work=Path('/build/efi-fonts')
work.mkdir(exist_ok=True)
fonts=extra['dejavu-fonts-ttf-2.37.tar.bz2']
with tarfile.open(cache/fonts['filename']) as t: t.extractall(work,filter='data')
subprocess.run(['install','-d','/usr/share/fonts/dejavu','/usr/share/licenses/dejavu'],check=True)
for font in (work/'dejavu-fonts-ttf-2.37/ttf').glob('*.ttf'):
 subprocess.run(['install','-m644',str(font),'/usr/share/fonts/dejavu/'],check=True)
subprocess.run(['install','-m644',str(work/'dejavu-fonts-ttf-2.37/LICENSE'),'/usr/share/licenses/dejavu/'],check=True)
subprocess.run(['fc-cache','-f'],check=True)
for key,opts in [('efivar',['ENABLE_DOCS=0','LIBDIR=/usr/lib']),('efibootmgr',['EFIDIR=Aether','EFI_LOADER=grubx64.efi'])]:
 stamp=Path('/build/done')/key
 if stamp.exists(): continue
 item=manifest[key]
 archive=cache/item['filename']
 assert hashlib.sha256(archive.read_bytes()).hexdigest()==item['sha256']
 dest=work/key
 dest.mkdir(exist_ok=True)
 if not (dest/'.extracted').exists():
  with tarfile.open(archive) as t: t.extractall(dest,filter='data')
  (dest/'.extracted').touch()
 src=next(p for p in dest.iterdir() if p.is_dir())
 if key=='efivar' and not (src/'.patched').exists():
  subprocess.run(['patch','-Np1','-i',str(cache/'efivar-39-upstream_fixes-1.patch')],cwd=src,check=True)
  (src/'.patched').touch()
 subprocess.run(['make','-j'+str(os.cpu_count()),*opts],cwd=src,check=True)
 subprocess.run(['make','install',*opts],cwd=src,check=True)
 subprocess.run(['ldconfig'],check=True)
 stamp.touch()
