#!/usr/bin/env python3
from pathlib import Path
import json,runpy
ns=runpy.run_path('/recipes/scripts/build-desktop-foundation.py');build=ns['build']
manifest=json.loads(Path('/recipes/configs/sources.json').read_text())
# API documentation is optional; ModemManagerQt is not, because plasma-nm
# requires it at configure time with no opt-out.
skip={'kapidox'}
# kdoctools encodes doc URIs with Perl's URI::Escape, which is not in core Perl.
build('uri','perl')
build('zxing','cmake',['-DBUILD_SHARED_LIBS=ON','-DBUILD_EXAMPLES=OFF','-DBUILD_BLACKBOX_TESTS=OFF','-DBUILD_UNIT_TESTS=OFF'])
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
