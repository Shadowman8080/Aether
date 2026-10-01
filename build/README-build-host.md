# Aether Linux: First Light

> Current native development: see [Aether 0.2.1 guest integration](next/GUEST-INTEGRATION.md) and [persistent base](next/PERSISTENT-BASE.md). The content below describes the older First Light live prototype.

This is Aether's first source-built x86-64 boot prototype. Ubuntu is only the
build host. Buildroot 2026.08 automates compilation; this is not a remastered
Ubuntu image and is not a completed Linux From Scratch book installation.

## Scope

The internal Aether toolchain builds Binutils, GCC, glibc, a Linux kernel,
BusyBox init/utilities, Bash, GNU coreutils, and BIOS/UEFI GRUB from source.
This is a RAM-based live console image. It is not yet a desktop distribution,
installer, persistent system, or self-hosting development environment.
It does not yet provide a package manager, AI, Wi-Fi firmware, or Secure Boot.
The pinned kernel is the Buildroot QEMU reference kernel; update it and review
security fixes before any public release. Virtual boot tests do not establish
compatibility with every physical Intel/AMD computer.

## Build

All commands below run inside the Ubuntu build VM. Compile as `aetherbuild`:

    sudo -iu aetherbuild
    cd /opt/aether
    ./scripts/fetch-buildroot.sh
    ./scripts/build.sh
    ./scripts/make-iso.sh
    ./scripts/test-boot.py bios
    ./scripts/test-boot.py uefi

The build uses `nproc` for package-level make parallelism (16 threads on this
VM), including through Buildroot's BR2_JLEVEL override. Dependencies and some
configuration/install stages are sequential. Generic x86-64 code generation
is configured, not -march=native or x86-64-v2/v3/v4.

Build scripts expect /opt/aether. Host tools are installed by the administrator.
The host-tools/install symlink selects /usr/bin/gnuinstall for this build to
avoid an upstream-documented Ubuntu uutils install compatibility problem.

## Files

- configs/aether_defconfig: source/toolchain/system configuration
- configs/linux.config: requested kernel configuration, including VMware drivers
- configs/grub-early.cfg: find the ISO and load its boot menu
- overlay/: Aether identity, welcome text, and boot self-tests
- scripts/: source fetching, building, ISO creation, and boot tests
- build/prototype/host/: source-built Aether cross compiler and sysroot
- build/prototype/images/: raw kernel, rootfs archives, and bootloaders
- images/aether-0.1-x86_64.iso: BIOS and UEFI CD/DVD boot image
- logs/: build output and BIOS/UEFI serial test transcripts

The source archive's SHA-256 is pinned after download over upstream HTTPS.
Buildroot validates component downloads against its shipped hash files.
This is not a claim of independently verified release-signing identities or
bit-for-bit reproducibility across different build hosts.

## Boot in VMware

Create a separate x86-64 test VM and attach the ISO as its virtual CD/DVD.
Start with 2 virtual CPUs and 1 GB RAM. Enable connect at power on and boot CD.
Either legacy BIOS or UEFI can be selected; disable Secure Boot for this unsigned
prototype. No hard disk is required. Keep the Ubuntu build VM intact.

Log in as `root` at the console with no password. This is intentional for this
local development image; no remote login server is installed. The normal boot
menu opens the console, and the self-test menu powers off after its checks.
Changes disappear on shutdown. Run `poweroff` to stop the guest.

## Roadmap beyond this milestone

Decide the long-term package/update architecture before adding the desktop.
Buildroot does not provide a general-purpose binary package manager. Aether's
desktop, installation, updates, and AI integration remain separate work.
