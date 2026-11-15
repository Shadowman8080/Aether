#!/usr/bin/env python3
"""Core Plasma desktop; run after foundation, dependencies and Frameworks."""
import hashlib
import runpy
import shutil
from pathlib import Path

_namespace = runpy.run_path('/recipes/scripts/build-desktop-foundation.py')
build = _namespace['build']
manifest = _namespace['manifest']

def plasma(name, *options):
    build(name, opts=['-DBUILD_QT5=OFF', '-DBUILD_QT6=ON', *options])

# Plasma Workspace needs the X11 ICE/SM session layer and Xft, which a bare LFS
# root does not provide.
for name in ('libICE', 'libSM', 'libXft'):
    build(name, 'autoconf')

# spectacle links libtesseract unconditionally (CMakeLists.txt:111), and its OCR
# action needs a language model at runtime as well.
build('leptonica', opts=['-DBUILD_PROG=OFF', '-DBUILD_SHARED_LIBS=ON',
                         '-DCMAKE_POLICY_VERSION_MINIMUM=3.5'])
build('tesseract', opts=['-DBUILD_SHARED_LIBS=ON', '-DBUILD_TRAINING_TOOLS=OFF',
                         '-DBUILD_TESTS=OFF', '-DINSTALL_LANGDATA=OFF'])
cache = Path('/sources/desktop-cache')
tessdata = Path('/usr/share/tessdata')
tessdata.mkdir(parents=True, exist_ok=True)
for key, name in (('tessdata-fast-eng', 'eng.traineddata'),
                  ('tessdata-fast-osd', 'osd.traineddata')):
    item = manifest[key]
    source = cache / item['filename']
    assert hashlib.sha256(source.read_bytes()).hexdigest() == item['sha256']
    shutil.copy2(source, tessdata / name)
licenses = Path('/usr/share/licenses/tesseract')
licenses.mkdir(parents=True, exist_ok=True)
shutil.copy2(cache / manifest['tessdata-fast-license']['filename'],
             licenses / 'tessdata_fast-LICENSE')

for name in ('kdecoration', 'libkscreen', 'libksysguard', 'breeze', 'breeze-gtk',
             'layer-shell-qt', 'plasma-activities', 'kactivitymanagerd', 'libplasma', 'kscreenlocker',
             'kglobalacceld', 'kwayland', 'aurorae', 'knighttime', 'kpipewire',
             'kwin', 'kwin-x11', 'plasma5support', 'plasma-activities-stats'):
    plasma(name)
plasma('plasma-workspace', '-DWITH_X11_SESSION=ON', '-DPACKAGEKIT_OFFLINE_UPDATES=OFF',
       '-DUBUNTU_PACKAGEKIT=OFF')
for name in ('bluedevil', 'kde-gtk-config', 'kmenuedit', 'kscreen', 'kwallet-pam',
             'kwrited', 'milou'):
    plasma(name)
# OpenConnect's embedded authentication browser is a separate optional dependency.
plasma('plasma-nm', '-DBUILD_OPENCONNECT=OFF')
for name in ('plasma-pa', 'polkit-kde-agent', 'powerdevil', 'plasma-desktop',
             'sddm-kcm', 'xdg-desktop-portal-kde', 'kde-cli-tools', 'systemsettings',
             'qqc2-breeze-style', 'ksystemstats', 'plasma-systemmonitor',
             'ocean-sound-theme'):
    plasma(name)
plasma('kdeplasma-addons', '-DBUILD_KAMELEON=OFF')
plasma('print-manager', '-DSCP_INSTALL=OFF')
plasma('spectacle')
plasma('kinfocenter')
print('Core Plasma packages built. Session integration and boot tests remain required.', flush=True)
