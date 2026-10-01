from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import hashlib, json, urllib.request, tarfile
root=Path('/opt/aether')
items=[
 ('open-vm-tools-13.1.0-25218885.tar.gz','https://github.com/vmware/open-vm-tools/releases/download/stable-13.1.0/open-vm-tools-13.1.0-25218885.tar.gz','67a23d505aca77127b081445f758e269b1009e8824cf7f6f2d6efafb0b14d0fd'),
 ('VirtualBox-7.2.20.tar.bz2','https://download.virtualbox.org/virtualbox/7.2.20/VirtualBox-7.2.20.tar.bz2','5c2138213b72f36c129b92c2c267f2a40e9c98513f4c86a584327f09f9be706d')
]
def get(item):
    name,url,expected=item
    dest=root/'sources'/name
    if not dest.exists():
        tmp=dest.with_suffix('.part')
        with urllib.request.urlopen(url,timeout=120) as src,tmp.open('wb') as out:
            while data:=src.read(1024*1024):out.write(data)
        tmp.rename(dest)
    with dest.open('rb') as src:actual=hashlib.file_digest(src,'sha256').hexdigest()
    if actual!=expected:raise ValueError('Checksum mismatch: '+name)
    with tarfile.open(dest) as archive:archive.extractall(root/'sources',filter='data')
    print('Verified and extracted '+name,flush=True)
with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(get,items))
(root/'configs/guest-sources.json').write_text(json.dumps([dict(filename=n,url=u,sha256=h) for n,u,h in items],indent=2)+'\n')
