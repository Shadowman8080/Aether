# Building Aether

Aether is built by **compiling from pinned upstream sources**. There is no binary
tarball of the base system and no other distribution is bootstrapped. That is
the point of the project, and it is also why a full build takes hours and a lot
of disk.

## Requirements

| | |
|---|---|
| **Architecture** | x86_64 only |
| **Build host** | Linux, all CPUs used (the 0.3 desktop build used 16) |
| **Disk** | Budget generously; a full source build is on the order of 100 GB+ |
| **RAM** | 32 GB recommended for the heaviest native packages |
| **Time** | Hours for a cold build |

Only `x86_64` is supported. There are no i686, ARM64 or Raspberry Pi desktop
images, and older images for those targets are **not** upgraded desktop builds.

## How the build is organised

The build is driven by Python *recipe* scripts that append to an Arch-style
package set. Recipes are grouped by feature area and mirror the `src/` layout:

```
src/
├── desktop/     Plasma shell layout, power menu, greeter, installer, Vector
├── nimbrel/     native bindings, llama.cpp, engine packaging, units
├── security/    PAM helper, firewall tooling, cryptsetup, restic
├── updates/     python-tuf, GnuPG signing, release/client tooling
└── assets/      wallpapers, colour schemes, screensavers, Plymouth, layouts
```

Typical recipe names in the working tree are `add-<area>-<thing>.py`,
`build-<area>-<thing>.sh` and `fetch-<area>-<thing>.py`.

**Use every available CPU.** The build scripts scale thread counts from
`nproc`; do not override that downward on a build host.

## Source pinning

Sources are pinned in `sources.json`, and archive digests are recorded
alongside them. Some archives carry upstream-published SHA-256 verification;
others were fetched over upstream HTTPS with a pinned digest and, where
available, a cross-check against a published checksum list.

Be precise about what this means: pinning and digest checks protect against
*accidental* drift. They are **not** a claim that every upstream signing key or
the complete supply chain was independently authenticated.

Nimbrel's model weights are pinned the same way — see
[`../src/nimbrel/model.json`](../src/nimbrel/model.json) for repository,
revision, SHA-256, byte count and licence.

## Native compilation highlights

- GMP, MPFR and MPC are rebuilt for a **baseline** x86-64 target so they do not
  emit illegal instructions on older CPUs. This is why `qemu64` guests work.
- Qt is built **with CUPS support**, and KDE's printing portal is installed.
- Mesa and LLVM are built with clang for the generic CPU target.
- The kernel is built in-tree as `6.18.54-aether4` with nftables, AppArmor, Yama
  and Landlock, plus stack-offset randomisation, hardened usercopy, FORTIFY,
  allocation initialisation, IOMMU defaults and zram.
- Module signature *support* is compiled in but signatures are **not enforced**.

## Producing images

The 0.3 build produces two artefact shapes:

| Artefact | Notes |
|---|---|
| **Live ISO** | BIOS and x86_64 UEFI boot loaders. Changes are lost on shutdown. |
| **VMDK** | Whole-disk image for VMware/VirtualBox. Sparse, changes persist. |

Both carry a `SHA256SUMS` file. The released VMDK is `writable
monolithicSparse` and is validated with `qemu-img compare` against the detached
raw image.

To ship a VMDK to others, do **not** use GitHub Releases: the per-file limit is
2 GiB and the disk image is roughly 6.9 GB. ISOs are fine.

## Build verification

After a build, the checks in [`verification.md`](verification.md) are run
manually. There is no CI, so the build scripts are the only automated gate —
if you change one, say so in the pull request and state what you re-ran.

## Known build-system sharp edges

- **LightDM's command format** must be matched exactly by the session launcher.
- The **CA bundle path** must be set or HTTPS verification fails.
- **PAM helper ownership and permissions** must be correct or screen unlock
  fails in a way that looks like a wrong password.
- The **CA/PAM/session chain** has caused bugs that only appear at runtime, not
  at compile time. A clean build is not evidence of a working desktop.