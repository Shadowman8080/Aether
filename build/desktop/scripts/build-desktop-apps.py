#!/usr/bin/env python3
"""Build native everyday desktop applications after the Plasma stage."""
import runpy

build = runpy.run_path('/recipes/scripts/build-desktop-foundation.py')['build']
build('libarchive', 'autoconf')
build('poppler', opts=['-DENABLE_UNSTABLE_API_ABI_HEADERS=ON',
                     '-DENABLE_QT5=OFF', '-DENABLE_QT6=ON',
                     '-DENABLE_BOOST=OFF', '-DBUILD_GTK_TESTS=OFF',
                     '-DBUILD_QT6_TESTS=OFF', '-DBUILD_CPP_TESTS=OFF'])
for name in ('dolphin', 'konsole', 'kate', 'ark', 'gwenview', 'okular',
             'kcalc', 'kio-extras', 'kdialog'):
    build(name)
runpy.run_path('/recipes/scripts/build-vector.py', run_name='__main__')
print('Desktop applications installed; launch and file-operation tests remain required.', flush=True)
