#!/usr/bin/env python3
"""Preserve build records off-image; remove only generated credential backups."""
from pathlib import Path
import subprocess
root = Path('/opt/aether/system')
subprocess.run(['mountpoint', '-q', str(root)], check=True)
archive = Path('/opt/aether/build/native-build-metadata')
archive.mkdir(exist_ok=True)
for name in ('sources', 'jhalfs', 'blfs_root'):
    source, dest = root / name, archive / name
    if source.exists():
        assert not dest.exists(), str(dest)
        subprocess.run(['mv', str(source), str(dest)], check=True)
for name in ('shadow-', 'gshadow-', 'passwd-', 'group-'):
    (root / 'etc' / name).unlink(missing_ok=True)
print('Build metadata preserved outside the deliverable image.')
