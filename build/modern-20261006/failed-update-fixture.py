#!/usr/bin/env python3
"""Run ONLY inside a disposable guest. Fault injection after verified staging.

TUF/GPG verification is tested separately. This fixture substitutes the download
boundary, exercises the real clone/chroot/dpkg path, then kills an install group.
It deliberately leaves an incomplete system copy for inspection.
"""
import json,os,signal,subprocess,sys,time
from pathlib import Path
from unittest.mock import patch
sys.path[:0]=['/usr/lib/aether-updates','/usr/lib/aether-updates/vendor']
import runtime,slots
assert os.geteuid()==0
assert Path('/run/aether-disposable-test').read_text()=='modern-20261006\n','Disposable test marker required'
assert not Path('/etc/aether-slot-id').exists(),'Use a clean disposable guest'
temp=Path('/tmp/update-fault-fixture');temp.mkdir()
boot=Path('/boot/grub/grub.cfg');before=boot.read_bytes()
env=Path('/boot/grub/grubenv');env_before=env.read_bytes() if env.exists() else None
marker=Path('/etc/aether-update-fault-proof');assert not marker.exists()
db=Path('/var/lib/dpkg/status').read_bytes()

def package(name,body):
 p=temp/name;(p/'DEBIAN').mkdir(parents=True)
 (p/'DEBIAN/control').write_text(f'Package: {name}\nVersion: 1\nArchitecture: all\nMaintainer: Aether test fixture\nDescription: Disposable installation failure fixture\n')
 script=p/'DEBIAN/postinst';script.write_text('#!/bin/sh\nset -eu\n'+body+'\n');script.chmod(0o755)
 archive=temp/(name+'.deb');subprocess.run(['dpkg-deb','--build',str(p),str(archive)],check=True)
 return archive

archive=package('aether-test-fails','echo failed > /etc/aether-update-fault-proof\nexit 42')
metadata=[{'name':'aether-test-fails','version':'1','installed_version':'','download_bytes':archive.stat().st_size}]
old=set(slots.store().iterdir())
with patch.object(runtime,'check',return_value=({},None,metadata)),patch.object(runtime,'stage_packages',return_value=[archive]),patch('builtins.input',return_value='INSTALL'),patch.object(sys.stdin,'isatty',return_value=True):
 try:runtime.install()
 except subprocess.CalledProcessError:pass
 else:raise AssertionError('Failing package unexpectedly installed')
new=set(slots.store().iterdir())-old;assert len(new)==1
candidate=new.pop();root=candidate/'root';manifest=json.loads((candidate/'manifest.json').read_text())
assert manifest['state']=='building'
assert (root/'etc/aether-update-fault-proof').read_text().strip()=='failed'

def unchanged():
 assert not marker.exists(),'Maintainer script modified the running root'
 assert Path('/var/lib/dpkg/status').read_bytes()==db,'Running package database changed'
 assert boot.read_bytes()==before,'Boot menu changed'
 assert (env.read_bytes() if env.exists() else None)==env_before,'Boot selection changed'
 try:slots.checked_slot(candidate.name)
 except ValueError:pass
 else:raise AssertionError('Incomplete candidate is boot-selectable')

unchanged();print('PASS real failing maintainer script is confined to incomplete candidate',flush=True)
# Reuse this already disposable incomplete root to avoid a second full copy.
# The first pass above exercised the actual system-copy implementation.
archive=package('aether-test-interrupted','echo interrupted > /etc/aether-update-fault-proof\nwhile :; do sleep 1; done')
child=temp/'interrupted.py'
child.write_text('''import sys,json
from pathlib import Path
from unittest.mock import patch
sys.path[:0]=['/usr/lib/aether-updates','/usr/lib/aether-updates/vendor']
import runtime,slots
p=Path(sys.argv[1]);archive=Path(sys.argv[2]);m=json.loads((p/'manifest.json').read_text())
metadata=[{'name':'aether-test-interrupted','version':'1','installed_version':'','download_bytes':archive.stat().st_size}]
with patch.object(runtime,'check',return_value=({},None,metadata)),patch.object(runtime,'stage_packages',return_value=[archive]),patch.object(slots,'create',return_value=(p,m)),patch('builtins.input',return_value='INSTALL'),patch.object(sys.stdin,'isatty',return_value=True):runtime.install()
''')
p=subprocess.Popen(['python3',str(child),str(candidate),str(archive)],start_new_session=True)
try:
 for _ in range(180):
  if (root/'etc/aether-update-fault-proof').read_text().strip()=='interrupted':break
  assert p.poll() is None,'Install stopped before interruption fixture'
  time.sleep(1)
 else:raise RuntimeError('Interrupted-install fixture did not start')
finally:
 if p.poll() is None:os.killpg(p.pid,signal.SIGKILL)
 p.wait()
unchanged();assert json.loads((candidate/'manifest.json').read_text())['state']=='building'
print('PASS killed install group leaves original root and boot selection unchanged',flush=True)
Path('/tmp/update-fault-fixture-PASS').write_text('Failed maintainer script and interrupted install remained isolated. Verification boundary mocked; TUF/GPG tested separately.\n')
