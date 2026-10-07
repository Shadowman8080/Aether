#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Installed update client: verified checks, explicit install, isolated system copy."""
import argparse,hashlib,json,os,platform,re,shutil,stat,subprocess,sys,time
from pathlib import Path
import slots
CONFIG=Path('/etc/aether-updates/repository.json')
STATUS=Path('/var/lib/aether-updates-status.json')
ARCHES={'x86_64':'amd64','aarch64':'arm64','i686':'i386','armv7l':'armhf'}
NAME=re.compile(r'[a-z0-9][a-z0-9+.-]{0,127}\Z')
def protected_file(path):
 info=path.lstat()
 if not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_mode&0o022:raise PermissionError('Trust configuration must be a root-owned regular file, not writable by other users')
 return path
def configured():
 if not CONFIG.exists():raise RuntimeError('Signed OS updates are not configured. An administrator must provision the release trust root and package-signing key before enabling a repository.')
 c=json.loads(protected_file(CONFIG).read_text())
 if c.get('channel') not in ('development','testing','stable'):raise ValueError('Invalid update channel')
 if not re.fullmatch(r'(?:[A-Fa-f0-9]{40}|[A-Fa-f0-9]{64})',c.get('package_fingerprint','')):raise ValueError('A full package-signing fingerprint is required')
 c['package_fingerprint']=c['package_fingerprint'].upper()
 for key,name in [('root','trusted-root.json'),('keyring','package-signers.gpg')]:c[key]=protected_file(CONFIG.parent/name)
 return c
def status(value):
 value={**value,'checked_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'automatic_installation':False,'automatic_restart':False}
 slots.atomic(STATUS,value,0o644);return value
def validate_catalog(catalog,arch):
 if catalog.get('architecture')!=arch:raise ValueError('Repository architecture does not match this system')
 packages=catalog.get('packages')
 if not isinstance(packages,list) or len(packages)>1000:raise ValueError('Invalid package catalog')
 seen=set()
 for p in packages:
  if not isinstance(p,dict) or not NAME.fullmatch(p.get('name','')) or p['name'] in seen:raise ValueError('Invalid or duplicate package name')
  seen.add(p['name'])
  if p.get('architecture') not in ('all',ARCHES.get(arch)):raise ValueError('Invalid native package architecture')
  if not re.fullmatch(r'[A-Za-z0-9.+:~_-]{1,128}',p.get('version','')):raise ValueError('Invalid package version')
  if not re.fullmatch(r'[a-f0-9]{64}',p.get('sha256','')):raise ValueError('Invalid package digest')
  if not re.fullmatch(r'packages/[A-Za-z0-9_.+~-]+\.deb',p.get('target','')):raise ValueError('Invalid package target')
 return packages
def check():
 c=configured()
 from client import AetherUpdateClient
 arch=platform.machine()
 client=AetherUpdateClient(slots.origin()/'var/lib/aether-updates',c['root'].read_bytes(),c['url'])
 client.refresh();catalog=client.catalog(arch,c['channel']);pending=[]
 for p in validate_catalog(catalog,arch):
  r=subprocess.run(['dpkg-query','-W','-f=${Version}',p['name']],capture_output=True,text=True)
  old=r.stdout.strip() if r.returncode==0 else ''
  if old:
   comparison=subprocess.run(['dpkg','--compare-versions',p['version'],'gt',old])
   if comparison.returncode==1:continue
   if comparison.returncode!=0:raise ValueError('Invalid installed or repository version')
  info=client.updater.get_targetinfo(p['target'])
  if info is None:raise ValueError('Catalog references an unauthorized package')
  pending.append({**p,'installed_version':old,'download_bytes':info.length})
 status({'state':'updates-available' if pending else 'up-to-date','packages':pending,'channel':c['channel'],'summary':str(catalog.get('summary',''))[:4000]})
 return c,client,pending
def stage_packages(c,client,packages):
 from package_signing import verify_package
 from release import inspect_package
 result=[]
 for p in packages:
  archive=client.stage(p['target']);signature=client.stage(p['target']+'.sig')
  # TUF uses consistent-snapshot hashed filenames. gpgv accepts an explicit signature path.
  expected=Path(str(archive)+'.sig')
  if signature!=expected:shutil.copyfile(signature,expected)
  if hashlib.sha256(archive.read_bytes()).hexdigest()!=p['sha256']:raise ValueError('Package differs from the signed catalog')
  verify_package(archive,c['keyring'],c['package_fingerprint'])
  ident=inspect_package(archive)
  if any(ident.get(k)!=p[v] for k,v in [('Package','name'),('Version','version'),('Architecture','architecture')]):raise ValueError('Package identity differs from catalog')
  result.append(archive)
 return result
def install():
 if not sys.stdin.isatty():raise RuntimeError('Installation requires an interactive review and confirmation')
 c,client,packages=check()
 if not packages:print('No newer packages are available.');return
 for p in packages:print(p['name'],p['installed_version'] or '(new)','→',p['version'],p['download_bytes'],'bytes')
 print('Updates will be installed into a separate system copy. Your home remains shared. No restart occurs automatically.')
 if input('Type INSTALL to download, verify and prepare a trial boot: ')!='INSTALL':return
 archives=stage_packages(c,client,packages)
 p,m=slots.create('signed package update');m['state']='building';slots.atomic(p/'manifest.json',m);root=p/'root'
 cache=root/'var/cache/aether-update';cache.mkdir(parents=True,exist_ok=True)
 names=[]
 for index,archive in enumerate(archives):
  name=f'{index:04d}.deb';shutil.copyfile(archive,cache/name);names.append('/var/cache/aether-update/'+name)
 policy=root/'usr/sbin/policy-rc.d';previous=None
 if policy.is_symlink():raise RuntimeError('Unexpected service policy symlink in candidate')
 if policy.exists():previous=(policy.read_bytes(),policy.stat().st_mode&0o777)
 try:
  policy.write_text('#!/bin/sh\nexit 101\n');policy.chmod(0o755)
  # No live host /dev, /proc or /run is exposed to candidate package scripts.
  for name,major,minor in [('null',1,3),('zero',1,5),('random',1,8),('urandom',1,9)]:
   target=root/'dev'/name
   if not target.exists():os.mknod(target,stat.S_IFCHR|0o666,os.makedev(major,minor))
  slots.run(['unshare','--net','chroot',str(root),'/usr/bin/env','SYSTEMD_OFFLINE=1','DEBIAN_FRONTEND=noninteractive','/usr/bin/dpkg','--install',*names])
  slots.run(['chroot',str(root),'/usr/sbin/ldconfig'])
 finally:
  if previous:policy.write_bytes(previous[0]);policy.chmod(previous[1])
  else:policy.unlink(missing_ok=True)
 m['state']='ready';m['packages']=[{'name':q['name'],'version':q['version']} for q in packages];slots.atomic(p/'manifest.json',m)
 slots.register(p,m);slots.activate(m['id'])
 status({'state':'restart-available','slot':m['id'],'packages':packages})
def main():
 p=argparse.ArgumentParser();p.add_argument('action',choices=['status','check','install']);a=p.parse_args()
 if a.action=='status':
  if not CONFIG.exists():print('Signed OS updates: not configured. Automatic installation and restart: disabled.');return
  print(STATUS.read_text() if STATUS.exists() else 'Repository configured; no successful check recorded.');return
 if os.geteuid()!=0:os.execvp('pkexec',['pkexec','/usr/bin/aether-update',a.action])
 try:
  with slots.lock():
   if a.action=='check':check();print(STATUS.read_text())
   else:install()
 except Exception as e:
  status({'state':'error','message':str(e)[:1000]});raise
if __name__=='__main__':
 try:main()
 except Exception as e:print('Update operation stopped:',str(e),file=sys.stderr);sys.exit(1)
