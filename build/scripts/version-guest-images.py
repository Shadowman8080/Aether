from pathlib import Path
import re
r = Path('/opt/aether')
for name in ['overlay', 'overlay-x86', 'overlay-arm64']:
    p = r/name/'etc/os-release'
    p.write_text(re.sub(r'0\.1(?:\.1)?\b', '0.1.1', p.read_text()))
for name in ['scripts/make-arm64-iso.sh', 'scripts/test-boot-arm64.py', 'scripts/prepare-arm64-test.py']:
    p = r/name
    p.write_text(p.read_text().replace('aether-0.1-arm64-vm.iso', 'aether-0.1.1-arm64-vm.iso'))
