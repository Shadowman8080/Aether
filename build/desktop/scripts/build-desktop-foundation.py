from pathlib import Path
import hashlib,json,os,subprocess,tarfile,shutil,zipfile
manifest={x['key']:x for x in json.loads(Path('/recipes/configs/sources.json').read_text())}
root=Path('/build'); jobs=str(os.cpu_count())
for name in ('packages','logs','done'): (root/name).mkdir(exist_ok=True)
def run(cmd,cwd,log): subprocess.run(cmd,cwd=cwd,stdout=log,stderr=subprocess.STDOUT,check=True)
def build(key,kind='cmake',opts=()):
 if os.environ.get('AETHER_BUILD_ONLY') and key not in os.environ['AETHER_BUILD_ONLY'].split(','): return
 item=manifest[key]; stamp=root/'done'/key
 if stamp.exists(): return
 print('BUILD',key,flush=True)
 archive=Path('/sources/desktop-cache')/item['filename']
 with archive.open('rb') as stream:
  assert hashlib.file_digest(stream,'sha256').hexdigest()==item['sha256']
 dest=root/'packages'/key; dest.mkdir(exist_ok=True)
 if not (dest/'.extracted').exists():
  if archive.suffix=='.zip':
   with zipfile.ZipFile(archive) as t:
    for name in t.namelist():
     assert (dest/name).resolve().is_relative_to(dest.resolve())
    t.extractall(dest)
  else:
   with tarfile.open(archive) as t: t.extractall(dest,filter='data')
  (dest/'.extracted').touch()
 src=dest if key=='docbook-45-xml' else next(p for p in dest.iterdir() if p.is_dir())
 with (root/'logs'/(key+'.log')).open('w') as log:
  if key=='gmp': run(['sed','-i','/long long t1;/,+1s/()/(...)/','configure'],src,log)
  if key=='intltool':
   p=src/'intltool-update.in'; p.write_text(p.read_text().replace(r'\${',r'\$\{'))
  if key=='itstool' and not (dest/'.patched').exists():
   patch=manifest['itstool-lxml-patch']; patchfile=Path('/sources/desktop-cache')/patch['filename']
   assert hashlib.sha256(patchfile.read_bytes()).hexdigest()==patch['sha256']
   run(['patch','-Np1','-i',str(patchfile)],src,log); (dest/'.patched').touch()
  if key=='qca':
   p=src/'CMakeLists.txt'; p.write_text(p.read_text().replace('cert.pem','certs/ca-bundle.crt'))
  if key=='lightdm': run(['python3','/recipes/scripts/prepare-lightdm-source.py',str(src)],src,log)
  if key=='plasma-workspace': run(['python3','/recipes/scripts/patch-aurasearch.py',str(src)],src,log)
  if key=='kdeplasma-addons': run(['python3','/recipes/scripts/patch-optional-kameleon.py',str(src)],src,log)
  if key=='breeze': run(['python3','/recipes/scripts/patch-aether-decoration.py',str(src)],src,log)
  if kind=='cmake-bootstrap':
   run(['./bootstrap','--prefix=/usr','--parallel='+jobs,'--','-DCMAKE_BUILD_TYPE=Release'],src,log)
   run(['make','-j'+jobs],src,log); run(['make','install'],src,log)
  elif kind=='cmake':
   source=src/key if key in ('llvm','clang') else src
   if key in ('llvm','clang') and not (dest/'.patched').exists():
    run(['patch','-Np1','-i','/sources/lfs-cache/llvm-22.1.8-upstream_fix-1.patch'],src,log)
    (dest/'.patched').touch()
   run(['cmake','-S',str(source),'-B','_build','-G','Ninja','-DCMAKE_INSTALL_PREFIX=/usr','-DCMAKE_INSTALL_LIBDIR=lib','-DCMAKE_BUILD_TYPE=Release','-DBUILD_TESTING=OFF','-DCMAKE_INSTALL_LIBEXECDIR=libexec',*opts],src,log)
   run(['cmake','--build','_build','--parallel',jobs],src,log)
   run(['cmake','--install','_build'],src,log)
  elif kind=='meson':
   more=['--reconfigure'] if (src/'_build/meson-private/coredata.dat').exists() else []
   run(['meson','setup',*more,'_build','--prefix=/usr','--libdir=lib','--buildtype=release','--wrap-mode=nodownload',*opts],src,log)
   run(['ninja','-C','_build','-j',jobs],src,log); run(['ninja','-C','_build','install'],src,log)
  elif kind=='autoconf':
   if not (src/'configure').exists(): run(['autoreconf','-fi'],src,log)
   run(['./configure','--prefix=/usr','--sysconfdir=/etc','--localstatedir=/var','--disable-static',*opts],src,log)
   run(['make','-j'+jobs],src,log)
   if key in ('gmp','mpfr','mpc'): run(['make','-j'+jobs,'check'],src,log)
   run(['make','install'],src,log)
  elif kind=='make':
   run(['make','-j'+jobs,*opts],src,log); run(['make',*opts,'install'],src,log)
  elif kind=='perl':
   run(['perl','Makefile.PL'],src,log)
   run(['make','-j'+jobs],src,log); run(['make','install'],src,log)
  elif kind=='python':
   run(['python3','-m','pip','wheel','--no-build-isolation','--no-deps','--no-index','--wheel-dir=dist','.'],src,log)
   run(['python3','-m','pip','install','--no-deps','--no-index',*map(str,(src/'dist').glob('*.whl'))],src,log)
  elif kind=='boost':
   run(['./bootstrap.sh','--prefix=/usr','--with-python=python3'],src,log)
   run(['./b2','-j'+jobs,'threading=multi','link=shared','install'],src,log)
  elif kind=='duktape':
   run(['make','-f','Makefile.sharedlibrary','INSTALL_PREFIX=/usr','-j'+jobs],src,log)
   run(['make','-f','Makefile.sharedlibrary','INSTALL_PREFIX=/usr','install'],src,log)
  elif kind=='lmdb':
   run(['make','-j'+jobs],src/'libraries/liblmdb',log)
   run(['make','prefix=/usr','install'],src/'libraries/liblmdb',log)
  elif kind in ('lua','wpa','vpx','ffmpeg'):
   run(['python3','/recipes/scripts/build-special-dependency.py',key,str(src),jobs],src,log)
  elif kind=='docbook':
   run(['python3','/recipes/scripts/install-docbook.py',key,str(src)],src,log)
  elif kind=='icu':
   (src/'_build').mkdir(exist_ok=True)
   run(['../source/configure','--prefix=/usr','--disable-static'],src/'_build',log)
   run(['make','-j'+jobs],src/'_build',log); run(['make','install'],src/'_build',log)
  else:
   raise ValueError('Unsupported build system: '+kind)
  run(['ldconfig'],src,log)
 stamp.write_text(item['sha256']+'\n')
 # Keep verified archives and logs, but reclaim compiled intermediates per package.
 assert dest.resolve().parent == (root/'packages').resolve()
 shutil.rmtree(dest)
 print('DONE',key,flush=True)

def foundation():
 build('cmake','cmake-bootstrap')
 build('vulkan-headers')
 for name in ['Mako','PyYAML']: build(name,'python')
 build('wayland','meson',['-Ddocumentation=false','-Dtests=false'])
 build('wayland-protocols','meson',['-Dtests=false'])
 build('vulkan-loader',opts=['-DBUILD_TESTS=OFF','-DBUILD_WSI_WAYLAND_SUPPORT=ON'])
 for name in ['xcb-util','xcb-util-image','xcb-util-keysyms','xcb-util-renderutil','xcb-util-wm','xcb-util-cursor','xcb-util-errors']: build(name,'autoconf')
 build('libxkbcommon','meson',['-Denable-docs=false','-Denable-xkbregistry=true'])
 build('libgudev','meson',['-Dintrospection=disabled','-Dvapi=disabled','-Dtests=disabled'])
 build('libinput','meson',['-Ddebug-gui=false','-Dtests=false','-Dlibwacom=false','-Ddocumentation=false','-Dudev-dir=/usr/lib/udev'])
 build('llvm',opts=['-DLLVM_ENABLE_PROJECTS=','-DLLVM_TARGETS_TO_BUILD=X86;AArch64;ARM;AMDGPU','-DLLVM_BUILD_LLVM_DYLIB=ON','-DLLVM_LINK_LLVM_DYLIB=ON','-DLLVM_INCLUDE_TESTS=OFF','-DLLVM_INCLUDE_BENCHMARKS=OFF','-DLLVM_INCLUDE_EXAMPLES=OFF','-DLLVM_ENABLE_RTTI=ON','-DLLVM_PARALLEL_LINK_JOBS=1','-DLLVM_PARALLEL_TABLEGEN_JOBS=2'])
 build('clang',opts=['-DLLVM_DIR=/usr/lib/cmake/llvm','-DLLVM_INCLUDE_TESTS=OFF','-DCLANG_BUILD_TESTS=OFF','-DCLANG_INCLUDE_TESTS=OFF','-DCLANG_BUILD_EXAMPLES=OFF','-DCLANG_BUILD_STATIC_ANALYZER=OFF','-DCLANG_BUILD_ARCMT=OFF','-DCLANG_BUILD_CLANG_TOOLS=OFF','-DCLANG_LINK_CLANG_DYLIB=ON','-DLLVM_LINK_LLVM_DYLIB=ON','-DLLVM_PARALLEL_LINK_JOBS=1','-DLLVM_PARALLEL_TABLEGEN_JOBS=2','-DCMAKE_CXX_FLAGS_RELEASE=-O2 -DNDEBUG --param ggc-min-expand=20 --param ggc-min-heapsize=32768'])
 build('spirv-headers')
 build('spirv-tools',opts=['-DSPIRV_SKIP_TESTS=ON','-DSPIRV_WERROR=OFF','-DBUILD_SHARED_LIBS=ON','-DSPIRV-Headers_SOURCE_DIR=/usr'])
 build('spirv-llvm-translator',opts=['-DLLVM_DIR=/usr/lib/cmake/llvm','-DLLVM_EXTERNAL_SPIRV_HEADERS_SOURCE_DIR=/usr','-DLLVM_SPIRV_INCLUDE_TESTS=OFF','-DBUILD_SHARED_LIBS=ON'])
 build('libxshmfence','autoconf')
 build('libXxf86vm','autoconf')
 build('mesa','meson',['-Dplatforms=x11,wayland','-Dgallium-drivers=llvmpipe,softpipe,svga,virgl,iris,crocus,radeonsi,nouveau','-Dvulkan-drivers=','-Dglvnd=disabled','-Dvalgrind=disabled','-Dlibunwind=disabled','-Dgallium-rusticl=false','-Dvideo-codecs=','-Dbuild-tests=false'])
 build('nasm','autoconf')
 build('libjpeg',opts=['-DENABLE_STATIC=OFF'])
 build('double-conversion',opts=['-DBUILD_SHARED_LIBS=ON'])
 build('libwebp',opts=['-DBUILD_SHARED_LIBS=ON','-DWEBP_BUILD_EXTRAS=OFF'])
 build('tiff',opts=['-Dtiff-tests=OFF','-Dtiff-docs=OFF'])
 build('icu','icu')
 build('qtbase',opts=['-DQT_BUILD_TESTS=OFF','-DQT_BUILD_EXAMPLES=OFF','-DFEATURE_openssl_linked=ON','-DFEATURE_icu=ON','-DFEATURE_sql_mysql=OFF','-DFEATURE_sql_psql=OFF','-DFEATURE_sql_odbc=OFF','-DFEATURE_journald=ON'])
 for name in ['qtshadertools','qtdeclarative','qtwayland','qtsvg','qtimageformats','qttools','qttranslations','qt5compat','qtwebchannel','qtwebsockets','qtserialport','qtpositioning','qtsensors','qtlocation']:
  build(name,opts=['-DQT_BUILD_TESTS=OFF','-DQT_BUILD_EXAMPLES=OFF'])
 build('extra-cmake-modules',opts=['-DBUILD_HTML_DOCS=OFF','-DBUILD_MAN_DOCS=OFF'])
 print('Selected packages built: '+os.environ['AETHER_BUILD_ONLY'] if os.environ.get('AETHER_BUILD_ONLY') else 'Qt/Wayland foundation built natively.',flush=True)

if __name__ == "__main__": foundation()
