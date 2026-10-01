#!/usr/bin/env python3
"""Native builds; stage the checked Plymouth tarball in /build/experience-cache."""
from pathlib import Path
import hashlib, os, shutil, subprocess, tarfile
archive=Path('/build/experience-cache/plymouth_24.004.60.orig.tar.xz')
assert hashlib.sha256(archive.read_bytes()).hexdigest()=='f3f7841358c98f5e7b06a9eedbdd5e6882fd9f38bbd14a767fb083e3b55b1c34'
source=Path('/build/experience-plymouth-source')
if not source.exists():
    source.mkdir()
    with tarfile.open(archive) as tar: tar.extractall(source,filter='data')
source=next(source.glob('plymouth-*'))
def run(args): subprocess.run(args,check=True)
if not Path('/build/experience-plymouth/build.ninja').exists():
    run(['meson','setup','/build/experience-plymouth',str(source),'--prefix=/usr','--libdir=lib','--buildtype=release','-Ddocs=false','-Dgtk=disabled','-Drelease-file=/etc/os-release'])
run(['ninja','-C','/build/experience-plymouth','-j',str(os.cpu_count())])
run(['ninja','-C','/build/experience-plymouth','install'])
run(['cmake','-S','/recipes/installer','-B','/build/installer','-G','Ninja','-DCMAKE_BUILD_TYPE=Release','-DCMAKE_INSTALL_PREFIX=/usr'])
run(['cmake','--build','/build/installer','--parallel',str(os.cpu_count())])
run(['cmake','--install','/build/installer'])
theme=Path('/usr/share/plymouth/themes/aether');theme.mkdir(parents=True,exist_ok=True)
run(['env','QT_QPA_PLATFORM=offscreen','/build/installer/aether-render-svg','/usr/share/icons/hicolor/scalable/apps/aether-logo.svg',str(theme/'logo.png')])
run(['env','QT_QPA_PLATFORM=offscreen','/build/installer/aether-render-svg',str(theme/'dot.svg'),str(theme/'dot.png'),'6'])
print('AETHER_EXPERIENCE_BUILD_PASS')
