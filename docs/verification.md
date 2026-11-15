# Verification

> Historical 0.3 baseline. See the [0.3.2 development record](modern-desktop-20261006.md)
> for newer features and test results, or return to the [documentation hub](README.md).

This is the honest record of what has actually been tested for Aether 0.3 and
what has not. It is written to be checked against, not to reassure.

**Every result below comes from virtualised or emulated machines. Nothing in
this document certifies physical hardware.**

Test environment: baseline `qemu64` CPU, 6 virtual CPUs, 6 GB RAM, virtual
graphics, VMXNET3 networking, HDA audio. Builds ran on 16 build CPUs.

> `x64` and `x86_64` are the same architecture. Where a document says "x64" it
> means x86-64; there is no separate 32-bit build.

## Completed checks

**Compilation**

- Native Qt, KDE Frameworks, Plasma, desktop applications, printing portal and
  English OCR all compiled successfully.
- Shared-library resolution passed for the desktop shell, both compositors, the
  greeter, search and the core applications.
- GMP, MPFR and MPC were rebuilt for the baseline CPU so they do not emit
  illegal instructions on older processors. Upstream test suites passed,
  including **198 MPFR** and **75 MPC** tests. A `qemu64` CPU probe passed
  calculator and PDF-viewer startup.

**UEFI disk boot (the recommended configuration)**

- Graphical login, rejection of an incorrect password, and **mandatory first-boot
  password change** all passed.
- Plasma Wayland started; DHCP and DNS worked; HTTPS was verified.
- Desktop printing portal initialised; audio output was captured.
- AuraSearch opened on `Super+Space`, computed `2+2=4`, launched Konsole and
  found an indexed local file. Screenshots were reviewed.
- Dolphin, Konsole, Kate, KCalc, Gwenview, Okular and Ark each displayed their
  windows.
- Screen lock and password unlock passed.
- Reboot preserved both the changed password and a test file, and returned to
  the desktop. Shutdown completed normally.

**Other**

- A native Tesseract OCR test recognised a generated English test image.
- System Settings' Quick Settings window and category sidebar were visually
  verified in the final UEFI live ISO after allowing its cold start to finish.
- The final ISO passed a legacy BIOS boot smoke test **to the graphical greeter**
  only; it did not exercise a BIOS live session.
- The released writable `monolithicSparse` VMDK passed `qemu-img compare`
  against the detached release raw image: *Images are identical.*

**Nimbrel (verified on the 0.3 Nimbrel image, this session)**

- `nimbrel-engine.service` and `nimbrel-local.service` both active.
- llama-server served Qwen3.5 0.8B Q4_0 (563,036,064 bytes) on CPU.
- Real completions returned over `/run/nimbrel-engine/engine.sock` at roughly
  6.6 tok/s.
- The desktop client reached the engine end-to-end and produced visible answers.
- Confirmed **no listening TCP port** is opened for AI; the path is Unix
  sockets only.

**Aether Server (off-line checks only — nothing built or booted)**

- `build/server/scripts/test-server-roles.py` runs **23 unit tests** and passes.
  They validate the role catalog schema, confirm every role's config templates
  exist, apply roles to a throwaway root and assert the copied configs, service
  enablements, merged firewall ports and audit report, and check the
  directory-join config writers (krb5, sssd, PAM, nsswitch).
- The catalog is parsed and validated inside the chroot by
  `install-server-assets.sh`; a malformed catalog stops the image build.
- **Not verified:** the Qt server installer was never compiled, no role
  software was ever source-built, no server ISO exists, `adcli` is absent so no
  domain join ran, and no installed server has been booted. Every server claim
  beyond the catalog/backend unit tests is unvalidated.

**Secure Boot (QEMU/OVMF, VMware Workstation, VirtualBox)**

- Built and signed shim 15.8, standalone GRUB 2.14 and live/installed UKIs with
  the Aether db key; `sbverify` passed on each.
- Enrolled PK, KEK and db through `efi-updatevar` in Setup Mode.
- Under QEMU/OVMF, the signed live ISO booted with firmware Secure Boot enabled
  to the live LightDM session (`AETHER_LIVE_AUTOLOGIN`,
  `AETHER_LIGHTDM_START`).
- The backend UEFI test reported `INSTALLER_UEFI_PASS`: the ESP contained the
  signed shim, GRUB, installed UKI and chainloader config, all signature-verified.
- An OVMF encrypted-install fixture used the graphical backend on a fresh
  20 GiB disk with LUKS2 and LVM enabled. Firmware verified shim, GRUB and the
  installed UKI; the embedded initramfs unlocked the LUKS volume, activated the
  `aether/root` LV, reported `AETHER_ENCRYPTED_ROOT_MOUNTED` and
  `AETHER_INITRAMFS_SWITCHING_TO_ROOT`, and the installed system reached
  `aether login:` on the serial console. The independent recovery passphrase
  also unlocked the same disk and reached the login prompt. A later rerun used
  cryptsetup 2.8.7 and LVM 2.03.42 compiled from the pinned source archives;
  the boot again reached `aether login:`. That lab runtime is labelled with
  host-library fallbacks, so it is not a production runtime.
- The unencrypted UEFI backend fixture and a four-partition installed-disk boot
  also passed with the same signed UKI and embedded initramfs, reaching
  `aether login:` without a LUKS prompt.
- The repository encrypted fixture (`test-installer-backend.sh` +
  `test-encrypted-boot.py`) installed an encrypted/LVM disk, verified both LUKS
  keyslots, and booted the installed UKI with both the normal and recovery
  passphrases to `aether login:` under OVMF Secure Boot. The source-runtime
  rerun used cryptsetup 2.8.7 and LVM 2.03.42 from the pinned archives.
- The backend-installed disk booted through the signed chain with Secure Boot
  enabled to `aether login:`.
- VMware Workstation 26.0.1, with Secure Boot enabled and the Aether db appended,
  booted both the signed ISO and the installed disk through the signed chain to
  their live/installed LightDM markers and `aether login:`.
- VirtualBox 7.2.22, with EFI Secure Boot enabled and Aether's db enrolled in
  NVRAM, booted both images to the same markers.
- The same final ISO booted under legacy BIOS to the live session as well.

One initial VMware installed-disk run panicked before root mount
(`EXT4-fs (sda3): Could not load journal inode`); its VMDK had been converted
from a truncated intermediate. Rebuilding the VMDK directly and verifying the
root filesystem produced the passing run above. The hypervisor tests enrolled
keys in NVRAM directly; the installer's GUI enrollment action was not run.

This is virtual-machine evidence only. Physical firmware, firmware other than
OVMF/VMware/VirtualBox, and production revocation/rotation remain untested. The
encrypted OVMF rerun used source-built cryptsetup/LVM with labelled host-library
fallbacks; see
[the encrypted OVMF record](verification/20261113/encrypted-ovmf.json). A
disposable OVMF fixture now exercises signed dbx and SBAT revocation with test
keys, but it is not physical or production evidence.

## Repairs that were needed

These are recorded because they explain why naive instructions will not work:

- The session launcher now handles LightDM's command format.
- The CA bundle path is configured so HTTPS verification succeeds.
- Portable math libraries avoid illegal instructions on older CPUs.
- The PAM password-check helper needed correct ownership and permissions for
  screen unlock to work at all.
- Qt was rebuilt with CUPS support and KDE's printing portal was added.
- AuraSearch gained portal application metadata and a cold-start timeout
  suitable for slower machines.
- Drive controllers were moved to SATA and the VM was moved to hardware
  version 17 for VMware Workstation compatibility.

## Not verified

| Area | Status |
|---|---|
| **Physical hardware** | Not tested at all. Every result is virtualised/emulated. |
| **ARM64 / i686 / Raspberry Pi** | Not built, not updated, not tested. |
| **BIOS unlock automation** | Intermittent — **not** marked as passing. |
| **VMware clipboard / drag-drop** | Only partially verified. |
| **VirtualBox integration** | Boot and Secure Boot validated; clipboard/shared-folder integration outstanding. |
| **Suspend / resume** | Hibernation disabled pending an encrypted-resume design. |
| **HDR / VRR** | Not tested. |
| **Accessibility workflows** | Not tested end to end. |
| **Removable / encrypted media** | Removable media not tested. Encrypted installed root has OVMF lab evidence only. |
| **Plug-and-play devices** | udev device policy, the Aether Devices manager, hotplug notifications, `lspci`/`lsusb` and the extra kernel driver classes are implemented in source but **not compiled or boot-tested**; no physical-hardware claim. |
| **Multi-user lock boundaries** | Not tested. |
| **Aether Server edition** | Catalog/backend unit tests only. No compile, ISO, role software, adcli or booted server. |

## BIOS unlock — the specific known-flaky test

The first BIOS run completed application tests but rejected the scripted unlock
password. A private input probe in a disposable VM found three shifted
characters were incorrect despite the correct input length. The harness now
sends modifier press/release events separately and clears the field explicitly.
The probe was removed and the original PAM configuration restored before normal
password-unlock verification.

One normal-PAM BIOS unlock cycle then passed, but its repeated cycle failed, so
**BIOS unlock automation is not marked as fully passing.** The UEFI disk and
final UEFI ISO full-session passes remain the release evidence.

Earlier failed logs are retained. No diagnostic PAM module and no captured
token are present on the release disk. The disposable overlay's test password
was reset after the focused check; the release disk was unchanged.

## Interpretations and limits

- A successful `qemu-img compare` proves the shipped disk matches the built
  image. It proves nothing about hardware compatibility.
- Compilation success and emulated-VM success do **not** establish that every
  hardware platform works.
- The live ISO has no graphical installer and does not retain changes after
  shutdown.
- The security work is an incomplete implementation of a 192-item checklist. It
  is not a security certification and no compliance claim is made.

## Release artefact checksums

From the 0.3 Nimbrel release:

| Artefact | SHA-256 |
|---|---|
| Nimbrel ISO | `5d4fb3456592048ad4ebbe0c045f902ca9c850dec2eae8a2bd234dc66baf4d1b` |
| Nimbrel VMDK | `1c8185e0882de36993d14ff9e6775086142c68678fee0486900ffc3c04c9eb61` |

## Still outstanding

Release signing ownership and trust enrollment; Secure Boot key custody,
production rotation and revocation; TPM enrollment and attestation; an authenticated production repository with
maintained automatic security updates; firmware/microcode update coverage; broad
MAC and application sandbox coverage; a maintained browser; Flatpak permission
UI; tested multi-user lock/suspend/accessibility boundaries; FIDO, central
identity and biometrics; USB/Thunderbolt enrollment; network-profile and VPN
policies; audited update rollback; protected remote logs; independent immutable
backups; and an independent security assessment.