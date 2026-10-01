#!/usr/bin/env python3
"""Native builds using only Aether's installed toolchain and pinned archives."""
from pathlib import Path
import hashlib,json,os,subprocess,tarfile,time
root=Path('/build')
manifest={x['key']:x for x in json.loads(Path('/recipes/configs/native-guest-sources.json').read_text())}
jobs=str(os.cpu_count())
for d in ('packages','logs','done'): (root/d).mkdir(exist_ok=True)
def run(args,cwd,log):
 subprocess.run(args,cwd=cwd,stdout=log,stderr=subprocess.STDOUT,check=True)
def build(key,kind='auto',opts=()):
 stamp=root/'done'/key
 if stamp.exists(): return
 print('BUILD',key,flush=True)
 item=manifest[key]
 archive=Path('/sources/native-guest-cache')/item['filename']
 assert hashlib.sha256(archive.read_bytes()).hexdigest()==item['sha256']
 dest=root/'packages'/key
 dest.mkdir(exist_ok=True)
 if not (dest/'.extracted').exists():
  def safe_member(member,path):
   if member.issym() and member.linkname.startswith('/'):
    return None  # release tarball's absolute documentation symlink
   return tarfile.data_filter(member,path)
  with tarfile.open(archive) as t: t.extractall(dest,filter=safe_member)
  (dest/'.extracted').touch()
 src=next(p for p in dest.iterdir() if p.is_dir())
 with (root/'logs'/(key+'.log')).open('w') as log:
  if kind=='auto': kind='meson' if (src/'meson.build').exists() else 'autoconf'
  if kind=='autoconf' and not (src/'configure').exists() and (src/'meson.build').exists():
   kind='meson'
   opts=[]
  if kind=='meson':
   reconfigure=['--reconfigure'] if (src/'_aether/meson-private/coredata.dat').exists() else []
   run(['meson','setup',*reconfigure,'_aether','--prefix=/usr','--libdir=lib','--buildtype=release','--wrap-mode=nodownload','-Ddefault_library=shared',*opts],src,log)
   run(['ninja','-C','_aether','-j',jobs],src,log)
   run(['ninja','-C','_aether','install'],src,log)
  elif kind=='autoconf':
   run(['./configure','--prefix=/usr','--sysconfdir=/etc','--localstatedir=/var','--disable-static',*opts],src,log)
   run(['make','-j'+jobs],src,log)
   run(['make','install'],src,log)
  elif kind=='make':
   run(['make','-j'+jobs,*opts],src,log)
   run(['make','install',*opts],src,log)
  else: raise ValueError(kind)
  run(['ldconfig'],src,log)
 stamp.write_text(item['sha256']+'\n')
 print('DONE',key,flush=True)

build('glib2',opts=['-Dintrospection=disabled','-Dtests=false','-Ddocumentation=false','-Dman-pages=disabled'])
build('rpcsvc-proto','autoconf')
build('libtirpc','autoconf',['--disable-gssapi'])
build('fuse3',opts=['-Dtests=false','-Dexamples=false','-Dinitscriptdir=','-Denable-io-uring=false'])
build('libpng','autoconf')
build('freetype2','autoconf',['--without-harfbuzz'])
build('fontconfig',opts=['-Ddoc=disabled','-Dtests=disabled'])
for k in ['util-macros','xorgproto','libXau','libXdmcp','xcb-proto','libxcb','xtrans','libX11','libXext','libICE','libSM','libXScrnSaver','libXt','libXmu','libXpm','libXaw','libXfixes','libXcomposite','libXrender','libXcursor','libXdamage','libfontenc','libXfont2','libXft','libXi','libXinerama','libXrandr','libXtst','libxkbfile']:
 extra=['--disable-open-zfile'] if k=='libXpm' else []
 build(k,'autoconf',['--disable-docs','--disable-devel-docs',*extra])
build('pixman',opts=['-Dtests=disabled','-Ddemos=disabled'])
build('libdrm',opts=['-Dtests=false','-Dman-pages=disabled','-Dvmwgfx=enabled'])
build('libpciaccess')
build('cairo',opts=['-Dtests=disabled','-Dgtk_doc=false'])
build('harfbuzz',opts=['-Dtests=disabled','-Ddocs=disabled','-Dintrospection=disabled','-Dicu=disabled','-Dgpu=disabled'])
build('fribidi',opts=['-Ddocs=false','-Dtests=false'])
build('pango',opts=['-Dintrospection=disabled','-Dbuild-testsuite=false','-Dbuild-examples=false','-Ddocumentation=false'])
build('shared-mime-info',opts=['-Dbuild-tests=false','-Dbuild-translations=false','-Dbuild-spec=false','-Dupdate-mimedb=true'])
build('gdk-pixbuf',opts=['-Dintrospection=disabled','-Dgtk_doc=false','-Dman=false','-Dtests=false','-Dinstalled_tests=false','-Dglycin=disabled','-Dlegacy_xpm=enabled'])
build('at-spi2-core',opts=['-Dintrospection=disabled','-Ddocs=false','-Ddefault_bus=dbus-daemon','-Dgtk2_atk_adaptor=false'])
build('libepoxy',opts=['-Ddocs=false','-Dtests=false','-Degl=no','-Dglx=yes','-Dx11=true'])
build('gtk3',opts=['-Dwayland_backend=false','-Dintrospection=false','-Ddemos=false','-Dexamples=false','-Dtests=false','-Dgtk_doc=false','-Dman=false','-Dprint_backends=file'])
build('libxcvt')
build('xkeyboard-config')
build('xorg-server',opts=['-Dxorg=true','-Dglamor=false','-Dglx=false','-Ddri1=false','-Ddri2=false','-Ddri3=false','-Dxnest=false','-Dxvfb=true','-Ddocs=false','-Ddevel-docs=false','-Dsuid_wrapper=true','-Ddefault_font_path=built-ins','-Dxkb_output_dir=/var/lib/xkb'])
build('libevdev',opts=['-Dtests=disabled','-Ddocumentation=disabled'])
build('mtdev','autoconf')
build('xf86-input-evdev','autoconf')
for k in ['xbitmaps','xauth','xrandr','xkbcomp','xdpyinfo','xprop','xset','xmessage','xinit','twm','xterm']:
 build(k,'autoconf')
print('Native graphical dependencies complete.',flush=True)
