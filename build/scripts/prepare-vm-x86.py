from pathlib import Path
r = Path('/opt/aether')
c = (r/'configs/aether_x86_defconfig').read_text()
c = c.replace('/opt/aether/configs/linux.config', '/opt/aether/configs/linux-vm.config')
c += 'BR2_PACKAGE_AETHER_VMTOOLS=y\n'
(r/'configs/aether_vm_x86_defconfig').write_text(c)
s = (r/'scripts/build-vmtools-x64.sh').read_text()
s = s.replace('vmtools-x64', 'vmtools-x86').replace('aether_vm_x86_64_defconfig', 'aether_vm_x86_defconfig')
s = s.replace('build/prototype', 'build/prototype-x86')
(r/'scripts/build-vmtools-x86.sh').write_text(s)
