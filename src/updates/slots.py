#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Versioned ext4 system copies with one-shot GRUB selection and health commit.

User homes are shared; the system copy includes its own package database.
This is not a disk-failure backup. Only local root-owned slot manifests authorize
boot selection. Never remove a slot automatically.
"""
import fcntl,json,os,re,shutil,subprocess,tempfile,time,uuid
from pathlib import Path
from contextlib import contextmanager
ID=re.compile(r'[0-9]{8}T[0-9]{6}-[0-9a-f]{8}\Z')
def run(args,**kw):return subprocess.run(args,check=True,**kw)
def output(args):return subprocess.check_output(args,text=True).strip()
def current_id(cmdline=None):
 ids=[v.split('=',1)[1] for v in (cmdline if cmdline is not None else Path('/proc/cmdline').read_text()).split() if v.startswith('aether.slot=')]
 if len(ids)>1 or (ids and not ID.fullmatch(ids[0])):raise ValueError('Invalid boot slot')
 return ids[0] if ids else None
def origin():
 if current_id():
  p=Path('/run/aether-origin')
  if not os.path.ismount(p) or 'ID=aether' not in (p/'etc/os-release').read_text().splitlines():raise RuntimeError('Original system mount is unavailable')
  return p
 return Path('/')
def atomic(path,value,mode=0o600):
 path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
 fd,name=tempfile.mkstemp(dir=path.parent)
 try:
  with os.fdopen(fd,'w') as f:json.dump(value,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
  os.chmod(name,mode);os.replace(name,path)
  fd=os.open(path.parent,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
 finally:
  if os.path.exists(name):os.unlink(name)
@contextmanager
def lock():
 if os.geteuid()!=0:raise PermissionError('Administrator access is required')
 d=Path('/run/aether-maintenance');d.mkdir(mode=0o700,exist_ok=True)
 if d.is_symlink() or d.stat().st_uid!=0 or d.stat().st_mode&0o077:raise PermissionError('Unsafe maintenance lock directory')
 with (d/'lock').open('w') as f:
  fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
  yield
def store():
 # The checker permits writes to this exact path when running from a trial slot.
 # Create it before trial boot, including when no repository is configured yet.
 (origin()/'var/lib/aether-updates').mkdir(parents=True,exist_ok=True,mode=0o700)
 d=origin()/'var/lib/aether/slots';d.mkdir(parents=True,exist_ok=True,mode=0o700)
 if d.is_symlink() or d.stat().st_uid!=0 or d.stat().st_mode&0o077:raise PermissionError('Unsafe system slot directory')
 return d
def checked_slot(identifier):
 if not ID.fullmatch(identifier):raise ValueError('Invalid checkpoint identifier')
 p=store()/identifier
 if p.is_symlink() or not p.is_dir() or p.resolve()!=p:raise ValueError('Invalid checkpoint directory')
 m=json.loads((p/'manifest.json').read_text())
 if m.get('id')!=identifier or m.get('state') not in ('ready','pending','healthy'):raise ValueError('Checkpoint is incomplete')
 return p,m
def publish_status():
 records=[]
 for p in sorted(store().iterdir()):
  if not ID.fullmatch(p.name):continue
  try:_,m=checked_slot(p.name);records.append({k:m.get(k) for k in ('id','state','created','purpose')})
  except (OSError,ValueError):continue
 value={'current':current_id() or 'original','checkpoints':records}
 atomic(Path('/var/lib/aether-recovery-status.json'),value,0o644)
 if origin()!=Path('/'):atomic(origin()/'var/lib/aether-recovery-status.json',value,0o644)
 return value
def create(purpose='manual checkpoint'):
 if output(['findmnt','-n','-o','FSTYPE','/'])!='ext4':raise RuntimeError('This release supports installed ext4 systems only; live overlays cannot create system copies')
 # Keep enough space for a complete copy plus working room, without counting old slots.
 estimate=int(output(['du','-sx','--block-size=1','--exclude=/var/lib/aether','--exclude=/home','--exclude=/run','--exclude=/var/cache','--exclude=/var/log','/']).split()[0])
 if shutil.disk_usage(store()).free < estimate+2*1024**3:raise RuntimeError('Insufficient free space for a system copy plus 2 GiB working room')
 identifier=time.strftime('%Y%m%dT%H%M%S',time.gmtime())+'-'+uuid.uuid4().hex[:8]
 p=store()/identifier;p.mkdir(mode=0o700);root=p/'root';root.mkdir()
 excludes=['/var/lib/aether','/var/lib/aether-updates/downloads','/home/*','/run/*','/dev/*','/proc/*','/sys/*','/tmp/*','/mnt/*','/media/*','/var/cache/*','/var/log/*','/lost+found','/boot/*']
 # Locks coordinate with dpkg/apt as well as other Aether maintenance actions.
 with open('/var/lib/dpkg/lock-frontend','a') as frontend,open('/var/lib/dpkg/lock','a') as database:
  fcntl.lockf(frontend,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.lockf(database,fcntl.LOCK_EX|fcntl.LOCK_NB)
  run(['rsync','-aHAXx','--numeric-ids',*['--exclude='+v for v in excludes], '/',str(root)+'/'])
 for name in ('dev','proc','sys','run','tmp','home','mnt','media','boot','var/cache','var/log'):(root/name).mkdir(parents=True,exist_ok=True)
 (root/'tmp').chmod(0o1777)
 for pattern in ('vmlinuz-*','initramfs-*.img','config-*','System.map-*'):
  for f in Path('/boot').glob(pattern):
   if f.is_file() and not f.is_symlink():shutil.copy2(f,root/'boot'/f.name)
 (root/'etc/aether-slot-id').write_text(identifier+'\n')
 m={'schema':1,'id':identifier,'state':'ready','created':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'purpose':purpose}
 atomic(p/'manifest.json',m);return p,m
def register(p,m):
 root=p/'root';kernels=[v.name.removeprefix('vmlinuz-') for v in (root/'boot').glob('vmlinuz-*')]
 kernels=[v for v in kernels if re.fullmatch(r'[A-Za-z0-9._+-]+',v) and (root/'boot'/('initramfs-'+v+'.img')).is_file()]
 if not kernels:raise RuntimeError('No matching kernel and initramfs in checkpoint')
 release=run(['sort','-V'],input='\n'.join(kernels),text=True,capture_output=True).stdout.splitlines()[-1]
 # /boot is shared on installed systems with a separate boot filesystem. For
 # single-partition VM disks, use the original physical boot directory.
 boot=Path('/boot') if os.path.ismount('/boot') else origin()/'boot'
 boot.mkdir(exist_ok=True);dest=boot/'aether-slots'/m['id'];dest.mkdir(parents=True,exist_ok=False)
 for name,src in [('linux','vmlinuz-'+release),('initrd','initramfs-'+release+'.img')]:shutil.copy2(root/'boot'/src,dest/name)
 root_uuid=output(['findmnt','-n','-o','UUID','/']);boot_uuid=output(['findmnt','-n','-o','UUID','-T',str(boot)])
 if not all(re.fullmatch(r'[A-Fa-f0-9-]+',v) for v in (root_uuid,boot_uuid)):raise RuntimeError('Could not identify root and boot filesystems')
 prefix='/aether-slots/' if os.path.ismount('/boot') else '/boot/aether-slots/'
 luks=[v for v in Path('/proc/cmdline').read_text().split() if v.startswith('aether.luks=')]
 if any(not re.fullmatch(r'aether.luks=[A-Fa-f0-9-]+',v) for v in luks):raise ValueError('Invalid encrypted-root identifier')
 entry=f"menuentry 'Aether system {m['id']}' --id 'aether-slot-{m['id']}' {{\n search --no-floppy --fs-uuid --set=root {boot_uuid}\n linux {prefix}{m['id']}/linux root=UUID={root_uuid} {' '.join(luks)} aether.slot={m['id']} rootwait rw console=ttyS0,115200n8 console=tty0 quiet splash\n initrd {prefix}{m['id']}/initrd\n}}\n"
 fragment=boot/'grub/aether-slots.cfg';old=fragment.read_text() if fragment.exists() else ''
 temp=fragment.with_suffix('.new');temp.write_text(old+entry);run(['grub-script-check',str(temp)]);os.replace(temp,fragment)
 main=boot/'grub/grub.cfg';text=main.read_text()
 if '# Aether versioned systems' not in text:
  shutil.copy2(main,main.with_name('grub-before-versioned-systems.cfg'))
  loader='''# Aether versioned systems
if [ -s $prefix/grubenv ]; then load_env; fi
if [ -n "$next_entry" ]; then
 set default="$next_entry"
 set next_entry=
 save_env next_entry
elif [ -n "$saved_entry" ]; then
 set default="$saved_entry"
fi
'''
  # Original defaults run first; this override runs before menu entries.
  n=text.find('menuentry ')
  if n<0:raise RuntimeError('Unrecognized GRUB configuration')
  text=text[:n]+loader+text[n:]+ '\nsource $prefix/aether-slots.cfg\n'
  tmp=main.with_suffix('.new');tmp.write_text(text);run(['grub-script-check',str(tmp)]);os.replace(tmp,main)
 env=boot/'grub/grubenv'
 if not env.exists():run(['grub-editenv',str(env),'create'])
 m['boot_directory']=str(boot);m['kernel']=release;atomic(p/'manifest.json',m);os.sync();publish_status()
 return env
def activate(identifier):
 p,m=checked_slot(identifier)
 boot=Path('/boot') if os.path.ismount('/boot') else origin()/'boot'
 if not (boot/'aether-slots'/identifier/'initrd').is_file():raise RuntimeError('Checkpoint has no boot entry')
 run(['grub-editenv',str(boot/'grub/grubenv'),'set','next_entry=aether-slot-'+identifier])
 m['state']='pending';atomic(p/'manifest.json',m);publish_status();os.sync()
 print('Prepared one trial boot. Restart when ready. The previous default remains available until the health check succeeds.')
def bless():
 identifier=current_id()
 if not identifier:return
 p,m=checked_slot(identifier)
 if m['state']!='pending':return
 if Path('/etc/aether-slot-id').read_text().strip()!=identifier:raise RuntimeError('Boot identity mismatch')
 for _ in range(30):
  if subprocess.run(['systemctl','is-active','--quiet','lightdm.service']).returncode==0:break
  time.sleep(3)
 else:raise RuntimeError('Desktop service did not become healthy; previous boot default retained')
 boot=Path('/boot') if os.path.ismount('/boot') else origin()/'boot'
 run(['grub-editenv',str(boot/'grub/grubenv'),'set','saved_entry=aether-slot-'+identifier])
 m['state']='healthy';atomic(p/'manifest.json',m);publish_status();os.sync()
