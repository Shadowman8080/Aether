from pathlib import Path
r = Path('/opt/aether')
for name in ['overlay', 'overlay-x86', 'overlay-arm64']:
    p = r/name/'etc/network/interfaces'
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('auto lo\niface lo inet loopback\n\nauto eth0\niface eth0 inet dhcp\n')
p = r/'configs/linux-arm64.config'
if 'CONFIG_SYSFB_SIMPLEFB=y' not in p.read_text():
    with p.open('a') as f:
        f.write('\nCONFIG_SYSFB_SIMPLEFB=y\nCONFIG_ACPI_SPCR_TABLE=y\n')
