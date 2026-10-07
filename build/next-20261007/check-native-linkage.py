#!/usr/bin/env python3
"""Audit staged ELF dependencies in the candidate, including private systemd DSOs."""
import json,subprocess
from pathlib import Path
b=Path('/opt/aether/build/next-20261007');root=b/'root';checked=[];failures=[];contexts=[]
for name in ('libcbor','libfido2','tpm2-tss','apparmor','devmapper','cryptsetup','systemd','controlcenter'):
 stage=b/'stage'/name
 for path in stage.rglob('*'):
  if path.is_symlink() or not path.is_file():continue
  with path.open('rb') as stream:magic=stream.read(4)
  if magic!=b'\x7fELF':continue
  relative='/'+str(path.relative_to(stage))
  command=['chroot',str(root)]
  if relative=='/usr/lib/systemd/libsystemd-core-261.so':
   # PID1 directly loads both core and shared using its own RUNPATH. A standalone
   # ldd of this private DSO lacks that context; also audit PID1 without overrides.
   command+=['/usr/bin/env','LD_LIBRARY_PATH=/usr/lib/systemd']
   contexts.append({'path':relative,'private_library_directory':'/usr/lib/systemd'})
  result=subprocess.run([*command,'ldd',relative],capture_output=True,text=True)
  output=result.stdout+result.stderr
  if 'not found' in output or (result.returncode and 'not a dynamic executable' not in output):failures.append({'path':relative,'output':output})
  checked.append(relative)
assert '/usr/lib/systemd/systemd' in checked
report={'checked_elf_files':len(checked),'private_loader_contexts':contexts,'failures':failures}
(b/'native-linkage.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report));assert not failures
