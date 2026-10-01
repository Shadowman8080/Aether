#!/usr/bin/env python3
from pathlib import Path
import json,hashlib,subprocess,tarfile,os
assert 'ID=aether' in Path('/etc/os-release').read_text()
items={d['key']:d for d in json.loads(Path('/security/sources.json').read_text())}
base=Path('/build/security');base.mkdir(exist_ok=True)
jobs=str(os.cpu_count())
def run(args,cwd):
 print('RUN',args,flush=True);subprocess.run(args,cwd=cwd,check=True)
def extract(key):
 d=items[key];p=Path('/sources/security-cache')/d['filename']
 assert hashlib.sha256(p.read_bytes()).hexdigest()==d['sha256']
 dest=base/key;dest.mkdir(exist_ok=True)
 if not (dest/'.extracted').exists():
  with tarfile.open(p) as t:t.extractall(dest,filter='data')
  (dest/'.extracted').touch()
 return next(x for x in dest.iterdir() if x.is_dir())
def auto(key,opts,targets=None):
 if (base/(key+'.done')).exists():return
 src=extract(key)
 run(['./configure','--prefix=/usr','--libdir=/usr/lib','--sysconfdir=/etc','--disable-static',*opts],src)
 run(['make','-j'+jobs,*((targets or [])[0:1])],src)
 run(['make','-j1',*((targets or [])[1:2] or ['install'])],src)
 run(['ldconfig'],src)
 (base/(key+'.done')).write_text(items[key]['sha256'])
auto('libmnl',[])
auto('libnftnl',[])
auto('nftables',['--disable-man-doc','--disable-python','--without-cli','--without-json'])
if not (base/'apparmor.done').exists():
 src=extract('apparmor');lib=src/'libraries/libapparmor'
 run(['autoreconf','-fi'],lib)
 run(['./configure','--prefix=/usr','--libdir=/usr/lib','--enable-static','--disable-man-pages','--without-python','--without-perl','--without-ruby'],lib)
 run(['make','clean'],lib);run(['make','-j'+jobs],lib);run(['make','-j1','install'],lib);run(['ldconfig'],lib)
 run(['make','-j'+jobs,'USE_SYSTEM=1'],src/'parser')
 run(['make','-j1','install','USE_SYSTEM=1'],src/'parser')
 run(['make','install'],src/'profiles')
 (base/'apparmor.done').write_text(items['apparmor']['sha256'])
auto('devmapper',['--disable-selinux','--disable-udev_sync','--disable-udev_rules','--disable-readline','--enable-pkgconfig'],['device-mapper','install_device-mapper'])
auto('cryptsetup',['--disable-asciidoc','--disable-ssh-token','--disable-pwquality','--disable-external-tokens','--disable-udev'])
auto('dosfstools',['--enable-compat-symlinks'])
auto('cpio',['--enable-mt','--with-rmt=/usr/libexec/rmt','CFLAGS=-O2 -pipe -std=gnu17 -fstack-protector-strong -D_FORTIFY_SOURCE=3'])
print('SECURITY_PACKAGES_BUILD_PASS',flush=True)
