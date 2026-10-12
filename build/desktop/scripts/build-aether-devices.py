#!/usr/bin/env python3
"""Build and install Aether Devices: the plug-and-play device manager,
its udev/hwdb/modules-load wiring and the login-session notifier."""
from pathlib import Path
import os
import shutil
import subprocess

source = Path('/recipes/devices')
assert source.exists(), 'aether-devices source tree not staged at /recipes/devices'
build = Path('/build/devices')
build.mkdir(parents=True, exist_ok=True)

with (Path('/build/logs/devices.log')).open('w') as log:
    for command in (
        ['cmake', '-S', str(source), '-B', str(build), '-G', 'Ninja',
         '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_INSTALL_PREFIX=/usr'],
        ['cmake', '--build', str(build), '--parallel', str(os.cpu_count())],
        ['cmake', '--install', str(build)],
    ):
        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)

# Plug-and-play assets land in the image root so udev, systemd-modules-load
# and the login session pick them up on the next boot.
root = Path('/')
assets = source / 'assets'
for path in sorted(assets.rglob('*')):
    target = root / path.relative_to(assets)
    if path.is_dir():
        target.mkdir(parents=True, exist_ok=True)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)

rescan = root / 'usr/libexec/aether-device-rescan'
if rescan.exists():
    rescan.chmod(0o755)

print('AETHER_DEVICES_BUILD_PASS', flush=True)