# Aether 0.2 persistent console base

The x86-64 source-built native base is now bootable and persistent. It is not yet a graphical desktop or installer release.

## Delivered behavior

- Linux 6.18.54-aether and source-built GRUB 2.14, BIOS and x86-64 UEFI.
- 64 GiB GPT disk, ext4 root, FAT32 EFI partition, and 2 GiB swap file.
- Normal UID 1000 account `aether`, unique temporary password forced to change at first login, locked root login, password-authenticated sudo.
- DHCP on wired Ethernet, systemd-resolved DNS, time synchronization, persistent journals limited to 128 MiB, multi-user console, US keyboard and America/Denver timezone.
- Fresh machine identity on first boot. No SSH server, desktop, AI integration, installer or update service yet.

## Validation

`test-persistent.py bios` passed with QEMU q35, qemu64, 4 CPUs, 2 GiB RAM, VMware PVSCSI storage and virtio networking.
`test-persistent.py uefi` passed with OVMF, virtio storage and VMware VMXNET3 networking.
`test-persistent.py sata` passed with SATA/AHCI storage and Intel E1000 networking, including a third boot with no NIC.

Each mode tested real login, required password change, sudo, locked root, filesystem permissions, DHCP/DNS, swap, no failed systemd units, native C compilation, reboot/poweroff, and persistent home/settings/machine identity/journals. The SATA test additionally exercised `aether-system-status` offline and asserted two or more journal boots without counting the header.

Native VMware and VirtualBox host integration has not been verified. Windows sandbox permissions block VMware's authorization pipe; VirtualBox is unavailable on the host. QEMU device emulation is the automated evidence, not a claim of complete native hypervisor validation.

## Build state and recovery

`/opt/aether/build/aether-system.raw` is the pristine deliverable source and is detached, not mounted. Never mount or modify it while a test/guest uses it or a qcow2 backing chain that references it.

The completed native build metadata was preserved outside the image in `/opt/aether/build/native-build-metadata/{sources,jhalfs,blfs_root}`. The former `/opt/aether/system/jhalfs` path no longer exists in the shipping filesystem. Base/kernel build logs remain in `/opt/aether/logs/next`.

`configure-persistent.py` operates only on a verified mounted loop partition backed by the known Aether image. `finish-persistent-kernel.sh` adds VM storage/console drivers and builds with all `nproc` jobs. `install-persistent-boot.sh` uses a private mount namespace and installs only onto the verified image loop device. `finish-persistent.sh` is the initial mounted-image pipeline. It requires fresh test directories. `test-persistent.py` refuses an attached source disk and creates isolated qcow2 test overlays. `finalize-persistent-image.py` only performs final offline cleanup and preserves first-login state. `export-persistent.sh` checks successful logs and detached state, exports monolithicSparse VMDK, then checks and compares its contents against the source image.

The early pipeline log includes test-harness failures fixed during development. The final per-firmware logs and export status are authoritative. The temporary host sudo rule remains removed. Credentials are private ignored build artifacts and are not included in Git archives.

Next milestones: source-native desktop/guest userspace tools, package/update integration, AI integration, installer/recovery, then persistent builds for other architectures.
