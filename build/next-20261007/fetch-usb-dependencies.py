#!/usr/bin/env python3
import hashlib,json,tarfile,urllib.request
from pathlib import Path
b=Path('/opt/aether/build/next-20261007')
items=[
 {'key':'abseil','version':'20250512.1','url':'https://github.com/abseil/abseil-cpp/releases/download/20250512.1/abseil-cpp-20250512.1.tar.gz','sha256':'9b7a064305e9fd94d124ffa6cc358592eb42b5da588fb4e07d09254aa40086db'},
 {'key':'libqb','version':'2.0.10','url':'https://github.com/ClusterLabs/libqb/releases/download/v2.0.10/libqb-2.0.10.tar.xz','sha256':'326a69fb5b2ee4479f0db4f98d10d670ad0798b5ded8c4cfd585b765fd8941e8'},
 {'key':'protobuf','version':'36.2','url':'https://github.com/protocolbuffers/protobuf/releases/download/v36.2/protobuf-36.2.tar.gz','sha256':'3d9642a662d10e68ebae5e53f14dcce5105684212d5078f8e0d47d1ab3ae6b64'}]
for item in items:
 item['archive']=item['url'].rsplit('/',1)[1];item['verification']='Pinned upstream GitHub release asset SHA-256 over HTTPS'
 target=b/'sources'/item['archive']
 if not target.exists():
  temporary=target.with_suffix(target.suffix+'.partial')
  with urllib.request.urlopen(item['url'],timeout=90) as response,temporary.open('wb') as stream:
   while chunk:=response.read(1024*1024):stream.write(chunk)
  assert hashlib.file_digest(temporary.open('rb'),'sha256').hexdigest()==item['sha256'];temporary.rename(target)
 assert hashlib.file_digest(target.open('rb'),'sha256').hexdigest()==item['sha256']
 directory=b/'inspect'/item['key'];directory.mkdir(exist_ok=True)
 with tarfile.open(target) as archive:archive.extractall(directory,filter='data')
(b/'usb-dependencies.lock.json').write_text(json.dumps(items,indent=2)+'\n')
print('USB dependencies downloaded and checksummed')
