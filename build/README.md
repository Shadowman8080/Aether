build/: publish the build host's Aether work

This directory is the build host's Aether tree, carried over from the machine
that compiles the images. Until now it existed in exactly one place, on a
virtual machine with no remote configured, and was one disk failure from gone.

It is the counterpart to `src/`, not a replacement for it. `src/` is the
application code you read; `build/` is everything needed to turn pinned upstream
sources into a bootable image.

## Layout

```
configs/        Buildroot defconfig, kernel config, build settings
desktop/        Plasma desktop build recipes and scripts
apt/            apt/dpkg package-manager chain and the synthetic dpkg database
next/           in-progress work: assistant, guest, packages, release, scripts
overlay/        root filesystem overlay for the console base
overlay-x86/    overlay additions for x86
overlay-arm64/  overlay additions for ARM64
patches/        patches Aether applies to upstream GPL components
  upstream/       glibc, LLVM, Python, libssh2, kbd, tar, coreutils, bzip2,
                  docbook-xsl, itstool, expect, efivar
scripts/        build driver scripts
security/       firewall, AppArmor, PAM, backup and security tooling
aether-external/ external package definitions
```

## Reading the build

Start at `desktop/README.md` for the desktop pipeline, or
`configs/` plus `build-env.sh` for the console base. `README-build-host.md`
describes the build host itself.

`gitignore-build-host` is the build host's own ignore rules, kept for
reference. It is named without a leading dot so it does not affect this
repository.

## What is deliberately not here

- **ISOs and VMDKs.** Build outputs, and over GitHub's 100 MB per-file limit.
  Published as release assets instead.
- **Upstream source archives.** Several GiB of unmodified third-party source.
  Distributed as release assets with a digest manifest; see the Source code
  section of the top-level README.
- **Host toolchain trees** (`host-tools/`, the Go and LLVM source checkouts).
  These build Aether but are not part of Aether.
- **R2 credentials.** Never committed.
