#!/usr/bin/env python3
"""Core Plasma desktop; run after foundation, dependencies and Frameworks."""
import runpy

build = runpy.run_path('/recipes/scripts/build-desktop-foundation.py')['build']

def plasma(name, *options):
    build(name, opts=['-DBUILD_QT5=OFF', '-DBUILD_QT6=ON', *options])

for name in ('kdecoration', 'libkscreen', 'libksysguard', 'breeze', 'breeze-gtk',
             'layer-shell-qt', 'plasma-activities', 'libplasma', 'kscreenlocker',
             'kglobalacceld', 'kwayland', 'aurorae', 'knighttime', 'kpipewire',
             'kwin', 'kwin-x11', 'plasma5support', 'plasma-activities-stats'):
    plasma(name)
plasma('plasma-workspace', '-DWITH_X11_SESSION=ON', '-DPACKAGEKIT_OFFLINE_UPDATES=OFF',
       '-DUBUNTU_PACKAGEKIT=OFF')
for name in ('bluedevil', 'kde-gtk-config', 'kmenuedit', 'kscreen', 'kwallet-pam',
             'kwrited', 'milou'):
    plasma(name)
# OpenConnect's embedded authentication browser is a separate optional dependency.
plasma('plasma-nm', '-DBUILD_OPENCONNECT=OFF')
for name in ('plasma-pa', 'polkit-kde-agent', 'powerdevil', 'plasma-desktop',
             'sddm-kcm', 'xdg-desktop-portal-kde', 'kde-cli-tools', 'systemsettings',
             'qqc2-breeze-style', 'ksystemstats', 'plasma-systemmonitor',
             'ocean-sound-theme'):
    plasma(name)
plasma('kdeplasma-addons', '-DBUILD_KAMELEON=OFF')
plasma('print-manager', '-DSCP_INSTALL=OFF')
plasma('spectacle')
plasma('kinfocenter')
print('Core Plasma packages built. Session integration and boot tests remain required.', flush=True)
