# Aether Linux

**A Linux distribution built from source. Work in progress — not release-ready.**

[Website](https://shadowman8080.github.io/Aether/) · [Documentation](docs/README.md) · [Development downloads](https://github.com/Shadowman8080/Aether/releases) · [October 6 progress](docs/modern-desktop-20261006.md) · [Image verification](docs/modern-desktop-20261006.md#validation)

**New in the November 4 snapshot:** **Aether Beam** installs several
applications at once — preparation is threaded, package transactions stay
serialized — and **Aether Pilot** is a Copilot-style assistant that may only
propose an action from a fixed, reviewed catalog, which a person confirms and the
machine records. Both are implemented in source and unit-tested offline; no
published image contains them yet.

**In the October 6 snapshot:** Aether Settings, a Flatpak app store, on-demand
Nimbrel, privacy controls, phone connection and recovery. Public OS update trust
remains unconfigured while release keys and the base package inventory are
prepared. Aether is still a work in progress.

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
- Baseline x86-64 CPU build, **no BMI2/AVX/AVX2/FMA requirement, no CUDA**;
  response time depends on hardware and load

Being blunt about the model: **0.8B is small.** It is good enough for
definitions, summaries and light drafting, and it will confidently get things
wrong. That is why Nimbrel labels its own output *"Check important answers"*.
Nimbrel has **no command execution, no network access, and no vision** — by
design, not by omission. Acting on the machine is [Aether Pilot](docs/pilot.md)'s
job instead: a fixed catalog, a person's confirmation, and an audit line.

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

## Aether Glass — a softer sound for your desktop

Forty-two original chimes and effects for notifications, devices, power and
more. Generated from source. No borrowed system sounds, no constant click
noises, and your volume and mute preferences stay yours.

[Listen to the preview](media/audio/aether-glass-preview.wav) ·
[Build and install](src/sounds/README.md) · [Deployment status](docs/sounds.md)

**Development update:** Aether Glass is included in the unified 20261006.1
image build. Applications choose which sound events they emit; guest audio
playback still needs confirmation.

Vector also gives application, file and sidebar icons a brief click animation.
The power button has matching feedback; disabling KDE animations disables this
motion. [Animation details](docs/icon-motion.md).

The unified x86_64 image replaces the separate desktop, security, Vector and
local-AI variants. Historical x86 and ARM console prototypes remain archived;
they are not current desktop builds. See [release verification](docs/release-20261006.md).

## Aether Server

Alongside the desktop, Aether is growing a **server edition** — a
console-first image in the spirit of Ubuntu Server with an interactive
**graphical** installer. It configures the network, creates an administrator
with sudo, applies a data-driven **role catalog** (DHCP, NTP, DNS, RADIUS/TACACS+,
syslog, files, databases, web, mail, proxies, virtualization, printing and
more), and can join an Active Directory domain during installation.

The catalog is data, not code: `src/server/roles/catalog.json` drives both the
installer UI and the install backend, so a new server role is a catalog entry
plus a config template. A role whose software is not built into the image is
reported as unavailable rather than failing the install.

Status, roles and design: [`docs/server.md`](docs/server.md). Like the rest of
Aether 0.3, the server edition is work in progress — the catalog and backend
are unit-tested, and nothing has been compiled or booted yet.

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
| **Devices** | Aether Devices — plug-and-play manager + hotplug notifications, udev/hwdb policy, driver auto-loading |
| **Security** | nftables default-deny, AppArmor, `aether-security-status`, PAM lockout, cryptsetup/LUKS2 |
| **Secure Boot** | UEFI signed shim → GRUB → UKI, Aether PK/KEK/db enrollment, signed live UEFI media |
| **Backups** | restic 0.19.1, encrypted, user-driven setup, no backup until it succeeds |
| **Updates** | GnuPG package signing + TUF repository tooling — built and tested, **not deployed** |
| **Install** | Interactive x86_64 installer: whole-disk, optional LUKS2, mandatory first-boot password change |
| **Installs** | Beam — concurrent download and verification, one package transaction at a time, resumable |
| **Pilot** | Allowlisted system actions that a person confirms, with a local audit log |

<p align="center">
  <img src="media/screenshots/08-vector-applications.png" width="880" alt="Vector showing 23 installed Aether and KDE applications">
</p>

## Every screenshot and video

Everything below was recorded from a **live Aether 0.3 virtual machine** — no
mockups, no design files, no staged dialogs. Full provenance, capture method and
per-file notes are in [`media/README.md`](media/README.md).

### Videos

<p align="center">
  <video src="media/videos/01-nimbrel-on-device-ai.mp4" width="880" controls muted loop playsinline></video>
  <br><sub>01 — Nimbrel answering on-device. 46 s. Nothing leaves the machine.</sub>
</p>

<p align="center">
  <video src="media/videos/02-aurasearch-and-vector.mp4" width="880" controls muted loop playsinline></video>
  <br><sub>02 — AuraSearch and Vector. 26 s. Real synthetic X11 input.</sub>
</p>

### Desktop sessions

<p align="center">
  <img src="media/screenshots/01-desktop.png" width="880" alt="Aether Plasma session, the hero image">
</p>

<p align="center">
  <img src="media/screenshots/11-desktop-session.png" width="420" alt="A second desktop session">
  <img src="media/screenshots/24-installed-desktop.png" width="420" alt="First boot from the installed disk">
</p>
<p align="center">
  <img src="media/screenshots/25-desktop-panels.png" width="420" alt="Panel layout">
  <img src="media/screenshots/32-kate-editor.png" width="420" alt="Kate text editor">
</p>
<p align="center">
  <img src="media/screenshots/14-vmware-integration.png" width="420" alt="VMware guest integration in the panel">
  <img src="media/screenshots/31-vector-dark.png" width="420" alt="Vector in the dark colour scheme">
</p>

### AuraSearch and Vector

<p align="center">
  <img src="media/screenshots/08-vector-applications.png" width="880" alt="Vector showing 23 installed applications">
</p>

<p align="center">
  <img src="media/screenshots/02-aurasearch.png" width="420" alt="AuraSearch with an inline calculation">
  <img src="media/screenshots/05-aurasearch-launch.png" width="420" alt="The AuraSearch launcher">
</p>
<p align="center">
  <img src="media/screenshots/04-aurasearch-results.png" width="420" alt="AuraSearch results across apps, files and settings">
  <img src="media/screenshots/07-vector-file-manager.png" width="420" alt="Vector browsing the home directory">
</p>

### Nimbrel

<p align="center">
  <img src="media/screenshots/03-nimbrel-ai.png" width="880" alt="A real on-device answer from Nimbrel">
  <br><sub>Captured from video 01 — same pixels, not a staged capture. Note the
  "Check important answers" label: 0.8B is a small model and it says so.</sub>
</p>

### Greeter, lock screen and power

<p align="center">
  <img src="media/screenshots/06-login-greeter.png" width="420" alt="Aether login greeter">
  <img src="media/screenshots/33-greeter-current.png" width="420" alt="The greeter in its current form">
</p>
<p align="center">
  <img src="media/screenshots/12-caps-lock-warning.png" width="420" alt="Caps Lock warning at the greeter">
  <img src="media/screenshots/27-wrong-password.png" width="420" alt="Rejected sign-in">
</p>
<p align="center">
  <img src="media/screenshots/26-lock-screen.png" width="420" alt="Lock screen clock and actions">
  <img src="media/screenshots/09-power-menu.png" width="420" alt="Power menu with lock, sleep, restart, shut down">
</p>
<p align="center">
  <img src="media/screenshots/10-login-power-menu.png" width="420" alt="Power menu reachable before login">
  <img src="media/screenshots/13-shutdown-confirmation.png" width="420" alt="Shutdown countdown confirmation">
</p>

### Installer

<p align="center">
  <img src="media/screenshots/15-installer.png" width="880" alt="Installer welcome page stating the whole-disk limitation">
</p>

<p align="center">
  <img src="media/screenshots/16-installer-welcome.png" width="420" alt="Installer welcome page">
  <img src="media/screenshots/17-installer-region.png" width="420" alt="Region, keyboard and time zone">
</p>
<p align="center">
  <img src="media/screenshots/18-installer-account.png" width="420" alt="Account, LUKS2 and recovery passphrases">
  <img src="media/screenshots/19-installer-review.png" width="420" alt="Review page confirming erasure of the disk">
</p>
<p align="center">
  <img src="media/screenshots/20-installer-complete.png" width="420" alt="Installation finished, GRUB installed for both platforms">
</p>

### Security and encrypted boot

<p align="center">
  <img src="media/screenshots/21-security-center.png" width="880" alt="Aether Security Center showing what is protected, unverified and unsupported">
  <br><sub>The Security Center reports unverified items as unverified. That is
  the point of it.</sub>
</p>

<p align="center">
  <img src="media/screenshots/22-encrypted-unlock.png" width="420" alt="LUKS2 unlock prompt">
  <img src="media/screenshots/23-security-encrypted-boot.png" width="420" alt="Kernel log from an encrypted boot with AppArmor and Landlock present">
</p>

### Boot

<p align="center">
  <img src="media/screenshots/30-boot-splash.png" width="420" alt="The Aether Plymouth boot splash">
  <img src="media/screenshots/29-boot-menu.png" width="420" alt="The Aether GRUB menu with UEFI entries">
</p>

<details>
<summary>Settings and screen savers</summary>

<p align="center">
  <img src="media/screenshots/28-screensavers.png" width="420" alt="Screen saver previews">
</p>

</details>

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
- **Secure Boot**: signed shim, GRUB and UKI booted under OVMF with firmware
  Secure Boot enabled and the Aether db enrolled; the same signed chain booted
  an installed disk to `aether login:`, and the signed live ISO booted to the
  live desktop. VMware Workstation 26.0.1 and VirtualBox 7.2.22 also booted the
  signed ISO and an installed disk to `aether login:` with Secure Boot enabled.
  Legacy BIOS live boot also passed.

**Not verified**

- **No physical hardware.** Every result is from virtualised or emulated CPUs
- **Plug-and-play devices** are implemented in source (udev policy, device
  manager, hotplug notifications, kernel driver classes) but **not yet compiled
  into an image or boot-tested** — no hardware support claim exists
- **x86_64 only.** i686, ARM64 and Raspberry Pi desktop images are not built or
  updated. (`x64` and `x86_64` are the same architecture.) See
  [ARM64 status](docs/arm64.md) for what exists and what is missing.
- **Beam and Pilot are not in any image.** Both are implemented in source and
  unit-tested offline; nothing has been compiled into an image or booted.
- **Secure Boot** is implemented for UEFI Aether media and installs when the
  Aether key is enrolled. Physical hardware, firmware other than
  OVMF/VMware/VirtualBox, production key revocation, and the installer's GUI
  enrollment action are still unverified. A disposable OVMF lab fixture now
  executes signed dbx and SBAT revocation mechanisms with test keys; it is not
  a shipped revocation feature. Kernel module signatures are *not enforced*.
- BIOS unlock automation is **intermittent** and is not marked as passing; UEFI
  is the recommended configuration
- Native VMware/VirtualBox clipboard and drag-drop are only partially verified

## Secure Boot

Aether has a real UEFI Secure Boot chain: firmware verifies a signed shim,
shim verifies signed GRUB, and GRUB chainloads a signed unified kernel image.
The installer enrolls Aether's public PK/KEK/db hierarchy in firmware Setup
Mode, using `efi-updatevar` through `pkexec`, then installs the signed chain.
The live ISO uses the same chain for UEFI; BIOS live media uses normal
kernel/initramfs entries because BIOS has no Secure Boot.

The private keys stay outside the repository and outside every image. The
installed signed UKI embeds a generic initramfs and discovers
`LABEL=AETHER_ROOT`; it can unlock an optional LUKS2 `AETHER_CRYPT` volume and
activate LVM before mounting the root. `/boot` remains unencrypted. Boots are
verified under QEMU/OVMF, VMware Workstation 26.0.1 and VirtualBox 7.2.22;
physical firmware, including physical encrypted-root installs, has not been
certified. The encrypted lab rerun used source-built cryptsetup/LVM, but its
staged runtime still had labelled host-library fallbacks; a release asset
requires a complete source runtime with no fallbacks. Production revocation,
TPM attestation and key custody are not production-grade. A disposable OVMF fixture exercises signed dbx and SBAT
revocation without the release keys. See [Secure Boot details](docs/secure-boot.md)
for enrollment steps, evidence, the lab fixture and limits, and the
[physical UEFI Secure Boot test plan](docs/secure-boot-physical-test-plan.md)
for the real-hardware procedure.

## What is not done

Stated plainly, because a project that hides this is not worth trusting:

- ❌ No **production update repository**. The TUF/signing tooling is built and
  tested, and an automatic checker is installed. Public release trust remains unconfigured.
- ❌ No **ARM64**, i686 or Raspberry Pi desktop image
- ❌ No in-app Pilot confirmation pane; confirmed actions run through
  `aether-pilot` and Aether Settings, and Beam's only queue view is its receipt
- ❌ No production **Secure Boot key custody, rotation or revocation**; the
  Aether db key is a build-host key, not an HSM-backed release root. A
  disposable OVMF lab fixture exercises signed dbx and SBAT revocation with
  test keys, but it is not a production revocation process.
- ❌ No **TPM** enrollment or attestation
- ❌ **Most desktop apps are still unconfined** by AppArmor
- ❌ Installer is **whole-disk only** — it does not convert an existing install
- ❌ `/boot` is **not encrypted**; hibernation is disabled
- ❌ Backup credentials are root-readable local files, so root compromise
  exposes them
- Firmware controls are included through fwupd, but physical flashing and
  microcode coverage are not verified; a maintained browser remains outstanding.
- ❌ SSH is **not installed** by this build
- ❌ No accessibility, FIDO, biometric or multi-user lock-boundary testing

## Documentation

Start at the **[Aether documentation hub](docs/README.md)** for setup, features,
security, updates and developer guides.

- [Getting started](docs/getting-started.md)
- [Screenshot gallery](docs/screenshots.md)
- [Current features and verification](docs/modern-desktop-20261006.md)
- [VMware and VirtualBox](docs/guest-integration-status.md)
- [Building Aether](docs/build.md)
- [Update and recovery documentation](src/updates/README.md)

## Repository layout

```
docs/           architecture, build, verification, roadmap
media/          screenshots and videos (all recorded from a real Aether VM)
src/desktop/    Vector, greeter, installer, Plasma shell + power menu
src/server/     server edition: role catalog, installer, install backend
src/nimbrel/    on-device AI client, gateway, engine wiring
src/beam/       concurrent application installation
src/pilot/      confirmed, logged system actions for the assistant
src/security/   firewall, AppArmor, PAM, backups, security tooling
src/updates/    GnuPG signing + TUF repository and client
src/assets/     wallpapers, colour schemes, screensavers, Plymouth, layouts
```

## Source code

See the [0.3.0 release assets](https://github.com/Shadowman8080/Aether/releases/tag/0.3.0) for the **Corresponding Source**:

- `aether-0.3-corresponding-source.tar.gz` — the complete, verifiable source
  (build system, configs, overlays, all Aether-authored patches) plus an
  upstream component manifest. This is intended to satisfy GPL-3.0 section 6.
- `aether-0.3-upstream-sources.00.tar.part` and `.01.tar.part` — the full set of
  unmodified upstream source archives (3.0 GB total), with
  `RECONSTRUCT.sh` to reassemble them. Required for recipients who cannot
  reliably obtain every upstream archive from its original location.

The smaller `aether-0.3-desktop-sources.tar.gz` and `aether-nimbrel-sources.tar.gz`
remain available for reference, but **do not** by themselves constitute the
complete Corresponding Source. The repository's `src/` directory contains
Aether's own application code. It does not include the 6 GB of upstream build
inputs; those are distributed only via the release assets above.

> **Licensing note.** Aether's own code and assets are **GPL-3.0-or-later**.
> The Linux kernel and some other base components are **GPL-2.0-only**, which is
> *not* compatible with GPL-3.0. Those components keep their own licences, and
> the distribution as a whole ships under the corresponding per-component terms.
> See [`docs/licensing.md`](docs/licensing.md).

## Contributing

Aether is early and the build system is opinionated. Read
[`CONTRIBUTING.md`](CONTRIBUTING.md) first — it explains what will and will not
be accepted, and the security rules are not optional.

## Automated checks

[Source regression CI](https://github.com/Shadowman8080/Aether/actions/workflows/regressions.yml)
runs package-signature, metadata, privacy and other focused regression tests.
A separate manually dispatched image workflow checks BIOS and UEFI boot against
a reviewed ISO digest. These checks do not certify physical hardware or replace
installer, recovery and guest-integration testing for each release.


---

*Aether Linux 0.3 · development snapshot · not a release · not certified.*
