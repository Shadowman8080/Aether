#!/bin/bash
# Build into staging only. This never changes the Ubuntu host bootloader.
set -euo pipefail
cd /opt/aether
version=6.18.54
source_dir=/opt/aether/sources/linux-$version
build_dir=/opt/aether/build/kernel-$version
stage=/opt/aether/build/kernel-stage
date -u '+STARTED %FT%TZ' > logs/next/kernel.status
trap 'result=$?; echo "EXIT $result" >> /opt/aether/logs/next/kernel.status' EXIT
python3 next/scripts/prepare-next-kernel.py
if [ ! -d "$source_dir" ]; then tar -xf "sources/linux-$version.tar.xz" -C sources; fi
mkdir -p "$build_dir" "$stage/boot"
make -C "$source_dir" O="$build_dir" x86_64_defconfig
cfg=("$source_dir/scripts/config" --file "$build_dir/.config")
"${cfg[@]}" --set-str LOCALVERSION -aether --disable LOCALVERSION_AUTO
"${cfg[@]}" --disable X86_NATIVE_CPU
"${cfg[@]}" --disable DEBUG_INFO --disable DEBUG_INFO_DWARF_TOOLCHAIN_DEFAULT --enable DEBUG_INFO_NONE
"${cfg[@]}" --set-str SYSTEM_TRUSTED_KEYS '' --set-str SYSTEM_REVOCATION_KEYS ''
for option in BLK_DEV_INITRD DEVTMPFS DEVTMPFS_MOUNT \
  EFI EFI_STUB EFI_PARTITION EFIVAR_FS DMIID FHANDLE \
  CGROUPS CGROUP_SCHED CGROUP_PIDS MEMCG CPUSETS CGROUP_BPF \
  NAMESPACES USER_NS PID_NS NET_NS SECCOMP SECCOMP_FILTER \
  BPF BPF_SYSCALL INOTIFY_USER FANOTIFY AUTOFS_FS \
  TMPFS TMPFS_POSIX_ACL TMPFS_XATTR EXT4_FS EXT4_FS_POSIX_ACL \
  UNIX INET IPV6 NETFILTER PACKET \
  SCSI BLK_DEV_SD ATA SATA_AHCI ATA_PIIX \
  VIRTIO VIRTIO_PCI VIRTIO_BLK VIRTIO_NET \
  SERIAL_8250 SERIAL_8250_CONSOLE BLK_DEV_NVME \
  INPUT_EVDEV INPUT_MOUSEDEV USB_XHCI_HCD USB_EHCI_HCD USB_OHCI_HCD \
  USB_HID HID_GENERIC HID_MULTITOUCH DRM DRM_KMS_HELPER \
  SOUND SND CFG80211 MAC80211 RFKILL; do
  "${cfg[@]}" --enable "$option"
done
for option in BLK_DEV_LOOP BLK_DEV_DM DM_CRYPT BTRFS_FS VFAT_FS \
  DRM_I915 DRM_AMDGPU DRM_NOUVEAU DRM_VMWGFX DRM_VIRTIO_GPU \
  SND_HDA_INTEL SND_HDA_CODEC_REALTEK SND_HDA_CODEC_HDMI SND_USB_AUDIO \
  E1000 E1000E IGB IGC R8169 VMXNET3 FUSE_FS \
  IWLWIFI IWLDVM IWLMVM ATH9K ATH10K ATH10K_PCI ATH11K ATH11K_PCI \
  BT BT_HCIBTUSB USB_STORAGE UAS; do
  "${cfg[@]}" --module "$option"
done
make -C "$source_dir" O="$build_dir" olddefconfig
grep -qx '# CONFIG_X86_NATIVE_CPU is not set' "$build_dir/.config"
for option in X86_64 DEVTMPFS CGROUPS USER_NS SECCOMP_FILTER \
  EXT4_FS SATA_AHCI VIRTIO_BLK EFI_STUB; do
  grep -qx "CONFIG_$option=y" "$build_dir/.config" || { echo "Missing required option: $option"; exit 1; }
done
cp "$build_dir/.config" next/configs/kernel.config
make -C "$source_dir" O="$build_dir" -j"$(nproc)" bzImage modules
make -C "$source_dir" O="$build_dir" -j"$(nproc)" INSTALL_MOD_PATH="$stage" modules_install
release=$(make -s -C "$source_dir" O="$build_dir" kernelrelease)
install -m644 "$build_dir/arch/x86/boot/bzImage" "$stage/boot/vmlinuz-$release"
install -m644 "$build_dir/System.map" "$stage/boot/System.map-$release"
install -m644 "$build_dir/.config" "$stage/boot/config-$release"
printf '%s\n' "$release" > logs/next/kernel.release
