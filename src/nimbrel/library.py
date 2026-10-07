#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Opt-in local text search. No background crawl, network or command execution."""
import argparse,json,os,re,sqlite3,stat,tempfile
from pathlib import Path
EXTENSIONS={'.txt','.md','.rst','.csv'}
MAX_FILE=1024*1024
MAX_FILES=5000
MAX_TOTAL=64*1024*1024
def state_dir():
 p=Path(os.environ.get('XDG_DATA_HOME',str(Path.home()/'.local/share')))/'nimbrel-library'
 if p.is_symlink():raise ValueError('Library directory must not be a symlink')
 p.mkdir(parents=True,exist_ok=True,mode=0o700);p.chmod(0o700)
 return p
def folders():
 p=state_dir()/'folders.json'
 return json.loads(p.read_text()) if p.exists() else []
def set_folders(values):
 home=Path.home().resolve();clean=[]
 for value in values:
  p=Path(value).expanduser()
  if p.is_symlink():raise ValueError('Choose a real folder, not a symbolic link')
  p=p.resolve(strict=True)
  if not p.is_dir() or not p.is_relative_to(home) or p==home:raise ValueError('Choose specific folders inside your home directory')
  if any(v.startswith('.') for v in p.relative_to(home).parts):raise ValueError('Hidden configuration folders cannot be indexed')
  if str(p) not in clean:clean.append(str(p))
 d=state_dir();fd,name=tempfile.mkstemp(dir=d)
 with os.fdopen(fd,'w') as f:json.dump(clean,f);f.flush();os.fsync(f.fileno())
 os.replace(name,d/'folders.json')
 clear_index() # Revoked folders must stop appearing immediately.
 return {'folders':clean,'message':'Folder access saved. Rebuild the index when ready.'}
def clear_index():
 for suffix in ('','-wal','-shm'):(state_dir()/('library.sqlite'+suffix)).unlink(missing_ok=True)
def rebuild():
 d=state_dir();fd,name=tempfile.mkstemp(dir=d);os.close(fd);count=total=0
 try:
  with sqlite3.connect(name) as db:
   db.execute('CREATE VIRTUAL TABLE docs USING fts5(path UNINDEXED, content)')
   for folder in folders():
    root=Path(folder)
    if not root.is_dir() or root.is_symlink() or root.resolve()!=root or not root.is_relative_to(Path.home().resolve()):continue
    for directory,dirs,files in os.walk(root,followlinks=False):
     dirs[:]=sorted(x for x in dirs if not x.startswith('.') and not (Path(directory)/x).is_symlink())
     for filename in sorted(files):
      p=Path(directory)/filename
      if filename.startswith('.') or p.suffix.lower() not in EXTENSIONS:continue
      if count>=MAX_FILES or total>=MAX_TOTAL:break
      try:
       fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
       with os.fdopen(fd,'rb') as f:
        st=os.fstat(f.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_size>MAX_FILE:continue
        # Recheck containment through resolved parents before consuming content.
        if not p.resolve().is_relative_to(root.resolve()):continue
        raw=f.read(min(MAX_FILE+1,MAX_TOTAL-total+1))
       if len(raw)>MAX_FILE or total+len(raw)>MAX_TOTAL or b'\0' in raw:continue
       text=raw.decode('utf-8')
      except (OSError,UnicodeError):continue
      db.execute('INSERT INTO docs VALUES (?,?)',(str(p),text));count+=1;total+=len(raw)
     if count>=MAX_FILES or total>=MAX_TOTAL:break
    if count>=MAX_FILES or total>=MAX_TOTAL:break
  os.replace(name,d/'library.sqlite')
 finally:
  if os.path.exists(name):os.unlink(name)
 return {'indexed_files':count,'bytes':total,'limit_reached':count>=MAX_FILES or total>=MAX_TOTAL}
def search(query):
 words=re.findall(r'\w+',query,flags=re.UNICODE)[:12]
 p=state_dir()/'library.sqlite'
 if not words or not p.exists():return []
 approved=[Path(v).resolve() for v in folders()]
 with sqlite3.connect('file:'+str(p)+'?mode=ro',uri=True) as db:
  rows=db.execute('SELECT path,snippet(docs,1,\'\',\'\',\' … \',48) FROM docs WHERE docs MATCH ? ORDER BY rank LIMIT 20',(' OR '.join('"'+w+'"' for w in words),)).fetchall()
 return [{'path':p,'excerpt':t} for p,t in rows if Path(p).is_file() and not Path(p).is_symlink() and any(Path(p).resolve().is_relative_to(r) for r in approved)]
def main():
 os.umask(0o077);p=argparse.ArgumentParser();p.add_argument('action',choices=['folders','add','clear','rebuild','search']);p.add_argument('value',nargs='?');a=p.parse_args()
 if a.action=='folders':result={'folders':folders()}
 elif a.action=='add':result=set_folders(folders()+[a.value])
 elif a.action=='clear':result=set_folders([])
 elif a.action=='rebuild':result=rebuild()
 else:result=search(a.value or '')
 print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
