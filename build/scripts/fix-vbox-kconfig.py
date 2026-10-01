from pathlib import Path
r = Path('/opt/aether')
for name in ['configs/linux-vm.config', 'configs/linux-arm64.config', 'scripts/prepare-vm-profile.py', 'scripts/prepare-arm64.py']:
    p = r/name
    text = p.read_text()
    if 'CONFIG_VIRT_DRIVERS=y' not in text:
        text = text.replace('CONFIG_VBOXGUEST=y', 'CONFIG_VIRT_DRIVERS=y\nCONFIG_VBOXGUEST=y')
        p.write_text(text)
