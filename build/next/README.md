# Aether native distribution development

This tree extends the boot-tested 0.1 recovery prototype into a persistent, self-hosting desktop distribution. It is not yet an installable desktop release.

## Current persistent-base status

Step one is complete for x86-64. See [PERSISTENT-BASE.md](PERSISTENT-BASE.md) for the shipped disk, tested behavior, current detached-image state, and relocated native build metadata. The historical active-work notes below describe earlier development. The build-only sudo rule has been removed.

## Current guest-integration status

Aether 0.2.1 adds source-native VMware and VirtualBox tools, a basic X11/GTK graphical integration session, EFI utilities, and framebuffer console support. Its separate disk and VMware template default to UEFI. See [GUEST-INTEGRATION.md](GUEST-INTEGRATION.md) for recipes and validation limits. Native hypervisor clipboard/shared-folder tests remain outstanding. The full desktop and local assistant are not yet packaged in this image.

## Decisions

- Source-built x86-64 system: LFS 13.1 systemd, followed by BLFS libraries and Plasma. Ubuntu is the build host only.
- Generic x86-64 CPU baseline; do not compile distributable components with `-march=native`. All parallel-capable builds use `nproc` jobs. Critical toolchain tests remain enabled.
- BIOS and UEFI boot. Desktop kernel follows the maintained 6.18 long-term branch, beginning at 6.18.54. The LFS book's 7.1.8 API headers are separate from the runtime kernel.
- Plasma top bar and floating application dock, with original Aether wallpaper and branding.
- Local AI first, optional cloud support later. No cloud provider, credentials, or remote chat path is configured.
- Planned package management is source-built pacman with Aether's own signed repository. This is not an Arch binary distribution.

## Historical base-build work

The native base build runs in `/opt/aether/system/jhalfs`; its log is `/opt/aether/logs/next/base-run.log`. It builds a source toolchain and userspace into the root filesystem mounted from `/opt/aether/build/aether-system.raw`.

The 64 GiB sparse image contains a BIOS boot partition, an EFI system partition, and an ext4 root. The Ubuntu host disk is not an installation target. Never boot the raw image read-write in QEMU while its partitions or chroot mounts are mounted by the builder.

`scripts/finish-component-tests.sh` builds the host inference engine without the optional web frontend or HTTPS support, runs the offline integration test, then builds the next kernel into a staging directory. These host-linked assistant binaries are for testing only. Rebuild the app and inference engine against Aether's own libraries before packaging. Run component verification only when no separate build of the same component is active.

## Local assistant

`assistant/` contains a Qt 6 interface and a Python standard-library session manager. Its pinned model is Qwen3.5 0.8B Q4_0, approximately 563 MB, with exact revision, size, download URL and SHA256 in `model.json`. Model downloading is an explicit action. Normal chat uses only authenticated loopback requests and bypasses proxy environment variables.

The model starts with the first question and stops when the session closes. Chat history is held in memory. The assistant cannot run commands or autonomously read files; a user may preview and share a text file. Keep AI optional for low-memory machines. Hardware minimums are not validated yet.

All seven `test_ai.py` tests pass, covering downloader integrity, oversized downloads, path handling, corrupt cached models and requests rejected before model startup. `test_inference.py` passed with real model inference in a network namespace containing only loopback. It also verified authentication, proxy bypass and process/key cleanup. The host UI has been compiled and rendered for initial layout review. Native desktop integration is still pending.

## Package workflow tested on the build host

Pacman 7.1.0 was built from its pinned upstream source into an isolated host prefix. An original Aether wallpaper package was created and signed with a temporary development test key. A signed file-based repository installed and removed it in a disposable root. Tests also rejected unsigned packages, altered packages and an altered repository database. See `scripts/build-package-tools.sh` and `scripts/test-package-repository.sh`.

This proves the package/signature workflow, not native package-manager integration or recovery from interrupted OS updates. The test key expires after 30 days and must not become a production release key. Private keys stay under the ignored build directory and are excluded from source archives. Build pacman and its dependencies natively before installing it in Aether.

## Remaining release gates

Complete native hypervisor integration testing; build native pacman and libraries; create a signed test repository and verify rejection of tampered packages; build Plasma and service dependencies; extend first-boot setup beyond the existing password change; test networking, audio and suspend where hardware allows; rebuild and package the assistant; implement and test installer/recovery flows on disposable disks; record checksums, licenses and source manifests; produce a new bootable release image.

Physical hardware coverage, Secure Boot and public update hosting are not yet established. Do not advertise these as supported based solely on VM tests.

## Builder notes

The LFS generator is pinned by `configs/jhalfs.commit`; the LFS and BLFS books have separate pinned commits. Generated libffi instructions were adjusted from `--with-gcc-arch=native` to `--with-gcc-arch=x86-64`; retain that adjustment if regenerating.

The build host uses GNU install via alternatives and Bash for `/bin/sh`, as required by this build setup. The historical temporary `/etc/sudoers.d/aether-source-build` rule has been removed. The guest-integration builder uses a private mount namespace entered by an administrator. Never copy build-only privilege rules into Aether.

LLVM's required fix is cached as `sources/lfs-cache/llvm-22.1.8-upstream_fix-1.patch`, fetched from the official release archive at https://www.linuxfromscratch.org/blfs/downloads/13.1-systemd/patches/llvm-22.1.8-upstream_fix-1.patch . The book's initial patch URL returned 404.
