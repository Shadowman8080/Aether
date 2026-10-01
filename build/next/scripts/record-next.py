#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path
import subprocess

root = Path('/opt/aether')
ignore = root/'.gitignore'
text = ignore.read_text()
for entry in ('/system/', '**/__pycache__/', '**/*.pyc'):
    if entry not in text.splitlines(): text += entry+'\n'
ignore.write_text(text)
sources = {}
for path in sorted((root/'sources/lfs-cache').iterdir()):
    if not path.is_file() or path.name.endswith('.part'): continue
    with path.open('rb') as handle: checksum = hashlib.file_digest(handle, 'sha256').hexdigest()
    sources[path.name] = {'bytes':path.stat().st_size, 'sha256':checksum}
(root/'next/configs/source-cache-lock.json').write_text(json.dumps(sources, indent=2)+'\n')
for name, directory in [('llama.cpp','llama.cpp'), ('pacman','pacman-7.1.0')]:
    commit = subprocess.check_output(['git','-C',str(root/'sources'/directory),'rev-parse','HEAD'], text=True)
    (root/'next/configs'/f'{name}.commit').write_text(commit)
for path in (root/'next/desktop').rglob('*.json'): json.loads(path.read_text())
import xml.etree.ElementTree as ET
for path in (root/'next/desktop').rglob('*.svg'): ET.parse(path)
print(f'Recorded {len(sources)} source-cache checksums and pinned source commits; desktop metadata parsed.')
