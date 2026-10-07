#!/usr/bin/env python3
"""Build USB authorization dependencies natively; never activate the daemon."""
import hashlib,json,os,shutil,subprocess
from pathlib import Path
b=Path('/next');records=json.loads((b/'usb-dependencies.lock.json').read_text())
records+=[r for r in json.loads((b/'sources.lock.json').read_text()) if r['key']=='usbguard']
assert 'ID=aether' in Path('/etc/os-release').read_text().splitlines()
jobs=str(os.cpu_count());env={**os.environ,'CFLAGS':'-O2 -pipe -march=x86-64 -mtune=generic -fstack-protector-strong','CXXFLAGS':'-O2 -pipe -march=x86-64 -mtune=generic -fstack-protector-strong','LDFLAGS':'-Wl,-z,relro,-z,now'}
def run(args,cwd,extra=None):
 print('RUN',args,flush=True);subprocess.run(args,cwd=cwd,env={**env,**(extra or {})},check=True)
for record in records:
 key=record['key'];archive=b/'sources'/record['archive']
 assert hashlib.file_digest(archive.open('rb'),'sha256').hexdigest()==record['sha256']
 marker=b/'logs'/(key+'.done')
 build_id=record['sha256']+(':localstate-var-v1' if key=='usbguard' else '')
 if marker.exists() and marker.read_text().strip()==build_id:continue
 source=next(p for p in (b/'inspect'/key).iterdir() if p.is_dir());obj=b/'obj'/key;obj.mkdir(exist_ok=True);stage=b/'stage'/key;stage.mkdir(exist_ok=True)
 if key in ('abseil','protobuf'):
  options=['-DCMAKE_INSTALL_PREFIX=/usr','-DCMAKE_INSTALL_LIBDIR=lib','-DCMAKE_BUILD_TYPE=Release','-DCMAKE_CXX_STANDARD=17','-DBUILD_SHARED_LIBS=ON','-DFETCHCONTENT_FULLY_DISCONNECTED=ON']
  if key=='abseil':options+=['-DABSL_BUILD_TESTING=OFF','-DABSL_ENABLE_INSTALL=ON','-DABSL_PROPAGATE_CXX_STD=ON']
  else:options+=['-Dprotobuf_BUILD_TESTS=OFF','-Dprotobuf_BUILD_SHARED_LIBS=ON','-Dprotobuf_LOCAL_DEPENDENCIES_ONLY=ON']
  run(['cmake','-S',str(source),'-B',str(obj),'-G','Ninja',*options],b)
  run(['cmake','--build',str(obj),'--parallel',jobs],b)
  run(['cmake','--install',str(obj)],b,{'DESTDIR':str(stage)})
  run(['cmake','--install',str(obj)],b)
 else:
  options=['--prefix=/usr','--libdir=/usr/lib','--sysconfdir=/etc','--localstatedir=/var','--disable-static']
  if key=='libqb':options+=['--disable-tests']
  else:options+=['--with-crypto-library=openssl','--enable-seccomp','--enable-systemd','--with-dbus','--with-polkit','--with-bundled-pegtl','--with-bundled-catch','--disable-full-test-suite']
  run([str(source/'configure'),*options],obj)
  run(['make','-j'+jobs],obj)
  if key=='usbguard':run(['make','-j'+jobs,'check'],obj)
  if key=='usbguard':shutil.rmtree(stage);stage.mkdir()
  run(['make','install','DESTDIR='+str(stage)],obj)
  if key!='usbguard':run(['make','install'],obj)
 run(['ldconfig'],b);marker.write_text(build_id+'\n')
print('USB_AUTHORIZATION_COMPONENTS_STAGED; DAEMON_NOT_ENABLED')
