#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Per-user desktop preferences. No privilege escalation or model commands."""
import argparse,json,os,shutil,subprocess,tempfile
from pathlib import Path
def config_dir():
 return Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))/'aether'
def atomic_json(path,value):
 path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
 fd,name=tempfile.mkstemp(dir=path.parent)
 try:
  with os.fdopen(fd,'w') as f:json.dump(value,f);f.flush();os.fsync(f.fileno())
  os.replace(name,path)
 finally:
  if os.path.exists(name):os.unlink(name)
SETTINGS=[('kdeglobals','KDE','AnimationDurationFactor','0'),('kwinrc','Plugins','blurEnabled','false'),('kwinrc','Plugins','backgroundcontrastEnabled','false'),('baloofilerc','Basic Settings','Indexing-Enabled','false')]
def run(args):return subprocess.run(args,check=True,text=True,capture_output=True).stdout.strip()
def profile(mode):
 p=config_dir()/'profile-before.json'
 if mode=='lightweight':
  if not p.exists():
   old=[run(['kreadconfig6','--file',f,'--group',g,'--key',k,'--default','__AETHER_UNSET__']) for f,g,k,v in SETTINGS]
   atomic_json(p,old)
  values=[v for f,g,k,v in SETTINGS]
 elif mode=='restore':
  if not p.exists():return {'message':'No lightweight profile changes to restore.'}
  values=json.loads(p.read_text())
  if not isinstance(values,list) or len(values)!=len(SETTINGS) or not all(isinstance(v,str) for v in values):raise ValueError('Invalid saved preferences')
 else:raise ValueError('Unknown profile')
 for (f,g,k,_),v in zip(SETTINGS,values):
  run(['kwriteconfig6','--file',f,'--group',g,'--key',k,*(['--delete'] if v=='__AETHER_UNSET__' else [v])])
 # Reload where available; settings also take effect on next login.
 for command in ([shutil.which('qdbus6') or 'qdbus','org.kde.KWin','/KWin','reconfigure'],['balooctl6','disable' if mode=='lightweight' or values[-1]=='false' else 'enable']):
  try:subprocess.run(command,capture_output=True)
  except FileNotFoundError:pass  # Saved settings still apply at the next login.
 if mode=='restore':p.unlink()
 return {'message':'Preferences saved. Log out and in to apply all effects.','profile':mode}
def main():
 p=argparse.ArgumentParser();p.add_argument('action',choices=['lightweight','restore','finish-welcome','status']);a=p.parse_args()
 if a.action=='finish-welcome':atomic_json(config_dir()/'welcome-v1.json',{'completed':True});result={'message':'Setup complete. You can reopen Aether Settings at any time.'}
 elif a.action=='status':result={'lightweight':(config_dir()/'profile-before.json').exists(),'welcome_completed':(config_dir()/'welcome-v1.json').exists()}
 else:result=profile(a.action)
 print(json.dumps(result))
if __name__=='__main__':main()
