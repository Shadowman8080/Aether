from pathlib import Path
import re,subprocess
base=Path('/opt/aether')
secret=re.search(r'^Temporary password: (.+)$',(base/'build/persistent-credentials.txt').read_text(),re.M)[1]
for mode in ('uefi','bios'):
 data=(base/f'logs/next/guest-integration-{mode}.log').read_text()
 assert f'PASS: {mode}' in data
 assert secret not in data and not re.search(r'Test7![0-9a-f]{24}',data), 'Credential leaked into test log'
 data=re.sub(r'\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)','',data)
 data=re.sub(r'\x1bP.*?\x1b\\','',data,flags=re.S)
 data=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',data)
 data=re.sub(r'\x1b[78]','',data)
 data=data.replace('\r','')
 (base/f'images/aether-0.2.1-{mode}-test.log').write_text(data)
for p in (base/'next/scripts').glob('*.sh'):
 subprocess.run(['bash','-n',str(p)],check=True)
subprocess.run(['python3','-m','compileall','-q',str(base/'next/scripts')],check=True)
print('Public logs contain no test credentials; recipe syntax checks passed.')
