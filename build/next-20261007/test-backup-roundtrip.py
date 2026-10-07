#!/usr/bin/env python3
"""Verify encrypted backup/restore and corruption detection in a disposable repo.

This tests the backup engine, not destination independence or immutable storage.
No configured Aether backup repository or credential is read.
"""
import argparse,json,os,secrets,subprocess,tempfile
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--restic',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args();binary=args.restic.resolve(strict=True)
args.output.mkdir(parents=True,exist_ok=False)
results=[]
with tempfile.TemporaryDirectory(prefix='aether-backup-fixture-') as temporary:
 root=Path(temporary);key=root/'key';key.write_text(secrets.token_urlsafe(48)+'\n');key.chmod(0o600)
 repo=root/'repository';source=root/'source';source.mkdir()
 files={'document.txt':b'Aether restore fixture\n','nested/binary.dat':bytes(range(256))*1024,'private.txt':b'Private test fixture, no user data\n'}
 for name,data in files.items():
  path=source/name;path.parent.mkdir(exist_ok=True);path.write_bytes(data)
 (source/'private.txt').chmod(0o600)
 (source/'shortcut').symlink_to('document.txt')
 env={k:v for k,v in os.environ.items() if not k.startswith(('RESTIC_','AWS_','B2_','AZURE_','GOOGLE_'))}
 env['HOME']=str(root)
 def run(*command,expect_success=True):
  result=subprocess.run([str(binary),'--no-cache','--repo',str(repo),'--password-file',str(key),*command],env=env,text=True,capture_output=True,timeout=180)
  if expect_success and result.returncode:raise RuntimeError(f'{command[0]} failed: {result.stderr}')
  return result
 run('init');run('backup','--one-file-system','--',str(source))
 snapshot=json.loads(run('snapshots','--json').stdout)[0]['id']
 run('check','--read-data');results.append({'check':'encrypted repository integrity','passed':True})
 destination=root/'restore';destination.mkdir(mode=0o700)
 run('restore',snapshot,'--target',str(destination),'--verify')
 restored=destination/str(source).lstrip('/')
 for name,data in files.items():assert (restored/name).read_bytes()==data,name
 assert (restored/'private.txt').stat().st_mode&0o777==0o600
 assert (restored/'shortcut').is_symlink() and os.readlink(restored/'shortcut')=='document.txt'
 assert (source/'document.txt').read_bytes()==files['document.txt']
 results.append({'check':'restore contents permissions and symlink into new directory','passed':True})
 # Deliberately damage this throwaway encrypted repository only.
 pack=next(path for path in (repo/'data').rglob('*') if path.is_file())
 # restic makes packs read-only. Permit deliberate corruption of this owned
 # fixture even when CI runs without root; never change a real repository.
 pack.chmod(0o600)
 with pack.open('r+b') as stream:
  original=stream.read(1);assert original;stream.seek(0);stream.write(bytes([original[0]^1]))
 damaged=run('check','--read-data',expect_success=False)
 assert damaged.returncode!=0,'Corrupted repository incorrectly passed integrity check'
 results.append({'check':'corrupted encrypted data is rejected','passed':True})
report={'engine':subprocess.check_output([str(binary),'version'],text=True).strip(),'checks':results,'scope':'Disposable local engine test; not proof of independent or immutable backup storage'}
(args.output/'checks.json').write_text(json.dumps(report,indent=2)+'\n')
print('BACKUP_ROUNDTRIP_PASS')
