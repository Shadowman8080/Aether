#!/usr/bin/env python3
"""Restore pinned extra source trees without changing an existing checkout."""
from pathlib import Path
import re
import subprocess

root = Path('/opt/aether')
repos = [
    ('llama.cpp', 'llama.cpp', 'https://github.com/ggml-org/llama.cpp.git'),
]
for name, directory, url in repos:
    revision = (root/'next/configs'/f'{name}.commit').read_text().strip()
    if not re.fullmatch(r'[0-9a-f]{40}', revision): raise ValueError('Invalid pinned revision')
    destination = root/'sources'/directory
    if destination.exists():
        actual = subprocess.check_output(['git','-C',str(destination),'rev-parse','HEAD'], text=True).strip()
        if actual != revision: raise RuntimeError(f'{directory} has a different revision; inspect it before replacing')
    else:
        subprocess.run(['git','init',str(destination)], check=True)
        subprocess.run(['git','-C',str(destination),'fetch','--depth=1',url,revision], check=True)
        subprocess.run(['git','-C',str(destination),'checkout','--detach','FETCH_HEAD'], check=True)
    print(f'{name}: {revision}')
