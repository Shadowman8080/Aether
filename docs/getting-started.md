# Getting started with Aether

[Documentation home](README.md)

Aether 0.3.2 is a development snapshot. Use a virtual machine for evaluation and
keep backups of important files. The current desktop target is x86_64; x64 is
another name for the same architecture.

## Choose a download

Open the [0.3.2 development release](https://github.com/Shadowman8080/Aether/releases/tag/0.3.2-dev.20261006).

- **ISO:** boot a live desktop or start the installer. Live-session changes are
  lost on shutdown unless you install to a disk.
- **VMware bundle (`-vm.tar.xz`):** a clean, persistent VMDK and matching VMX.
  Extract the archive before opening it; keep both files in the same folder.
- **Source archives:** application source, build recipes and upstream inputs for developers.

Read the included `README-VM.txt` and `VERIFICATION.json`. Compare downloads with
`SHA256SUMS`; these checksums detect corruption and are not release signatures.

## Start the VMware desktop

1. Extract the VM bundle and open its `.vmx` in VMware. The supplied configuration
   requires a VMware version supporting virtual hardware 22.
2. The supplied VM uses four virtual CPUs, 6 GiB RAM, NAT, UEFI and a 32 GiB virtual
   disk. Secure Boot is disabled. The build host is not needed to run Aether.
3. Start the VM and sign in with the public development credentials below.

- Username: `aether`
- Password: `aether2026`

These credentials apply to the clean downloadable image. An existing personal
installation keeps its own account settings. Choose your own password when installing.

For automatic mouse release, set VMware's input preferences to automatically
grab/ungrab the mouse and set mouse optimization for games to **Never**. The
supplied VMX enables clipboard and drag/drop; shared host folders are disabled.
See [guest integration](guest-integration-status.md) for helper checks and limits.

For VirtualBox, create a 64-bit Linux VM, attach the VMDK using SATA, enable EFI,
select VMSVGA and a USB Tablet, and enable Mouse Integration. Enable bidirectional
clipboard/drag-and-drop explicitly if wanted. Native VirtualBox interactions
have not been certified for this snapshot.

## Explore the desktop

- Open **Aether Settings** for first-run guidance, performance, privacy,
  accessibility, applications and update/recovery controls.
- Press **Super+Space** for AuraSearch. Use **Vector** to browse applications and files.
- Open **Nimbrel** for on-device AI. Its small model can make mistakes; check
  important answers. Folder indexing is opt-in and does not automatically send
  documents to the model.
- Use **Discover** for Flatpak applications after choosing whether to enable Flathub.

## Installation and updates

The installer is whole-disk only. Select only a disposable or backed-up target;
it does not convert an existing installation. Disk encryption is an installer
option. Secure Boot is not supported and `/boot` is not encrypted.

Aether checks for OS updates automatically and asks before installation, but the
public OS update feed remains unconfigured pending release trust and base-package
inventory work. This is an explicit development limitation. Do not install
publisher credentials or private signing keys on client machines.

[Current testing and known limitations](modern-desktop-20261006.md) explain what
has been verified. Keep your previous image and backups when evaluating a new build.
