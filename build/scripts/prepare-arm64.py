from pathlib import Path
import shutil
r=Path('/opt/aether')
overlay=r/'overlay-arm64'
shutil.copytree(r/'overlay',overlay,dirs_exist_ok=True)
f=overlay/'etc/init.d/S99aether'; f.write_text(f.read_text().replace('= x86_64','= aarch64'))
f=overlay/'etc/motd'; f.write_text(f.read_text().replace('x86-64','ARM64'))
post=(r/'scripts/post-build.sh').read_text().replace('x86_64-aether-linux-gnu-gcc','aarch64-aether-linux-gnu-gcc').replace('-march=x86-64 -mtune=generic','-march=armv8-a')
post=post.replace("grep -q '^ttyS0::'", "grep -q '^ttyAMA0::'").replace('ttyS0::respawn:/sbin/getty -L ttyS0','ttyAMA0::respawn:/sbin/getty -L ttyAMA0')
(r/'scripts/post-build-arm64.sh').write_text(post)
(r/'scripts/post-build-arm64.sh').chmod(0o755)
cfg=(r/'configs/aether_defconfig').read_text()
cfg=cfg.replace('BR2_x86_64=y\nBR2_x86_x86_64=y','BR2_aarch64=y\nBR2_cortex_a53=y')
cfg=cfg.replace('source-built x86-64 prototype','source-built ARM64 prototype')
cfg=cfg.replace('/opt/aether/overlay"','/opt/aether/overlay-arm64"')
cfg=cfg.replace('/opt/aether/scripts/post-build.sh','/opt/aether/scripts/post-build-arm64.sh')
cfg=cfg.replace('/opt/aether/configs/linux.config','/opt/aether/configs/linux-arm64.config')
cfg=cfg.replace('BR2_TARGET_GRUB2_I386_PC=y\n','').replace('BR2_TARGET_GRUB2_X86_64_EFI=y','BR2_TARGET_GRUB2_ARM64_EFI=y')
cfg='\n'.join(s for s in cfg.splitlines() if not s.startswith(('BR2_TARGET_GRUB2_BUILTIN_MODULES_PC=', 'BR2_TARGET_GRUB2_BUILTIN_CONFIG_PC=')))+'\n'
cfg+='BR2_LINUX_KERNEL_NEEDS_HOST_OPENSSL=y\n'
(r/'configs/aether_arm64_defconfig').write_text(cfg)
kernel=(r/'sources/buildroot-2026.08/board/qemu/aarch64-virt/linux.config').read_text()
kernel+='''
CONFIG_BLK_DEV_INITRD=y
CONFIG_RD_GZIP=y
CONFIG_BINFMT_ELF=y
CONFIG_BINFMT_SCRIPT=y
CONFIG_EFI=y
CONFIG_EFI_STUB=y
CONFIG_EFI_PARTITION=y
CONFIG_VT=y
CONFIG_VT_CONSOLE=y
CONFIG_FRAMEBUFFER_CONSOLE=y
CONFIG_DRM_SIMPLEDRM=y
CONFIG_DRM_VMWGFX=y
CONFIG_FB_EFI=y
CONFIG_USB=y
CONFIG_USB_XHCI_HCD=y
CONFIG_USB_XHCI_PCI=y
CONFIG_USB_HID=y
CONFIG_USB_STORAGE=y
CONFIG_HID=y
CONFIG_HID_GENERIC=y
CONFIG_SATA_AHCI=y
CONFIG_BLK_DEV_NVME=y
CONFIG_E1000=y
CONFIG_E1000E=y
CONFIG_VMXNET3=y
CONFIG_VMWARE_VMCI=y
CONFIG_VMWARE_BALLOON=y
CONFIG_VMWARE_VMCI_VSOCKETS=y
CONFIG_VIRTIO_VSOCKETS=y
CONFIG_VIRT_DRIVERS=y
CONFIG_VBOXGUEST=y
CONFIG_VBOXSF_FS=y
CONFIG_ISO9660_FS=y
CONFIG_FAT_FS=y
CONFIG_VFAT_FS=y
CONFIG_NLS_CODEPAGE_437=y
CONFIG_NLS_ISO8859_1=y
CONFIG_LOCALVERSION="-aether"
# CONFIG_LOCALVERSION_AUTO is not set
'''
(r/'configs/linux-arm64.config').write_text(kernel)
