#!/usr/bin/env python3
"""Configure the mounted development disk; installer writes its own /boot layout."""
from pathlib import Path
import re, subprocess, sys
assert 'ID=aether' in Path('/etc/os-release').read_text().splitlines()
uuid=sys.argv[1]
assert re.fullmatch('[a-fA-F0-9-]{36}',uuid)
release='6.18.54-aether4'
service=Path('/usr/lib/systemd/system/lightdm.service')
text=service.read_text().replace(' plymouth-quit.service','')
if 'ExecStartPre=' not in text:
    text=text.replace('ExecStart=/usr/sbin/lightdm','ExecStartPre=-/usr/bin/plymouth quit --retain-splash\nExecStart=/usr/sbin/lightdm')
service.write_text(text)
subprocess.run(['/usr/bin/aether-mkinitramfs','/boot/initramfs-'+release+'.img'],check=True)
Path('/boot/grub/grub.cfg').write_text(f'''set default=0
set timeout_style=hidden
set timeout=3
serial --unit=0 --speed=115200
terminal_input console serial
terminal_output console serial
clear
insmod part_gpt
insmod ext2
search --no-floppy --fs-uuid --set=root {uuid}
menuentry 'Aether Linux' --hotkey=a {{
 linux /boot/vmlinuz-{release} root=UUID={uuid} rootwait rw console=ttyS0,115200n8 console=tty0 quiet splash loglevel=3 systemd.show_status=false vt.global_cursor_default=0
 initrd /boot/initramfs-{release}.img
}}
menuentry 'Aether diagnostics and console login' --hotkey=d {{
 linux /boot/vmlinuz-{release} root=UUID={uuid} rootwait rw console=ttyS0,115200n8 console=tty0 plymouth.enable=0 systemd.show_status=yes systemd.unit=multi-user.target
 initrd /boot/initramfs-{release}.img
}}
if [ "$grub_platform" = efi ]; then
 menuentry 'UEFI firmware settings' --hotkey=f {{ fwsetup }}
fi
''')
subprocess.run(['/usr/bin/grub-script-check','/boot/grub/grub.cfg'],check=True)
print('AETHER_BOOT_CONFIGURATION_PASS')
