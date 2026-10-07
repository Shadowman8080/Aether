#!/usr/bin/env python3
"""Replay native installs into individual dpkg payloads; preserve file ownership."""
import ast,hashlib,json,os,subprocess
from pathlib import Path
b=Path('/modern');source=b/'project/build/modern-20261006/build-packages.py'
tree=ast.parse(source.read_text());recipes=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='recipes' for t in n.targets))
items={d['key']:d for d in json.loads((b/'sources.json').read_text())}
names={'discover':'plasma-discover','qtconnectivity':'qt6-connectivity'}
def run(args,**kw):subprocess.run(args,check=True,**kw)
payloads={}
for key,kind,_ in recipes:
 p=b/'packages'/key;p.mkdir(parents=True,exist_ok=True);out=b/'obj'/key
 if kind=='meson':run(['meson','install','-C',str(out),'--no-rebuild','--destdir',str(p)])
 elif kind=='cmake':run(['cmake','--install',str(out)],env={**os.environ,'DESTDIR':str(p)})
 else:run(['make','DESTDIR='+str(p),'install'],cwd=out)
 version=items[key].get('version') or items[key]['filename'].removeprefix(key+'-').split('.tar.')[0]
 payloads[names.get(key,key)]=(p,version.lstrip('v')+'-1aether1')
owners={}
for path in Path('/var/lib/dpkg/info').glob('*.list'):
 for f in path.read_text().splitlines():owners[f]=path.name.removesuffix('.list').split(':')[0]
conflicts=[]
for name,(p,_) in payloads.items():
 for f in p.rglob('*'):
  if f.relative_to(p).parts[0]=='DEBIAN':continue
  if not (f.is_file() or f.is_symlink()):continue
  path='/'+f.relative_to(p).as_posix();old=owners.get(path)
  if old and old!=name:conflicts.append({'path':path,'owner':old,'new':name})
  owners[path]=name
if conflicts:
 (b/'package-conflicts.json').write_text(json.dumps(conflicts,indent=2));raise SystemExit('Package ownership conflicts require review')
records=[]
for name,(p,version) in payloads.items():
 depends=set();unowned=set()
 for f in p.rglob('*'):
  if f.is_symlink() or not f.is_file():continue
  with f.open('rb') as stream:magic=stream.read(4)
  if magic!=b'\x7fELF':continue
  r=subprocess.run(['ldd',str(f)],capture_output=True,text=True,env={**os.environ,'LD_LIBRARY_PATH':'/usr/lib/plasma-discover'})
  if 'not found' in r.stdout:raise RuntimeError(r.stdout)
  for line in r.stdout.splitlines():
   parts=line.strip().split();lib=parts[2] if len(parts)>2 and parts[1]=='=>' else (parts[0] if parts else '')
   if not lib.startswith('/'):continue
   owner=owners.get(lib) or owners.get(str(Path(lib).resolve()))
   if owner and owner!=name:depends.add(owner)
   elif not owner:unowned.add(lib)
 for dependency in {'flatpak':['bubblewrap','xdg-dbus-proxy'],'plasma-discover':['flatpak','fwupd'],'kdeconnect':['qt6-connectivity']}.get(name,[]):depends.add(dependency)
 control=p/'DEBIAN';control.mkdir(exist_ok=True)
 text=f'Package: {name}\nVersion: {version}\nArchitecture: amd64\nMaintainer: Aether Linux developers\nDescription: Native source-built {name} for Aether\n'
 if depends:text+='Depends: '+', '.join(sorted(depends))+'\n'
 (control/'control').write_text(text)
 configs=sorted('/'+f.relative_to(p).as_posix() for f in (p/'etc').rglob('*') if f.is_file() and not f.is_symlink()) if (p/'etc').exists() else []
 if configs:(control/'conffiles').write_text('\n'.join(configs)+'\n')
 output=b/'packages'/(name+'_'+version+'_amd64.deb');run(['dpkg-deb','--build','--root-owner-group',str(p),str(output)])
 records.append({'name':name,'version':version,'archive':output.name,'sha256':hashlib.file_digest(output.open('rb'),'sha256').hexdigest(),'depends':sorted(depends),'unowned_shared_libraries':sorted(unowned)})
(b/'native-packages.json').write_text(json.dumps(records,indent=2)+'\n')
print('NATIVE_PACKAGES_BUILT',len(records))
