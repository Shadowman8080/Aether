from pathlib import Path
r=Path('/opt/aether')
config=(r/'configs/aether_defconfig').read_text()
config=config.replace('/opt/aether/configs/linux.config','/opt/aether/configs/linux-vm.config')
config+='BR2_PACKAGE_AETHER_VMTOOLS=y\n'
(r/'configs/aether_vm_x86_64_defconfig').write_text(config)
kernel=(r/'configs/linux.config').read_text()+'''
CONFIG_VSOCKETS=y
CONFIG_VMWARE_VMCI_VSOCKETS=y
CONFIG_VIRTIO_VSOCKETS=y
CONFIG_FUSE_FS=y
CONFIG_VIRT_DRIVERS=y
CONFIG_VBOXGUEST=y
CONFIG_VBOXSF_FS=y
CONFIG_DRM_VBOXVIDEO=y
CONFIG_PCNET32=y
'''
(r/'configs/linux-vm.config').write_text(kernel)
