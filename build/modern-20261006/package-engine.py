#!/usr/bin/env python3
"""Package the baseline CPU engine separately from the desktop integration."""
import hashlib,json,shutil,subprocess
from pathlib import Path
b=Path('/opt/aether/build/modern-20261006');p=b/'packages/nimbrel-engine'
dest=p/'opt/nimbrel/engine';dest.parent.mkdir(parents=True,exist_ok=True)
shutil.copytree(b/'stage/opt/nimbrel/engine',dest,symlinks=True,dirs_exist_ok=True)
launcher=p/'usr/libexec/nimbrel-engine-start';launcher.parent.mkdir(parents=True,exist_ok=True)
launcher.write_bytes((b/'project/src/nimbrel/nimbrel-engine-start').read_bytes().replace(b'\r\n',b'\n'));launcher.chmod(0o755)
license=p/'usr/share/doc/nimbrel-engine/LICENSE';license.parent.mkdir(parents=True,exist_ok=True)
shutil.copyfile('/opt/aether/sources/llama.cpp/LICENSE',license)
control=p/'DEBIAN';control.mkdir(exist_ok=True)
(control/'control').write_text('Package: nimbrel-engine\nVersion: 0.5.0~git2145525a-1aether1\nArchitecture: amd64\nMaintainer: Aether Linux developers\nDepends: glibc, gcc, openssl\nDescription: Pinned llama.cpp inference engine for baseline x86-64\n')
archive=b/'packages/nimbrel-engine_0.5.0~git2145525a-1aether1_amd64.deb'
subprocess.run(['dpkg-deb','--build','--root-owner-group',str(p),str(archive)],check=True)
subprocess.run(['dpkg','--root='+str(b/'root'),'--install',str(archive)],check=True)
(b/'engine-package.json').write_text(json.dumps({'archive':archive.name,'sha256':hashlib.file_digest(archive.open('rb'),'sha256').hexdigest(),'commit':'2145525a4081d66ff1a87cf43ef809f95a85ac0c','optional_cpu_instructions':False},indent=2)+'\n')
