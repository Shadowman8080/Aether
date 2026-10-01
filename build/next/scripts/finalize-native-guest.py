#!/usr/bin/env python3
from pathlib import Path
import shutil
base=Path('/opt/aether')
root=base/'guest-system'
assert (root/'etc/os-release').read_text().find('VERSION_ID=0.2.1') >= 0
ignore=base/'.gitignore'
if '/guest-system/' not in ignore.read_text():
 with ignore.open('a') as f: f.write('\n/guest-system/\n')
licenses=root/'usr/share/licenses/native-guest'
licenses.mkdir(parents=True,exist_ok=True)
for package in (base/'build/native-guest/packages').iterdir():
 if not package.is_dir(): continue
 for source in package.iterdir():
  if not source.is_dir(): continue
  for f in source.iterdir():
   if f.is_file() and (f.name.upper().startswith(('COPYING','LICENSE','LICENCE','COPYRIGHT'))):
    dest=licenses/package.name/f.name
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(f,dest)
for f in (base/'build/native-guest/vmtools').glob('COPYING*'):
 if f.is_file():
  dest=licenses/'open-vm-tools'/f.name
  dest.parent.mkdir(parents=True,exist_ok=True)
  shutil.copy2(f,dest)
assert not (root/'etc/sudoers.d/aether-source-build').exists()
print('Collected package license files and verified temporary build sudo access is absent.')
