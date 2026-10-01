from pathlib import Path
import shutil
root=Path('/opt/aether')
overlay=root/'overlay-x86'
shutil.copytree(root/'overlay', overlay, dirs_exist_ok=True)
check=overlay/'etc/init.d/S99aether'
check.write_text(check.read_text().replace('= x86_64', '= i686'))
motd=overlay/'etc/motd'
motd.write_text(motd.read_text().replace('x86-64', '32-bit x86'))
config=(root/'configs/aether_defconfig').read_text()
config=config.replace('BR2_x86_64=y\nBR2_x86_x86_64=y','BR2_i386=y\nBR2_x86_i686=y')
config=config.replace('source-built x86-64 prototype','source-built 32-bit x86 prototype')
config=config.replace('/opt/aether/overlay"','/opt/aether/overlay-x86"')
config=config.replace('/opt/aether/scripts/post-build.sh','/opt/aether/scripts/post-build-x86.sh')
config=config.replace('BR2_TARGET_GRUB2_X86_64_EFI=y\n','')
config='\n'.join(line for line in config.splitlines() if not line.startswith(('BR2_TARGET_GRUB2_BUILTIN_MODULES_EFI=', 'BR2_TARGET_GRUB2_BUILTIN_CONFIG_EFI=')))+'\n'
(root/'configs/aether_x86_defconfig').write_text(config)
post=(root/'scripts/post-build.sh').read_text().replace('sizeof(void*) == 8', 'sizeof(void*) == 4')
post=post.replace('x86_64-aether-linux-gnu-gcc','i686-aether-linux-gnu-gcc').replace('-march=x86-64','-march=i686')
(root/'scripts/post-build-x86.sh').write_text(post)
(root/'scripts/post-build-x86.sh').chmod(0o755)
test=(root/'scripts/test-boot.py').read_text()
test=test.replace('boot-{firmware}.log','boot-x86-{firmware}.log')
test=test.replace('qemu-system-x86_64','qemu-system-i386').replace("'q35'","'pc'").replace("'qemu64'","'pentium3'")
test=test.replace('aether-0.1-x86_64.iso','aether-0.1-x86.iso')
test=test.replace("assert firmware in ('bios', 'uefi')", "assert firmware == 'bios', 'This 32-bit prototype supports BIOS boot only'")
(root/'scripts/test-boot-x86.py').write_text(test)
