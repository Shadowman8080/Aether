from pathlib import Path
r = Path('/opt/aether')
for name in ['configs/linux-arm64.config', 'scripts/prepare-arm64.py']:
    p = r/name
    p.write_text(p.read_text().replace('CONFIG_VMWARE_PVSCSI=y\n', ''))
