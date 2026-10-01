#!/usr/bin/env python3
from pathlib import Path
import concurrent.futures, hashlib, json, re, subprocess
base = Path('/opt/aether')
book = base / 'sources/blfs-r13.1'
entities = {}
rx = re.compile(r'<!ENTITY\s+([\w.-]+)\s+"([^"]*)"\s*>', re.S)
for f in book.rglob('*.ent'):
    entities.update(rx.findall(f.read_text()))
def expand(s, extra=None):
    d = entities | (extra or {})
    for _ in range(30):
        n = re.sub(r'&([\w.-]+);', lambda m: d.get(m[1], m[0]), s)
        if n == s: break
        s = n
    assert not re.search(r'&[\w.-]+;', s), s
    return s
items = []
def add(key, url, md5, **kwargs):
    items.append(dict(key=key, url=url, filename=url.rsplit('/', 1)[-1], md5=md5, **kwargs))
selected = {
 'glib2':'general/genlib/glib2.xml', 'libtirpc':'networking/netlibs/libtirpc.xml',
 'fuse3':'postlfs/filesystems/fuse3.xml', 'libpng':'general/graphlib/libpng.xml',
 'freetype2':'general/graphlib/freetype2.xml', 'fontconfig':'general/graphlib/fontconfig.xml',
 'util-macros':'x/installing/util-macros.xml', 'xorgproto':'x/installing/xorgproto.xml',
 'libXau':'x/installing/libXau.xml', 'libXdmcp':'x/installing/libXdmcp.xml',
 'xcb-proto':'x/installing/xcb-proto.xml', 'libxcb':'x/installing/libxcb.xml',
 'pixman':'general/graphlib/pixman.xml', 'libdrm':'x/lib/libdrm.xml',
 'cairo':'x/lib/cairo.xml', 'harfbuzz':'general/genlib/harfbuzz.xml',
 'fribidi':'general/genlib/fribidi.xml', 'pango':'x/lib/pango.xml',
 'gdk-pixbuf':'x/lib/gdk-pixbuf.xml', 'at-spi2-core':'x/lib/at-spi2-core.xml',
 'libepoxy':'x/lib/libepoxy.xml', 'gtk3':'x/lib/gtk+3.xml',
 'xkeyboard-config':'x/installing/xkeyboard-config.xml', 'libxcvt':'x/installing/libxcvt.xml',
 'xorg-server':'x/installing/xorg-server.xml', 'xinit':'x/installing/xinit.xml',
 'twm':'x/installing/twm.xml', 'xterm':'x/installing/xterm.xml',
 'xbitmaps':'x/installing/xbitmaps.xml', 'libevdev':'x/installing/libevdev.xml',
 'efivar':'postlfs/boot/efivar.xml', 'efibootmgr':'postlfs/boot/efibootmgr.xml',
 'rpcsvc-proto':'networking/netlibs/rpcsvc-proto.xml',
 'libsigc':'general/genlib/libsigc++.xml', 'glibmm':'general/genlib/glibmm.xml',
 'cairomm':'x/lib/cairomm-1.0.xml', 'pangomm':'x/lib/pangomm.xml',
 'atkmm':'x/lib/atkmm.xml', 'gtkmm3':'x/lib/gtkmm3.xml',
 'shared-mime-info':'general/sysutils/shared-mime-info.xml',
 'mtdev':'general/genlib/mtdev.xml',
 'popt':'general/genlib/popt.xml',
 'which':'general/sysutils/which.xml',
}
for key, rel in selected.items():
    p = book / rel
    if not p.exists():
        candidates = list(book.rglob(Path(rel).name))
        assert len(candidates) == 1, (key, candidates)
        p = candidates[0]
    local = dict(rx.findall(p.read_text()))
    download = [x for x in local if x.endswith('-download-http')]
    match = next((x for x in download if x == key + '-download-http'), download[0])
    prefix = match.removesuffix('-download-http')
    add(key, expand(local[match], local), expand(local[prefix+'-md5sum'], local))
# Xorg's grouped pages pin each library/app separately.
for rel, names, folder in [
 ('x/installing/x7lib.xml', ['xtrans','libX11','libXext','libICE','libSM','libXScrnSaver','libXt','libXmu','libXpm','libXaw','libXfixes','libXcomposite','libXrender','libXcursor','libXdamage','libfontenc','libXfont2','libXft','libXi','libXinerama','libXrandr','libXtst','libxkbfile','libpciaccess'], 'lib'),
 ('x/installing/x7app.xml', ['xauth','xrandr','xkbcomp','xdpyinfo','xprop','xset','xmessage'], 'app')]:
    local = dict(rx.findall((book/rel).read_text()))
    for name in names:
        version = expand('&'+name+'-version;', local)
        add(name, 'https://www.x.org/pub/individual/'+folder+'/'+name+'-'+version+'.tar.xz', expand('&'+name+'-md5sum;', local))
# The input driver is pinned by its BLFS chapter.
p = book/'x/installing/x7driver-evdev.xml'
local = dict(rx.findall(p.read_text()))
prefix = next(k.removesuffix('-download-http') for k in local if k.endswith('-download-http'))
add('xf86-input-evdev', expand(local[prefix+'-download-http'], local), expand(local[prefix+'-md5sum'], local))
cache = base / 'sources/native-guest-cache'
cache.mkdir(exist_ok=True)
def fetch(item):
    dest = cache / item['filename']
    if not dest.exists():
        subprocess.run(['curl','-fL','--retry','3','--connect-timeout','20','-o',str(dest)+'.partial',item['url']], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        Path(str(dest)+'.partial').rename(dest)
    data = dest.read_bytes()
    assert hashlib.md5(data).hexdigest() == item['md5'], item['key']+' checksum mismatch'
    item['sha256'] = hashlib.sha256(data).hexdigest()
    print(item['key'], item['filename'], flush=True)
    return item
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    result = list(pool.map(fetch, items))
(base/'next/configs/native-guest-sources.json').write_text(json.dumps(result, indent=2)+'\n')
print('Verified', len(result), 'pinned sources.')
