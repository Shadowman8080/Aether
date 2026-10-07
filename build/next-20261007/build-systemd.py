#!/usr/bin/env python3
"""Build the missing crypto/AppArmor integration and stage systemd with explicit features."""
from pathlib import Path
import hashlib,json,os,subprocess
b=Path('/next');records={v['key']:v for v in json.loads((b/'sources.lock.json').read_text())}
assert 'ID=aether' in Path('/etc/os-release').read_text()
env={**os.environ,'CFLAGS':'-O2 -pipe -march=x86-64 -mtune=generic -fstack-protector-strong','CXXFLAGS':'-O2 -pipe -march=x86-64 -mtune=generic -fstack-protector-strong','LDFLAGS':'-Wl,-z,relro,-z,now'}
jobs=str(os.cpu_count())
def run(args,cwd,extra=None):
 print('RUN',args,flush=True);subprocess.run(args,cwd=cwd,env={**env,**(extra or {})},check=True)
for record in json.loads((b/'boot-python-sources.json').read_text()):
 archive=b/'sources'/record['archive']
 with archive.open('rb') as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==record['sha256']
 marker=b/'logs'/(record['name']+'.done')
 if marker.exists():continue
 run(['python3','-m','pip','install','--no-index','--no-deps','--no-build-isolation',str(archive)],b)
 run(['python3','-m','pip','install','--ignore-installed','--no-index','--no-deps','--no-build-isolation','--root',str(b/'stage/boot-python'),'--prefix=/usr',str(archive)],b)
 marker.write_text(record['sha256']+'\n')
for key in ('autoconf-archive','apparmor','devmapper','cryptsetup','systemd'):
 record=records[key];archive=b/'sources'/record['archive']
 with archive.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==record['sha256']
 if (b/'logs'/(key+'.done')).exists():continue
 src=next(p for p in (b/'inspect'/key).iterdir() if p.is_dir());obj=b/'obj'/key;obj.mkdir(exist_ok=True);stage=b/'stage'/key;stage.mkdir(exist_ok=True)
 if key=='systemd':
  run(['meson','setup',str(obj),str(src),'--prefix=/usr','--libdir=lib','--sysconfdir=/etc','--localstatedir=/var','--buildtype=release','-Dmode=release','-Dman=disabled','-Dhtml=disabled','-Dtests=false','-Dseccomp=enabled','-Dapparmor=enabled','-Dlibfido2=enabled','-Dtpm2=enabled','-Dlibcryptsetup=enabled','-Dlibcryptsetup-plugins=enabled','-Dbootloader=enabled','-Dukify=enabled','-Ddefault-dnssec=no','-Dsbat-distro=aether','-Dsbat-distro-generation=1','-Dsbat-distro-summary=Aether Linux','-Dsbat-distro-pkgname=systemd','-Dsbat-distro-version=261.2-2aether1','-Dsbat-distro-url=https://github.com/Shadowman8080/Aether'],b)
  run(['ninja','-C',str(obj),'-j',jobs],b)
  run(['meson','install','-C',str(obj),'--no-rebuild','--destdir',str(stage)],b)
  # Stage only. Replacing PID1 belongs to the disposable-image integration phase.
 else:
  opts=['--prefix=/usr','--libdir=/usr/lib','--sysconfdir=/etc']
  if key=='apparmor':
   src=src/'libraries/libapparmor';run(['autoreconf','-fi'],src)
   opts+=['--disable-static','--disable-man-pages','--without-python','--without-perl','--without-ruby']
  elif key=='devmapper':opts+=['--disable-selinux','--disable-udev_sync','--disable-udev_rules','--disable-readline','--enable-pkgconfig']
  elif key=='cryptsetup':opts+=['--disable-static','--disable-asciidoc','--disable-ssh-token','--disable-pwquality','--enable-udev','--enable-external-tokens']
  run([str(src/'configure'),*opts],obj)
  target=['device-mapper'] if key=='devmapper' else []
  install='install_device-mapper' if key=='devmapper' else 'install'
  run(['make','-j'+jobs,*target],obj)
  run(['make',install,'DESTDIR='+str(stage)],obj)
  run(['make',install],obj)
  run(['ldconfig'],b)
 (b/'logs'/(key+'.done')).write_text(record['sha256']+'\n')
print('SYSTEMD_SECURITY_INTEGRATION_STAGED',flush=True)
