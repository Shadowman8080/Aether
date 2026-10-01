# Aether 0.2.1 native guest integration

The working persistent 0.2 image is preserved at `build/aether-system.raw`. The separate 0.2.1 image is `build/aether-0.2.1-system.raw`. It includes the same pristine first-login account state; existing user modifications in other downloaded VMs are not migrated.

## Build sequence

Run from the Ubuntu build host as an administrator. The scripts explicitly verify the new image's loop-device backing file before operations. Do not boot or export a mounted disk.

1. `bash next/scripts/prepare-native-guest.sh`
2. `python3 next/scripts/fetch-native-guest-sources.py`
3. `python3 next/scripts/fetch-native-guest-extras.py`
4. `bash next/scripts/build-guest-kernel.sh`
5. `bash next/scripts/run-native-guest.sh`
6. `python3 next/scripts/finalize-native-guest.py`
7. `bash next/scripts/install-guest-boot.sh`
8. `bash next/scripts/unmount-native-guest.sh`
9. Run `python3 next/scripts/test-guest-integration.py uefi` and `bios` with fresh test overlays.

Host prerequisites include the completed LFS native base, QEMU/OVMF, Python with pexpect, kBuild, nasm, yasm, and the pinned upstream sources. Package manifests record URLs and hashes. The build-only kBuild tools are copied into `/build/host-tools`; the shipped guest software is compiled by Aether's native GCC. Build source directories are outside the guest image and exposed through private bind mounts. Host D-Bus sockets are not exposed. Compilation uses all available CPUs.

## Firmware

Linux enables EFI variables, framebuffer console, DRM framebuffer emulation, and virtual display drivers. GRUB includes BIOS, vendor EFI, and removable EFI paths. Its firmware-settings menu appears only when booted under EFI. This avoids trying to enter EFI firmware from a BIOS boot. EFI variables cannot exist in a BIOS boot; the VM template selects EFI. Secure Boot is not signed in this development release.

## Guest runtime

- open-vm-tools 13.1.0: vmtoolsd, GTK 3/gtkmm clipboard plugin, vmware-user-suid-wrapper, vmhgfs-fuse, vmblock-fuse.
- VirtualBox 7.2.20: VBoxService, VBoxControl, VBoxClient, VBoxDRMClient, mount.vboxsf; in-kernel vboxguest/vboxsf/vmwgfx drivers.
- Xorg software modesetting, evdev input, TWM, GTK 3 panel, Xterm, DejaVu fonts.
- Hypervisor-conditioned system services and per-X-session desktop clients.
- `aether-efi-status`, `aether-guest-status`, `aether-mount-share NAME`.

The graphical session deliberately remains a basic integration development environment. The complete macOS-inspired desktop, local AI, installer, updates, and new 32-bit/ARM persistent releases are outside this patch.

## Validation limits

QEMU tests cover firmware, EFI NVRAM persistence, login/password change/sudo, network, guest-library loading, graphical startup, RandR resizing, shutdown/reboot and file persistence. They do not establish native VMware/VirtualBox clipboard or shared-folder behavior. Windows denies this session access to VMware's authorization pipe and VirtualBox is not installed. The release README contains the remaining native-host checks. Do not label those checks passed without evidence.

Both BIOS and EFI test suites passed on 2026-09-26 (America/Denver). The final EFI run verified the rendered panel at 1024x768 and activated End session through emulated keyboard input. The GUI test temporarily masks the spare tty2 getty inside its disposable overlay to avoid competing console ownership; normal users run startx from their existing login terminal. Tests leave the distributable base image untouched.

Use `prepare-guest-release.py` to verify recipe syntax and produce credential-checked public test logs. `export-native-guest.sh` checks test results, exports a monolithic sparse VMDK, verifies image integrity, and compares it against the source disk before promoting the output.
