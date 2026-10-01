# Aether Linux 0.2.1 — EFI and virtual-machine integration

This source-built x86-64 development disk adds EFI console support, firmware utilities, VMware open-vm-tools, VirtualBox Guest Additions, and a basic X11 graphical session for testing guest integration. x64 and x86-64 are the same architecture. The earlier 32-bit x86 and ARM images remain separate prototypes; this release does not update them.

## VMware

1. Keep `aether-0.2.1-x86_64.vmx` and `aether-0.2.1-x86_64.vmdk` together in a writable folder.
2. Open the new VMX in VMware Workstation. Select **I copied it** if asked. It defaults to **UEFI**, with Secure Boot disabled, 3 GiB RAM, four virtual CPUs, PVSCSI storage, VMXNET3 networking, and software graphics.
3. Log in as **aether** using the private `Aether-0.2.1-credentials.txt` file. Change the temporary password when prompted. Password entry is invisible. Root login is locked; use `sudo`.
4. Run `aether-efi-status`. It should report **UEFI 64-bit** and an `efivarfs` mount.
5. Run `startx` to open the graphical guest-integration session. **End session** returns to the console.

The disk has 64 GiB virtual capacity and grows as you store data. This is a separate image; changes made inside your previous Aether VM are not migrated automatically. Keep your previous VM for its files.

The supplied VMX shares only the included `Aether-Shared-Test` folder, under the name `AetherTest`. If you move the files, update the shared-folder path in VMware settings. Guest isolation enables copy/paste; host policy can still override it. Keep 3D acceleration disabled for this software-rendered development desktop.

## VirtualBox

Install VirtualBox on the host, then run `Set-Up-Aether-VirtualBox.ps1` from PowerShell with the VMDK beside it. The script creates a separate VDI copy and a new EFI VM, so the VMware and VirtualBox instances do not share a writable system disk. It refuses to overwrite an existing VM or output directory. It does not start the VM automatically.

For manual setup, use Linux 64-bit, EFI, Secure Boot disabled, VMSVGA graphics, 128 MiB video RAM, 3D disabled, SATA/AHCI storage, NAT with Intel PRO/1000 networking, and bidirectional clipboard. Attach a separate copy of the disk. Add the included test folder as `AetherTest`.

## Guest checks

After starting the graphical session:

- Resize the VM window and check whether the desktop and displayed resolution follow it.
- Copy text from Windows and press **Paste** in the Aether panel. Then use **Copy text** in Aether and paste into a host text editor.
- Open **Terminal**, then run:

```bash
aether-guest-status
sudo aether-mount-share AetherTest
cat /mnt/aether-shares/AetherTest/host-marker.txt
printf '%s\n' 'Written from Aether' > /mnt/aether-shares/AetherTest/guest-marker.txt
```

Check that `guest-marker.txt` appears in the Windows test folder. To unmount it, run `sudo umount /mnt/aether-shares/AetherTest`.

VMware's `vmtoolsd` starts automatically on VMware. VirtualBox's `VBoxService` and the VMSVGA display helper start on VirtualBox. Desktop clipboard/display clients start with `startx`. Services for the other hypervisor are intentionally skipped. Shared folders use `vmhgfs-fuse` on VMware and `vboxsf` on VirtualBox.

## About the EFI warning

An EFI environment is supplied by the VM firmware. A system started in legacy BIOS mode cannot expose EFI runtime services. The new VMX selects EFI, and the disk includes both the vendor bootloader and the standard removable-media EFI fallback, plus BIOS boot support. A firmware-settings GRUB entry is shown only under EFI.

The new kernel also enables framebuffer-console support missing from the earlier 0.2 image. Merely changing the old VMX to EFI can leave its text display blank. Use the matching 0.2.1 disk and VMX together. Secure Boot signing is not included.

## Scope and validation

The graphical session uses GTK 3, Xorg, TWM, and Xterm. It is a guest-integration development environment; the planned macOS-inspired desktop and local AI assistant remain future work. The base includes Linux 6.18.54-aether and GRUB 2.14. VMware tools 13.1.0 and VirtualBox additions 7.2.20 are built from source with Aether's native compiler. Build scripts use all available CPUs, 16 on the build VM.

Native VMware and VirtualBox clipboard/shared-folder transfers still require the checks above. This session cannot launch VMware through the Windows authorization service, and VirtualBox is not installed on the host. QEMU boot-test logs document the firmware, graphics, networking, and persistence checks that were possible here; they do not substitute for host integration testing.

Completed QEMU checks: BIOS and 64-bit UEFI boot; first-login password change and sudo; DHCP/DNS; guest-tool versions and library dependencies; Xorg/GTK startup; resolution change to 1024×768; clean system services; files surviving reboot. The EFI test also created a boot entry and verified it after reboot. The final EFI run exercised **End session** using emulated keyboard input. `Aether-0.2.1-desktop.png` shows the rendered session. Tests used the generic `qemu64` CPU, four virtual CPUs, and 3 GiB RAM.

The recipe archive contains build scripts, pinned source URLs/checksums, and configuration. It is not a complete mirror of upstream sources. Keep credentials private. Use the accompanying SHA256 file to verify public artifacts.
