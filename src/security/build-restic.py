from pathlib import Path
import hashlib,json,os,subprocess,tarfile
base=Path('/opt/aether')
cache=base/'sources/security-cache'
url='https://go.dev/dl/go1.27.1.linux-amd64.tar.gz'
p=cache/'go1.27.1.linux-amd64.tar.gz'
if not p.exists():subprocess.run(['curl','-fsSL','--proto','=https','--retry','3','-o',str(p),url],check=True)
assert hashlib.sha256(p.read_bytes()).hexdigest()=='63d339f0da5ab53635a56f2490a7984dfe12dfcff22ad749f63edaf590168445'
tool=base/'host-tools/go'
if not (tool/'bin/go').exists():
 with tarfile.open(p) as t:t.extractall(base/'host-tools',filter='data')
u='https://github.com/restic/restic/archive/refs/tags/v0.19.1.tar.gz'
r=cache/'restic-v0.19.1.tar.gz'
if not r.exists():subprocess.run(['curl','-fsSL','--proto','=https','--retry','3','-o',str(r),u],check=True)
source=base/'build/security/restic-0.19.1'
if not source.exists():
 with tarfile.open(r) as t:t.extractall(base/'build/security',filter='data')
e=os.environ.copy();e.update(PATH=str(tool/'bin')+':'+e['PATH'],GOMAXPROCS=str(os.cpu_count()),CGO_ENABLED='0',GOAMD64='v1',GOFLAGS='-buildvcs=false',GOCACHE=str(base/'build/security/go-cache'),GOPATH=str(base/'build/security/go-path'))
subprocess.run([str(tool/'bin/go'),'run','build.go'],cwd=source,env=e,check=True)
subprocess.run(['install','-m755',str(source/'restic'),str(base/'security-system/usr/bin/restic')],check=True)
subprocess.run([str(source/'restic'),'version'],check=True)
with (base/'security/restic-build-provenance.txt').open('w') as f:
 f.write('Source URL: '+u+'\nSource SHA256: '+hashlib.sha256(r.read_bytes()).hexdigest()+'\nCompiler: '+url+'\nSource archive retrieved from upstream HTTPS; tag signing verification pending. Go modules checked using go.sum.\n')
 subprocess.run([str(tool/'bin/go'),'version','-m',str(source/'restic')],stdout=f,env=e,check=True)
print('RESTIC_BUILD_PASS',flush=True)
