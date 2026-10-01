#!/usr/bin/env python3
from pathlib import Path
import json,runpy
ns=runpy.run_path('/recipes/scripts/build-desktop-foundation.py');build=ns['build']
manifest=json.loads(Path('/recipes/configs/sources.json').read_text())
# API documentation and mobile-modem integration are optional in the desktop image.
skip={'kapidox','modemmanager-qt'}
for item in manifest:
 if item['group']!='frameworks' or item['key'] in skip: continue
 options=['-DBUILD_PYTHON_BINDINGS=OFF']
 if item['key']=='extra-cmake-modules': options+=['-DBUILD_HTML_DOCS=OFF','-DBUILD_MAN_DOCS=OFF']
 if item['key']=='breeze-icons': options+=['-DWITH_ICON_GENERATION=OFF']
 build(item['key'],opts=options)
build('pulseaudio-qt')
build('kirigami-addons')
build('kquickimageeditor')
print('KDE Frameworks stage completed.',flush=True)
