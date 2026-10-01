#!/usr/bin/env python3
"""Copy native Plymouth and its runtime dependencies into an Aether initramfs."""
from pathlib import Path
import re, shutil, subprocess, sys
root = Path(sys.argv[1]).resolve()
release = sys.argv[2]
assert root != Path('/') and re.fullmatch('[A-Za-z0-9._+-]+', release)
copied = set()
def binary(path):
    path=Path(path)
    if str(path) in copied: return
    copied.add(str(path))
    target=root/str(path).lstrip('/'); target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(path,target,follow_symlinks=True)
    result=subprocess.run(['ldd',str(path)],capture_output=True,text=True)
    if 'not found' in result.stdout: raise RuntimeError(result.stdout)
    for library in re.findall(r'(/[^\s()]+)',result.stdout):
        dest=root/library.lstrip('/');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(library,dest,follow_symlinks=True)
for path in ('/usr/bin/plymouth','/usr/sbin/plymouthd','/usr/sbin/modprobe','/usr/lib/systemd/systemd-udevd','/usr/bin/udevadm','/usr/bin/loadkeys'):
    binary(path)
for path in Path('/usr/lib/plymouth').rglob('*.so'): binary(path)
for directory in ('usr/share/plymouth','etc/plymouth','etc/fonts','usr/share/fonts/dejavu','usr/share/X11/xkb','usr/share/keymaps'):
    source=Path('/')/directory
    if source.exists(): shutil.copytree(source,root/directory,dirs_exist_ok=True)
for name in ('50-udev-default.rules','60-input-id.rules','71-seat.rules'):
    target=root/'usr/lib/udev/rules.d'/name;target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(Path('/usr/lib/udev/rules.d')/name,target)
config=Path('/etc/vconsole.conf').read_text()
if 'XKBLAYOUT=' not in config: config+='\nXKBLAYOUT=us\n'
(root/'etc/vconsole.conf').write_text(config)
for name in ('start-splash', 'unlock-root'):
    target=root/'usr/lib/aether-initramfs'/name
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(Path('/usr/lib/aether-initramfs')/name,target)
    target.chmod(0o755)
for directory in ('run/plymouth','var/lib/plymouth','var/log','dev','proc','sys','newroot'):
    (root/directory).mkdir(parents=True,exist_ok=True)
(root/'etc').mkdir(exist_ok=True)
(root/'etc/initrd-release').write_text('NAME="Aether initramfs"\nID=aether\n')
modules=Path('/lib/modules')/release
for name in ('vmwgfx','virtio_gpu'):
    result=subprocess.run(['modprobe','--set-version',release,'--show-depends',name],capture_output=True,text=True,check=True)
    for line in result.stdout.splitlines():
        if line.startswith('insmod '):
            module=Path(line.split()[1]); relative=module.relative_to(modules)
            target=root/'lib/modules'/release/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(module,target)
destination=root/'lib/modules'/release;destination.mkdir(parents=True,exist_ok=True)
for path in modules.glob('modules.*'):
    if path.is_file(): shutil.copy2(path,destination/path.name)
print('Native Plymouth initramfs assets installed')
