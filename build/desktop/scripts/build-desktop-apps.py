#!/usr/bin/env python3
"""Build native everyday desktop applications after the Plasma stage."""
import os, runpy, subprocess

build = runpy.run_path('/recipes/scripts/build-desktop-foundation.py')['build']
# The graphical installer is an end-user tool, so the apps stage owns it. It
# also provides the --welcome Try/Install chooser used on the live media.
# The backend formats the EFI system partition, so the live image needs a FAT
# formatter; the dependency stage was already running when this was added.
build('dosfstools', 'autoconf')
subprocess.run(['cmake','-S','/recipes/installer','-B','/build/installer','-G','Ninja','-DCMAKE_BUILD_TYPE=Release','-DCMAKE_INSTALL_PREFIX=/usr'],check=True)
subprocess.run(['cmake','--build','/build/installer','--parallel',str(os.cpu_count())],check=True)
subprocess.run(['cmake','--install','/build/installer'],check=True)
build('libarchive', 'autoconf')
# poppler treats OpenJPEG as mandatory; JPEG2000 images inside PDFs need it.
build('openjpeg2', opts=['-DBUILD_CODEC=OFF'])
# NSS3 only adds PDF signature verification and the image ships no NSS, so
# poppler's soft-mandatory check is satisfied by turning that feature off.
build('poppler', opts=['-DENABLE_UNSTABLE_API_ABI_HEADERS=ON',
                     '-DENABLE_QT5=OFF', '-DENABLE_QT6=ON', '-DENABLE_NSS3=OFF',
                     '-DENABLE_BOOST=OFF', '-DBUILD_GTK_TESTS=OFF',
                     '-DBUILD_QT6_TESTS=OFF', '-DBUILD_CPP_TESTS=OFF'])
for name in ('dolphin', 'konsole', 'kate', 'ark'):
    build(name)
# gwenview hard-requires kImageAnnotator, which in turn requires kColorPicker;
# neither is in the BLFS book, so both are pinned as direct sources.
build('kColorPicker', opts=['-DBUILD_SHARED_LIBS=ON', '-DBUILD_WITH_QT6=ON',
                         '-DBUILD_EXAMPLE=OFF'])
build('kImageAnnotator', opts=['-DBUILD_SHARED_LIBS=ON', '-DBUILD_WITH_QT6=ON',
                            '-DBUILD_EXAMPLE=OFF'])
build('gwenview')
# PDF support stays required through Poppler; PostScript, DjVu, ePub, Mobipocket,
# Markdown and Exif rotation would otherwise pull ghostscript and four more
# libraries into the image, so they are explicitly optional.
build('okular', opts=['-DFORCE_NOT_REQUIRED_DEPENDENCIES=KF6Wallet;KF6DocTools;'
                      'Qt6Qml;TIFF;LibSpectre;KExiv2Qt6;DjVuLibre;EPub;'
                      'QMobipocket6;QMobiPocket6;Discount'])
for name in ('kcalc', 'kdialog'):
    build(name)
# WPAD proxy discovery is the only libproxy user and this image ships no
# libproxy, so keep that optional component out instead of adding a proxy stack.
build('kio-extras', opts=['-DWITH_LIBPROXY=OFF'])
runpy.run_path('/recipes/scripts/build-vector.py', run_name='__main__')
# Plug-and-play: the Aether Devices manager, the udev/hwdb/driver wiring and
# the hardware enumeration utilities (lspci / lsusb).
runpy.run_path('/recipes/scripts/build-aether-devices.py', run_name='__main__')
runpy.run_path('/recipes/scripts/build-desktop-pnp-utils.py', run_name='__main__')
print('Desktop applications installed; launch and file-operation tests remain required.', flush=True)
