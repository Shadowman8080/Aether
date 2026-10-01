#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path
import re
import urllib.request

root = Path('/opt/aether')
version = '6.18.54'
name = f'linux-{version}.tar.xz'
base = 'https://cdn.kernel.org/pub/linux/kernel/v6.x/'
sums = urllib.request.urlopen(base+'sha256sums.asc', timeout=60).read().decode()
match = re.search(r'^([a-f0-9]{64})\s+'+re.escape(name)+r'$', sums, re.M)
if not match: raise RuntimeError('Kernel archive absent from upstream checksum list')
expected = match[1]
archive = root/'sources'/name
if not archive.exists():
    tmp = archive.with_suffix('.part')
    h = hashlib.sha256()
    with urllib.request.urlopen(base+name, timeout=60) as response, tmp.open('wb') as out:
        while block := response.read(1024*1024):
            out.write(block); h.update(block)
    if h.hexdigest() != expected:
        tmp.unlink(); raise RuntimeError('Kernel checksum mismatch')
    tmp.rename(archive)
else:
    with archive.open('rb') as source: actual = hashlib.file_digest(source, 'sha256').hexdigest()
    if actual != expected: raise RuntimeError('Cached kernel checksum mismatch')
(root/'next/configs/kernel-source.json').write_text(json.dumps({
    'version':version, 'url':base+name, 'sha256':expected,
    'checksums_url':base+'sha256sums.asc', 'verification':'SHA256 against upstream HTTPS checksum list'
}, indent=2)+'\n')
print(f'Verified {name}: {expected}')
