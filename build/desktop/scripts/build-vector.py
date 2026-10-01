#!/usr/bin/env python3
"""Compile Vector inside the native Aether desktop build root."""
from pathlib import Path
import os
import subprocess

build = Path('/build/vector')
build.mkdir(parents=True, exist_ok=True)
with Path('/build/logs/vector.log').open('w') as log:
    for command in (
        ['cmake', '-S', '/recipes/vector', '-B', str(build), '-G', 'Ninja',
         '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_INSTALL_PREFIX=/usr'],
        ['cmake', '--build', str(build), '--parallel', str(os.cpu_count())],
        ['cmake', '--install', str(build)],
    ):
        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
print('VECTOR_BUILD_PASS', flush=True)
