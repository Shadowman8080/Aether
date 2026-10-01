#!/usr/bin/env python3
import runpy,re,tarfile
state=runpy.run_path('/recipes/scripts/build-native-packages.py')
build=state['build']
build('popt','autoconf')
build('which','autoconf')
for key in ['libsigc','glibmm','cairomm','pangomm','atkmm','gtkmm3']:
 item=state['manifest'][key]
 with tarfile.open('/sources/native-guest-cache/'+item['filename']) as archive:
  text='\n'.join(archive.extractfile(m).read().decode() for m in archive.getmembers() if m.name.count('/')==1 and m.name.rsplit('/',1)[-1] in ('meson.options','meson_options.txt'))
 options=set(re.findall(r'''option\(\s*['"]([^'"]+)''',text))
 flags=['-D'+name+'=false' for name in ('build-documentation','build-examples','build-tests') if name in options]
 build(key,opts=flags)
print('Native GTK C++ bindings complete.',flush=True)
