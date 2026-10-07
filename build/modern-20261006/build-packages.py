#!/usr/bin/env python3
"""Run inside the native Aether build root; install into a separate payload too."""
from pathlib import Path
import hashlib,json,os,subprocess,sys
B=Path('/modern'); jobs=str(os.cpu_count()); stage=B/'stage'; stage.mkdir(exist_ok=True)
assert 'ID=aether' in Path('/etc/os-release').read_text().splitlines()
items={d['key']:d for d in json.loads((B/'sources.json').read_text())}
def run(args,cwd=None,env=None):
 print('RUN',args,flush=True);subprocess.run(args,cwd=cwd,env=env,check=True)
if 'pyparsing' in items:
 p=B/'sources'/items['pyparsing']['filename']
 assert hashlib.sha256(p.read_bytes()).hexdigest()==items['pyparsing']['sha256']
 run(['python3','-m','pip','install','--no-index','--no-deps','--no-build-isolation',str(p)])
def build(key,kind,opts):
 d=items[key]; archive=B/'sources'/d['filename']
 assert hashlib.sha256(archive.read_bytes()).hexdigest()==d['sha256']
 marker=B/(key+'.done')
 if marker.exists() and marker.read_text()==d['sha256']:return
 src=next(p for p in (B/'inspect'/key).iterdir() if p.is_dir()); out=B/'obj'/key;out.mkdir(parents=True,exist_ok=True)
 if kind=='meson':
  if not (out/'build.ninja').exists():run(['meson','setup',str(out),str(src),'--prefix=/usr','--libdir=lib','--sysconfdir=/etc','--localstatedir=/var','--buildtype=release','--wrap-mode=nodownload',*opts])
  run(['ninja','-C',str(out),'-j',jobs]);run(['meson','install','-C',str(out),'--no-rebuild','--destdir',str(stage)]);run(['meson','install','-C',str(out),'--no-rebuild'])
 elif kind=='cmake':
  run(['cmake','-S',str(src),'-B',str(out),'-G','Ninja','-DCMAKE_INSTALL_PREFIX=/usr','-DCMAKE_INSTALL_LIBDIR=lib','-DCMAKE_BUILD_TYPE=Release','-DBUILD_TESTING=OFF',*opts])
  run(['cmake','--build',str(out),'--parallel',jobs]);run(['cmake','--install',str(out)],env={**os.environ,'DESTDIR':str(stage)});run(['cmake','--install',str(out)])
 else:
  if not (src/'configure').exists():run(['autoreconf','-fi'],src)
  run([str(src/'configure'),'--prefix=/usr','--libdir=/usr/lib','--sysconfdir=/etc','--localstatedir=/var','--disable-static',*opts],out)
  run(['make','-j'+jobs],out);run(['make','DESTDIR='+str(stage),'install'],out);run(['make','install'],out)
 run(['ldconfig']);marker.write_text(d['sha256'])
 print('BUILT',key,flush=True)
recipes=[
 ('libseccomp','auto',[]),
 ('bubblewrap','meson',['-Dman=disabled','-Dtests=false','-Dselinux=disabled']),
 ('xdg-dbus-proxy','meson',['-Dman=disabled','-Dtests=false']),
 ('ostree','auto',['--with-curl','--without-soup','--without-selinux','--disable-man','--disable-gtk-doc','--enable-introspection=no']),
 ('flatpak','meson',['-Ddocbook_docs=disabled','-Dgtkdoc=disabled','-Dgir=disabled','-Dtests=false','-Dseccomp=enabled','-Dmalcontent=disabled','-Dselinux_module=disabled','-Dsystem_bubblewrap=/usr/bin/bwrap','-Dsystem_dbus_proxy=/usr/bin/xdg-dbus-proxy']),
 ('libxmlb','meson',['-Dgtkdoc=false','-Dintrospection=false','-Dtests=false']),
 ('libjcat','meson',['-Dgtkdoc=false','-Dintrospection=false','-Dvapi=false','-Dtests=false','-Dman=false']),
 ('fwupd','meson',['-Ddocs=disabled','-Dman=false','-Dtests=false','-Dintrospection=disabled','-Dpassim=disabled','-Dp2p_policy=none','-Dpolkit=enabled','-Dsystemd=enabled','-Dlvfs=true']),
 ('qtconnectivity','cmake',[]),
 ('libfakekey','auto',[]),
 ('kdeconnect','cmake',['-DINSTALL_UFW_APPLICATION_RULE=OFF']),
 ('discover','cmake',[]),
 ('flatpak-kcm','cmake',[])]
for key,kind,opts in recipes:
 if len(sys.argv)==1 or key in sys.argv[1:]:build(key,kind,opts)
