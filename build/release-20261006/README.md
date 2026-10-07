# Unified development snapshot, 20261006.1

This release extends the previously published unified x86_64 image. It does not
rebuild historical x86 or ARM prototypes. The existing upstream sources remain
available in release 0.3.0; this repository contains the changed first-party
source and the image integration scripts.

Build Vector inside the Aether native build root using src/desktop/vector and
CMake, with `cmake --build <build-directory> -j"$(nproc)"`. Enable
`AETHER_TEST_ICON_MOTION=ON` and run its offscreen tests at scale 1 and 2.
Generate the sound theme with src/sounds/generate.py (all CPUs by default).

The staging directory is /opt/aether/build/release-20261006. Mount the original
/opt/aether/images/aether-0.3-x86_64-unified.iso read-only at iso/, its
live/rootfs.squashfs read-only at lower/, and an overlay with upper/ and work/
at root/. Copy ISO contents to stage/ excluding live/rootfs.squashfs.

Place these source-built additions in additions/:

- vector: the compiled Vector binary
- org.aether.powermenu: src/desktop/plasmoids/org.aether.powermenu
- AetherGlass: generated sound theme including source and license
- manage-sounds.py: src/sounds/manage.py
- configure-vmware-desktop.py: build/desktop/scripts/configure-vmware-desktop.py

Run patch-overlay.py, then build-iso.sh and build-disk.sh. These scripts assume
the dedicated paths and an unused /dev/nbd6; inspect before running. Never point
them at a personal VM disk. The clean VMDK is created directly, with GPT, BIOS
GRUB and removable-path UEFI GRUB. Writeback caching is flushed before detach.
The ISO packer deliberately does not use -one-file-system on the overlay mount:
lower files may have different device IDs and would otherwise be excluded.

Run test-boot.py for `iso bios`, `iso uefi`, `disk bios`, and `disk uefi`.
Disk tests use QEMU snapshot writes and do not modify the distributable disk.
The live marker remains 0.3 for initramfs compatibility; /etc/os-release carries
BUILD_ID=20261006.1. Full rebuilds of the base toolchain are outside this delta.
