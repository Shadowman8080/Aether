from pathlib import Path
import re,json,hashlib,concurrent.futures,subprocess
base=Path('/opt/aether'); book=base/'sources/blfs-r13.1'
rx=re.compile(r'<!ENTITY\s+([\w.-]+)\s+"([^"]*)"\s*>',re.S)
def booktext(p): return re.sub(r'<!--.*?-->','',p.read_text(),flags=re.S)
entities={}
for p in book.rglob('*.xml'): entities.update(rx.findall(booktext(p)))
for p in book.rglob('*.ent'): entities.update(rx.findall(booktext(p)))
def expand(s,d):
 for _ in range(40):
  n=re.sub(r'&([\w.-]+);',lambda m:d.get(m[1],m[0]),s)
  if n==s: break
  s=n
 return s
items=[]
def add(key,url,md5=None,group='base'):
 items.append(dict(key=key,url=url,filename=url.rsplit('/',1)[-1],md5=md5,group=group))
names=['cmake','git','llvm','libpng','freetype2','fontconfig','xorgproto','pixman','libxcvt','libfontenc','libXfont2','libxkbfile','xkbcomp','xkeyboard-config','mtdev','libevdev','xtrans','libXau','libXdmcp','xcb-proto','libxcb','libX11','libXext','libXrender','libXfixes','libXrandr','libXcursor','libXcomposite','libXdamage','libXi','libXtst','libpciaccess','libdrm','wayland','wayland-protocols','libxkbcommon','libinput','mesa','xcb-util','xcb-util-image','xcb-util-keysyms','xcb-util-renderutil','xcb-util-wm','xcb-util-cursor','xcb-util-errors','libjpeg','double-conversion','icu','libwebp','tiff','extra-cmake-modules','linux-pam','polkit','libgudev','libwacom','libdisplay-info','seatd','xwayland','libei','libepoxy','Mako','MarkupSafe','PyYAML','packaging','setuptools','libxmlb','duktape','json-glib']
extra=base/'desktop/configs/extra-sources.json'
if extra.exists(): names+=json.loads(extra.read_text(encoding='utf-8-sig'))
direct=base/'desktop/configs/direct-sources.json'
direct_items=json.loads(direct.read_text(encoding='utf-8-sig')) if direct.exists() else []
direct_keys={item['key'] for item in direct_items}
for key in dict.fromkeys(names):
 if key in direct_keys: continue
 if key in ('MarkupSafe','packaging','setuptools'): continue # Already supplied by the native LFS base.
 if key.startswith('xcb-util-'):
  d=entities|dict(rx.findall((book/'x/installing/xcb-utilities.xml').read_text()))
  add(key,expand('https://xorg.freedesktop.org/archive/individual/lib/'+key+'-&'+key+'-version;.tar.xz',d),d[key+'-md5sum'])
  continue
 page={'libjpeg':'libjpeg-turbo','libsass':'sassc','speexdsp':'speex','lm-sensors':'lm_sensors'}.get(key,key.lower())
 files=[p for p in book.rglob('*.xml') if p.name.lower()==page+'.xml' and 'archive' not in p.parts]
 if not files:
  # Xorg libraries are described in grouped chapter pages, not per-package
  # files, so fall back to the book-wide download entities.
  k=key+'-download-http'
  if k in entities:
   url=expand('&'+k+';',entities); md5=expand(entities.get(key+'-md5sum',''),entities)
  elif key+'-version' in entities:
   # The grouped x7lib/x7app chapters publish version and checksum entities
   # only. Applications such as xkbcomp live under individual/app; libraries
   # live under individual/lib.
   subdir='app' if key in ('xkbcomp','xauth','xhost','xmodmap','xrandr','xrdb','setxkbmap','xinit','xev') else 'lib'
   url=expand('https://xorg.freedesktop.org/archive/individual/'+subdir+'/'+key+'-&'+key+'-version;.tar.xz',entities)
   md5=expand(entities.get(key+'-md5sum',''),entities)
  else:
   print('DEFERRED missing book file',key); continue
  assert '&' not in url and re.fullmatch('[a-f0-9]{32}',md5),(key,url,md5)
  add(key,url,md5); continue
 p=files[0]; d=entities|{k:v for k,v in rx.findall(booktext(p)) if v!='&'+k+';'}
 candidates=[k for k in d if k.endswith('-download-http') and k in dict(rx.findall(booktext(p)))]
 if not candidates: print('DEFERRED grouped book file',key); continue
 k=next((k for k in candidates if k==key+'-download-http'),candidates[0]); prefix=k.removesuffix('-download-http')
 url=expand(d[k],d); md5=expand(d.get(prefix+'-md5sum',''),d)
 assert '&' not in url and re.fullmatch('[a-f0-9]{32}',md5),(key,url,md5)
 add(key,url,md5)
llvm=next(item for item in items if item['key']=='llvm')
add('clang',llvm['url'],llvm['md5'])
for rel,group,url in [('kde/kf6/kf6-frameworks.xml','frameworks','https://download.kde.org/stable/frameworks/6.29/'),('kde/plasma/plasma-all.xml','plasma','https://download.kde.org/stable/plasma/6.7.4/')]:
 for md5,filename in re.findall(r'^#?([a-f0-9]{32})\s+([\w.+-]+\.tar\.xz)',re.sub(r'<[^>]+>','',(book/rel).read_text()),re.M):
  add(re.sub(r'-\d.*','',filename),url+filename,md5,group)
for key in ['qtbase','qtshadertools','qtdeclarative','qtwayland','qtsvg','qtimageformats','qttools','qttranslations','qt5compat','qtmultimedia','qtlocation','qtpositioning','qtsensors','qtwebchannel','qtwebsockets','qtserialport','qtvirtualkeyboard','qtspeech']:
 add(key,f'https://download.qt.io/official_releases/qt/6.11/6.11.2/submodules/{key}-everywhere-src-6.11.2.tar.xz',group='qt')
for item in direct_items:
 add(item['key'],item['url'],group='direct')
 items[-1].update(item)
cache=base/'sources/desktop-cache'; cache.mkdir(exist_ok=True)
def fetch(item):
 p=cache/item['filename']
 existing=base/'sources/lfs-cache'/item['filename']
 if not p.exists() and existing.exists(): p.hardlink_to(existing)
 if not p.exists():
  subprocess.run(['curl','-fL','--retry','3','--connect-timeout','20',item['url'],'-o',str(p)+'.partial'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
  Path(str(p)+'.partial').rename(p)
 md5=hashlib.md5(); sha256=hashlib.sha256()
 with p.open('rb') as stream:
  for block in iter(lambda:stream.read(1024*1024),b''): md5.update(block); sha256.update(block)
 if item['md5']: assert md5.hexdigest()==item['md5'],item['key']
 item['sha256']=sha256.hexdigest()
 if item.get('sha256_expected'): assert item['sha256']==item['sha256_expected'],item['key']+' SHA256 mismatch'
 if item['group']=='qt':
  official=subprocess.check_output(['curl','-fsL','--retry','3',item['url']+'.sha256'],text=True).split()[0]
  assert item['sha256']==official,item['key']+' official SHA256 mismatch'
 print('Verified',item['key'],flush=True)
 return item
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool: result=list(pool.map(fetch,items))
(base/'desktop/configs/sources.json').write_text(json.dumps(result,indent=2)+'\n')
print('Pinned and verified',len(result),'desktop sources.')
