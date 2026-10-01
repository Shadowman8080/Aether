#!/usr/bin/env python3
from pathlib import Path
import subprocess
image = '/opt/aether/build/aether-system.raw'
root = Path('/opt/aether/system')
for proc in Path('/proc').glob('[0-9]*/cmdline'):
    try:
        args = proc.read_bytes().split(b'\0')
    except (FileNotFoundError, PermissionError):
        continue
    if args and b'qemu-system-' in args[0]:
        assert not any(b'/opt/aether/build/persistent-' in a for a in args), 'Aether test is running'
assert not subprocess.check_output(['losetup', '-j', image], text=True).strip()
loop = subprocess.check_output(['losetup', '--find', '--show', '--partscan', image], text=True).strip()
try:
    subprocess.run(['udevadm', 'settle'], check=True)
    subprocess.run(['mount', loop + 'p3', str(root)], check=True)
    status = root / 'usr/bin/aether-system-status'
    status.write_text(status.read_text().replace('findmnt / /boot/efi', 'findmnt --mountpoint /\nfindmnt --mountpoint /boot/efi'))
    assert (root / 'etc/machine-id').read_text() == ''
    shadow = (root / 'etc/shadow').read_text().splitlines()
    assert next(x for x in shadow if x.startswith('root:')).split(':')[1].startswith('!')
    assert next(x for x in shadow if x.startswith('aether:')).split(':')[2] == '0'
    assert not (root / 'sources').exists()
    subprocess.run(['sync'], check=True)
    subprocess.run(['fstrim', '-v', str(root)], check=True)
finally:
    if subprocess.run(['mountpoint', '-q', str(root)]).returncode == 0:
        subprocess.run(['umount', str(root)], check=True)
    subprocess.run(['losetup', '-d', loop], check=True)
print('Final image has fresh first-boot credentials and identity; source image detached.')
