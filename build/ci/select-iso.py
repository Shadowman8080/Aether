import json,os,re,sys
from pathlib import Path
release=json.loads(Path(sys.argv[1]).read_text())
assets=[a for a in release['assets'] if re.fullmatch(r'aether-[A-Za-z0-9._-]+-x86_64\.iso',a['name'])]
if len(assets)!=1:raise SystemExit('Expected exactly one unified x86_64 ISO')
asset=assets[0]
if asset.get('state')!='uploaded' or asset.get('digest')!='sha256:'+os.environ['EXPECTED_SHA256']:
 raise SystemExit('GitHub candidate digest does not match reviewed SHA-256')
print(asset['name'])
