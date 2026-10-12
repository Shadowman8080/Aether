#!/usr/bin/env python3
"""Build the hardware enumeration utilities: pciutils (lspci) and
usbutils (lsusb). Both are small, dependency-light, and give the Aether
console and Aether Devices a canonical way to name PCI/USB hardware."""
import runpy

ns = runpy.run_path('/recipes/scripts/build-desktop-foundation.py')
build = ns['build']

build('pciutils', 'make', ['PREFIX=/usr', 'SHARED=no', 'ZLIB=no'])
build('usbutils', 'meson')
print('PnP utilities installed (lspci, lsusb).', flush=True)