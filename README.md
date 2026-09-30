# Aether Linux

**A Linux distribution built from source. Work in progress — 0.3, not release-ready.**

Aether is a from-scratch desktop Linux built by compiling every package in its
base system from pinned upstream sources. No binary distribution is downloaded
and repackaged. No prebuilt distro is bootstrapped.

Right now it boots, logs in, and runs a real desktop with a local AI assistant
that answers questions with nothing leaving the machine. It is also honest about
everything that is not finished yet — see [Status](#status) and
[What is not done](#what-is-not-done).

<p align="center">
  <img src="media/screenshots/01-desktop.png" width="880" alt="Aether Linux 0.3 desktop running KDE Plasma with the Aether theme">
</p>

---

## Nimbrel — AI that never phones home

<p align="center">
  <video src="media/videos/01-nimbrel-on-device-ai.mp4" width="880" controls muted loop playsinline></video>
</p>

**No account. No pairing. No network call.** The model runs on the CPU inside
the machine you are watching.

- **Qwen3.5 0.8B (Q4_0)**, served by llama.cpp, 563 MB of weights, Apache-2.0,
  pinned to a single GGUF revision by SHA-256 (`src/nimbrel/model.json`)
- Reached only through **Unix domain sockets** — there is no listening TCP port
- `RestrictAddressFamilies=AF_UNIX` on both services: the engine is
  **kernel-forbidden from opening any IP socket**, so the AI cannot phone home
  even if the model itself wanted to
- A second socket is mode `0666`; every request is authorised by
  `SO_PEERCRED`, so the kernel tells the server which local user asked
- Hardening: dedicated `nimbrel` service account, `NoNewPrivileges`,
  `PrivateTmp`, `PrivateDevices`, `ProtectSystem=strict`, `ProtectHome`,
  `ProtectKernelTunables`, `ProtectControlGroups`, `UMask=0077`,
  `MemoryMax`/`TasksMax` caps, and a `0700` runtime directory for the engine
- ~6.6 tokens/sec on 6 vCPUs, generic x86-64, **no AVX/AVX2/FMA, no CUDA**

Being blunt about the model: **0.8B is small.** It is good enough for
definitions, summaries and light drafting, and it will confidently get things
wrong. That is why Nimbrel labels its own output *"Check important answers"*.
Nimbrel has **no command execution, no network access, and no vision** — by
design, not by omission.

## The desktop

<p align="center">
  <video src="media/videos/02-aurasearch-and-vector.mp4" width="880" controls muted loop playsinline></video>
</p>

`Super+Space` opens **AuraSearch** — applications, local files, settings, and
inline calculation. **Vector** is Aether's own applications-and-files browser.

<p align="center">
  <img src="media/screenshots/06-login-greeter.png" width="420" alt="Aether login greeter">
  <img src="media/screenshots/09-power-menu.png" width="420" alt="Aether power menu">
</p>
<p align="center">
  <img src="media/screenshots/21-security-center.png" width="420" alt="Aether Security Center, showing what is protected, unverified and unsupported">
  <img src="media/screenshots/20-installer-complete.png" width="420" alt="Aether installer completion">
</p>

## What is actually in the box

| | |
|---|---|
| **Kernel** | Linux 6.18.54-aether4, built in-tree with nftables, AppArmor, Yama, Landlock, FORTIFY, hardened usercopy, I/O IOMMU defaults |
| **Init** | systemd |
| **Display** | KDE Plasma 6 (Wayland default, X11 compatibility session) |
| **Session** | LightDM + a custom Aether greeter |
| **Search** | AuraSearch — first-party launcher and search shell |
| **AI** | Nimbrel + llama.cpp + Qwen3.5 0.8B, fully on-device |
| **Files** | Vector — first-party applications & files browser |
| **Security** | nftables default-deny, AppArmor, `aether-security-status`, PAM lockout, cryptsetup/LUKS2 |
| **Backups** | restic 0.19.1, encrypted, user-driven setup, no backup until it succeeds |
| **Updates** | GnuPG package signing + TUF repository tooling — built and tested, **not deployed** |
| **Install** | Interactive x86_64 installer: whole-disk, optional LUKS2, mandatory first-boot password change |

<p align="center">
  <img src="media/screenshots/08-vector-applications.png" width="880" alt="Vector showing 23 installed Aether and KDE applications">
</p>

## Status

> ### ⚠️ This is a development snapshot, not a distribution release.
>
> Aether is **not finished, not audited, and not certified.** Nothing here is a
> security or compliance claim. Please read this before you install it.

The full per-area breakdown lives in [`docs/verification.md`](docs/verification.md).

**Verified**

- Native source build of Qt, KDE Frameworks, Plasma, desktop applications and
  the printing portal completes on 16 build CPUs
- GMP / MPFR / MPC rebuilt for a baseline x86-64 CPU; upstream test suites pass
  (198 MPFR tests, 75 MPC tests)
- UEFI disk boot: graphical login, wrong-password rejection, **mandatory
  first-boot password change**, Plasma Wayland, DHCP, DNS, verified HTTPS,
  printing portal, captured audio
- AuraSearch opens, calculates `2+2=4`, launches apps, finds indexed files
- Screen lock and password unlock; reboot preserves the changed password;
  clean shutdown
- Native Tesseract OCR recognises a generated English test image
- The released VMDK passes `qemu-img compare` against the detached raw image:
  *Images are identical*

**Not verified**

- **No physical hardware.** Every result is from virtualised or emulated CPUs
- **x86_64 only.** i686, ARM64 and Raspberry Pi desktop images are not built or
  updated. (`x64` and `x86_64` are the same architecture.)
- **Secure Boot is unsupported** and kernel module signatures are *not enforced*
- BIOS unlock automation is **intermittent** and is not marked as passing; UEFI
  is the recommended configuration
- Native VMware/VirtualBox clipboard and drag-drop are only partially verified

## What is not done

Stated plainly, because a project that hides this is not worth trusting:

- ❌ No **production update repository**. The TUF/signing tooling is built and
  tested; nothing is deployed. There is no automatic update timer.
- ❌ No **ARM64**, i686 or Raspberry Pi desktop image
- ❌ No **Secure Boot**, no signed UKI, no verified boot chain
- ❌ No **TPM** enrollment or attestation
- ❌ No **Flatpak** or sandboxed application distribution
- ❌ **Most desktop apps are still unconfined** by AppArmor
- ❌ Installer is **whole-disk only** — it does not convert an existing install
- ❌ `/boot` is **not encrypted**; hibernation is disabled
- ❌ Backup credentials are root-readable local files, so root compromise
  exposes them
- ❌ No firmware/microcode update coverage, no maintained browser
- ❌ SSH is **not installed** by this build
- ❌ No accessibility, FIDO, biometric or multi-user lock-boundary testing

## Repository layout

```
docs/           architecture, build, verification, roadmap
media/          screenshots and videos (all recorded from a real Aether VM)
src/desktop/    Vector, greeter, installer, Plasma shell + power menu
src/nimbrel/    on-device AI client, gateway, engine wiring
src/security/   firewall, AppArmor, PAM, backups, security tooling
src/updates/    GnuPG signing + TUF repository and client
src/assets/     wallpapers, colour schemes, screensavers, Plymouth, layouts
```

## Build it yourself

Aether is built by compiling from pinned sources — there is no binary
tarball of the base system. See [`docs/build.md`](docs/build.md) for the recipe
and [`docs/architecture.md`](docs/architecture.md) for how the pieces fit
together.

> **Licensing note.** Aether's own code and assets are **GPL-3.0-or-later**.
> The Linux kernel and some other base components are **GPL-2.0-only**, which is
> *not* compatible with GPL-3.0. Those components keep their own licences, and
> the distribution as a whole ships under the corresponding per-component terms.
> See [`docs/licensing.md`](docs/licensing.md).

## Contributing

Aether is early and the build system is opinionated. Read
[`CONTRIBUTING.md`](CONTRIBUTING.md) first — it explains what will and will not
be accepted, and the security rules are not optional.

## Status badges are absent on purpose

There is no CI badge, because there is no CI yet, and a green badge on a
project this young would be a lie. Build verification is documented manually in
[`docs/verification.md`](docs/verification.md).

---

*Aether Linux 0.3 · development snapshot · not a release · not certified.*