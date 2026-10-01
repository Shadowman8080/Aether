# Aether guest integration builds

These are source-built console prototypes. KDE, the local AI interface, a persistent installer, production signing, and desktop clipboard/resize integration are not part of these ISOs yet.

The existing Ubuntu build VM provides build tools only. Target executables are built using Aether's own GCC/glibc toolchains. Compilation uses `nproc` (16 CPUs on this VM). The native LFS system under `system/` is a separate project stage.

## Components

- open-vm-tools 13.1.0-25218885: hardware-detected daemon startup and the `vmhgfs-fuse` shared-folder helper. The console profile excludes X11, VGAuth/PAM, deployment plugins, and TLS components.
- VirtualBox 7.2.20 source: VBoxService, VBoxControl, mount.vboxsf. The kernel supplies vboxguest and vboxsf. The proprietary Extension Pack is not used.
- The x86 VirtualBox build defines `RT_WITH_OLD_CPU_SUPPORT` to avoid an unconditional SSE2 memory fence on Pentium III-class CPUs.
- VMware and VirtualBox daemons start only when their respective guest hardware is detected. The first Ethernet interface uses DHCP.

Source URLs and verified SHA-256 values are in `configs/guest-sources.json`. The open-vm-tools compatibility patches are in `aether-external/package/aether-vmtools/`. The VirtualBox build uses a separate native compiler definition for build-time generators when cross-compiling.

## Rebuild on the prepared build VM

Run as `aetherbuild` from `/opt/aether`, after fetching/extracting the locked guest sources with `python3 scripts/fetch-guest-sources.py`:

64-bit x86:

```sh
bash scripts/build-vmtools-x64.sh
bash scripts/build-vbox.sh x86_64
bash scripts/finish-guest-x64.sh
```

32-bit x86:

```sh
bash scripts/build-vmtools-x86.sh
bash scripts/finish-guest-x86.sh
```

ARM64 VM:

```sh
bash scripts/build-arm64-base.sh
bash scripts/finish-guest-arm64.sh
```

Each finish script records success only after its ISO boot test passes. Inspect `logs/guest-x64.status`, `logs/guest-x86.status`, or `logs/guest-arm64.status`; `STARTED` without `EXIT 0` is not a completed build. A test failure leaves an ISO on disk, but that file is not a validated deliverable.

`aether-guest-status` reports installed tools and detected guest services. VMware's vmtoolsd intentionally exits outside VMware, even when asked for its version. The QEMU tests check the supported non-VMware path; they do not validate VMware host/guest RPC operations. Native VMware testing from this Windows agent was blocked by access denial to VMware's authorization pipe. A native VirtualBox host was not available.

ARM64 VM images require ARM virtualization hardware, or full-system emulation such as QEMU. Raspberry Pi images require board-specific kernels, firmware and SD-card layouts; the Pi model selection remains pending.

The x86 0.1.1 image passed BIOS boot and guest-utility checks on QEMU's Pentium III CPU model with 512 MiB RAM. The x86_64 image passed BIOS and UEFI boot. The ARM64 image passed UEFI boot on QEMU's Cortex-A53 model with 1 GiB RAM, including execution of the ARM64 VirtualBox utilities. The images also have separate DHCP/gateway test scripts.

On ARM64, use NVMe, SATA/AHCI, or virtio storage as supported by the VM platform. Linux 6.18's VMware PVSCSI driver is x86-only and is not present in the ARM kernel.
