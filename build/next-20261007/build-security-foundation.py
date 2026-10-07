#!/usr/bin/env python3
"""Build source-pinned authentication dependencies in the Aether build root."""
from pathlib import Path
import hashlib,json,os,subprocess
b=Path('/next');records={v['key']:v for v in json.loads((b/'sources.lock.json').read_text())}
assert 'ID=aether' in Path('/etc/os-release').read_text()
env={**os.environ,'CFLAGS':'-O2 -pipe -march=x86-64 -mtune=generic -fstack-protector-strong -D_FORTIFY_SOURCE=3','CXXFLAGS':'-O2 -pipe -march=x86-64 -mtune=generic -fstack-protector-strong -D_FORTIFY_SOURCE=3','LDFLAGS':'-Wl,-z,relro,-z,now'}
jobs=str(os.cpu_count())
def run(args,cwd,extra=None):
 print('RUN',args,flush=True);subprocess.run(args,cwd=cwd,env={**env,**(extra or {})},check=True)
for key in ('libcbor','libfido2','tpm2-tss'):
 record=records[key];archive=b/'sources'/record['archive']
 with archive.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==record['sha256']
 if (b/'logs'/(key+'.done')).exists():continue
 src=next(p for p in (b/'inspect'/key).iterdir() if p.is_dir());obj=b/'obj'/key;obj.mkdir(exist_ok=True);stage=b/'stage'/key;stage.mkdir(exist_ok=True)
 if key in ('libcbor','libfido2'):
  opts=['-DBUILD_SHARED_LIBS=ON','-DBUILD_STATIC_LIBS=OFF','-DBUILD_EXAMPLES=OFF'] if key=='libfido2' else ['-DBUILD_SHARED_LIBS=ON','-DWITH_EXAMPLES=OFF','-DWITH_TESTS=OFF']
  run(['cmake','-S',str(src),'-B',str(obj),'-DCMAKE_BUILD_TYPE=Release','-DCMAKE_INSTALL_PREFIX=/usr','-DCMAKE_INSTALL_LIBDIR=lib','-DCMAKE_C_FLAGS='+env['CFLAGS'].replace(' -D_FORTIFY_SOURCE=3','') if key=='libfido2' else '-DCMAKE_C_FLAGS='+env['CFLAGS'],*opts],b)
  run(['cmake','--build',str(obj),'--parallel',jobs],b)
  run(['cmake','--install',str(obj)],b,{'DESTDIR':str(stage)})
  run(['cmake','--install',str(obj)],b)
 else:
  run([str(src/'configure'),'--prefix=/usr','--libdir=/usr/lib','--sysconfdir=/etc','--localstatedir=/var','--disable-static','--disable-doxygen-doc','--with-udevrulesdir=/usr/lib/udev/rules.d','--with-sysusersdir=/usr/lib/sysusers.d','--with-tmpfilesdir=/usr/lib/tmpfiles.d'],obj)
  run(['make','-j'+jobs],obj)
  run(['make','install','DESTDIR='+str(stage)],obj)
  run(['make','install'],obj)
 run(['ldconfig'],b)
 (b/'logs'/(key+'.done')).write_text(record['sha256']+'\n')
print('AUTHENTICATION_DEPENDENCIES_BUILT',flush=True)
