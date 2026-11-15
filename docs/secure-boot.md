# Secure Boot

Aether 0.3 has a real UEFI Secure Boot chain, not a UI warning or an unsigned
boot loader described as signed. The chain is:

```
firmware db
  └─ shim 15.8                      signed with Aether's db key
       └─ grubx64.efi 2.14          signed with Aether's db key
            └─ aether-live.efi      signed live UKI (UEFI live media)
            └─ aether.efi           signed installed UKI
```

Firmware verifies shim; shim verifies GRUB; GRUB chainloads the signed UKI and
firmware verifies it. GRUB is a small standalone EFI image with only the modules
it needs (`chain`, `search`, `part_gpt`, FAT/ext filesystems, `memdisk`, normal
mode). The installed UKI embeds a generic initramfs and uses
`root=LABEL=AETHER_ROOT`; when the root is encrypted it also uses
`aether.luks=LABEL=AETHER_CRYPT`. The installer assigns the disk layout and
filesystem labels, so the same signed UKI works for every install.

## Enrolling the Aether key

The Aether platform key hierarchy is a self-signed PK, a KEK that authorizes db
updates, and a db code-signing certificate. The public files ship in
`/usr/share/aether/secureboot`; the private keys do not ship and are kept
outside the repository.

1. In firmware setup, clear the existing Secure Boot keys so firmware is in
   **Setup Mode**. This is destructive to the firmware's current trust
   hierarchy; a machine that needs its vendor keys should not be repurposed
   this way without a backup plan.
2. Boot the Aether live ISO. On UEFI the live ISO is itself signed by Aether, so
   it can be booted with Secure Boot already enabled once the key is enrolled.
3. In the installer's disk page, choose **Enroll Aether Secure Boot key**. The
   installer runs `/usr/libexec/aether-secureboot-enroll` through `pkexec`.
   `efi-updatevar` writes the authenticated `PK`, `KEK` and `db` updates.
4. Reboot the computer and turn Secure Boot back on if firmware turned it off.
5. Start the installer again. The disk page should report that Secure Boot is
   enabled and Aether's signed chain is enrolled; installation then copies the
   signed boot chain.

Enrollment only works in Setup Mode. On firmware with an existing PK, the
installer refuses to install while Secure Boot is on unless Aether's db
certificate is already present. The helper does not clear firmware keys, does
not disable Secure Boot, and does not touch NVRAM boot entries.

## What is installed

On a UEFI install the backend writes:

```
ESP (vfat, label AETHER_EFI)
  EFI/BOOT/BOOTX64.EFI        signed shim
  EFI/BOOT/grubx64.efi        signed standalone GRUB
  EFI/aether/aether.efi       signed installed UKI
  boot/grub/grub.cfg          chainloader /EFI/aether/aether.efi
```

It intentionally does not run `grub-install --target=x86_64-efi`; the signed
standalone GRUB is copied directly. The root filesystem also gets a fallback
`/boot/grub/grub.cfg` that chainloads the same UKI if GRUB falls back to the
root filesystem instead of the ESP. BIOS installs keep the separate i386-pc GRUB
path and are not part of Secure Boot.

## Live media

UEFI live media contains a signed live UKI with the live initramfs and
`rdinit=/init`. GRUB chainloads it, so Secure Boot works before installation.
BIOS live media has no Secure Boot layer and uses the normal kernel/initramfs
entries. The ISO carries the same signed shim and GRUB in its EFI El Torito
image and at its root for USB writing.

## Verification evidence

These checks cover QEMU/OVMF 4 MiB secure-boot firmware, VMware Workstation
26.0.1 and VirtualBox 7.2.22, each with Secure Boot enabled and Aether's db
certificate present:

- `sbverify --cert db.crt` passed for shim, GRUB, the installed UKI and the live
  UKI.
- Under QEMU/OVMF, the signed live ISO booted with Secure Boot enabled to the
  LightDM live session and `AETHER_LIVE_AUTOLOGIN`/`AETHER_LIGHTDM_START`.
- The backend's UEFI test (`AETHER_TEST_UEFI=1`) passed `INSTALLER_UEFI_PASS`
  with SecureBoot=1 and Aether's db certificate present, then `sbverify`
  verified all three installed files.
- Under QEMU/OVMF, the backend-installed disk booted with Secure Boot enabled
  through shim, signed GRUB and the signed installed UKI to `aether login:`.
- Under VMware Workstation 26.0.1, with `firmware = "efi"`,
  `uefi.secureBoot.enabled = "TRUE"` and the Aether db appended, both the
  signed ISO and the installed disk booted through the signed chain. The live
  ISO reached `AETHER_LIVE_AUTOLOGIN`/`AETHER_LIGHTDM_START`; the installed
  disk reported `not a live system`, started LightDM and reached
  `aether login:`.
- Under VirtualBox 7.2.22, with EFI firmware and an NVRAM initialized with
  `enrollorclpk`, `enrollmssignatures`, Aether's `db.esl` and
  `secureboot --enable`, both the signed ISO and the installed disk booted to
  the same live and installed markers.
- Hypervisor logs recorded Secure Boot active: VMware reported
  `SECUREBOOT: Image APPROVED`; VirtualBox reported `Secure Boot: Enabled` and
  `SecureBootEnable=01` for both VMs.
- The same final ISO also booted under legacy BIOS to the live session.

One initial VMware installed-disk run booted the signed UKI but panicked with
`EXT4-fs (sda3): Could not load journal inode` and `VFS: Unable to mount root
fs on PARTUUID=...`. That VMDK had been converted from a truncated
`streamOptimized` intermediate; the partition table was intact but the root
filesystem was not. Rebuilding the writable VMDK directly from the backend raw
disk and checking the root with `e2fsck -fn` produced the passing run above.
This was an artifact-conversion failure, not a firmware rejection.

The hypervisor tests enrolled keys directly in each VM's NVRAM. The installer's
`pkexec` **Enroll Aether Secure Boot key** GUI action was not exercised in these
runs. Physical hardware, firmware other than OVMF/VMware/VirtualBox, and
production key revocation have not been tested. The
[physical UEFI Secure Boot test plan](secure-boot-physical-test-plan.md) defines
the required enrollment, live-boot, install, revocation and recovery checks,
including which revocation checks are firmware/lab-only. For a field run, use
the [printable checklist](secure-boot-physical-checklist.html) and
[JSON evidence template](secure-boot-evidence-template.json). A separate
disposable OVMF fixture now executes the signed dbx and SBAT revocation
mechanisms; see [Lab revocation fixture](#lab-revocation-fixture).

## Lab revocation fixture

`build/desktop/scripts/test-secureboot-revocation.py` is an executable OVMF
fixture, not a shipped Aether feature. It generates a fresh disposable PK, KEK
and db for every run, builds a test shim whose embedded vendor certificate is
the fixed disposable CA at `/opt/aether/secureboot/test-ca`, and never reads
the Aether release keys. It leaves NVRAM images, signed artifacts, console logs, `result.json` and
`SHA256SUMS` in a new temporary directory.

Run it on the Linux build host:

```sh
python3 build/desktop/scripts/test-secureboot-revocation.py
python3 build/desktop/scripts/test-secureboot-revocation.py --only dbx
python3 build/desktop/scripts/test-secureboot-revocation.py --only sbat
```

The fixture requires QEMU, OVMF 4 MiB Secure Boot firmware, mtools, sbsign,
objcopy, efitools, virt-fw-vars and pexpect. It builds the test shim from
`/opt/aether/secureboot/src/shim` and uses the test CA at
`/opt/aether/secureboot/test-ca` by default; `--shim-source` and `--test-ca`
select other locations. A passing run prints
`SECUREBOOT_REVOCATION_FIXTURE_PASS`.

The observed checks are:

- **Signed dbx:** a test GRUB image signed by the disposable db boots first; a
dbx ESL containing that certificate, signed by the disposable KEK, is applied
to a copy of NVRAM; the same image then fails with `Access Denied`. A test
image signed by a different key is also rejected. Restoring the baseline NVRAM
image restores the accepted boot.
- **Signed SBAT:** a test shim advertising `shim,5` verifies a signed
`revocations.efi` carrying `.sbata`/`.sbatl`, applies `shim,5`, and the next
boot of the same test shim rebuilt as `shim,4` fails with
`SBAT self-check failed: Security Policy Violation`. A `revocations.efi`
signed by the wrong key is rejected and leaves `shim,4` bootable.

This fixture is deliberately narrower than a production revocation process:

- It applies the signed dbx update with `virt-fw-vars`, an offline NVRAM
  builder. That proves the update contents and their effect, but does not test
  a firmware's authenticated `SetVariable` update policy. The physical test
  plan's `efi-updatevar` procedure covers that separate question.
- The test shim uses a fixed disposable test CA, not an Aether release key or
  a per-user generated CA. The generated PK/KEK/db are disposable.
- It exercises only OVMF, the test chain and temporary media. It makes no
  claim about physical firmware, the Aether installer, production key custody
  or a production SBAT update.

## Key custody and rebuilding

Private PK/KEK/db material is kept in `/opt/aether/secureboot/keys` on the build
host, outside the repository and outside every image. Only the public
certificate, `.esl` lists, `.auth` updates and signed binaries are committed.
The build host's key directory is not a production HSM and has no independent
custody, rotation or revocation process yet.

The installed UKI requires a matching `/boot/initramfs-<release>.img`. Build it
with `aether-mkinitramfs` in the target root first; the builder refuses to
produce a kernel-only signed image. The initramfs contains the LUKS/LVM tools
and the dm-crypt, dm-mod and ESSIV modules, so it can discover the root label,
unlock the LUKS label, activate LVM, and switch to the installed root. The
OVMF lab fixture was rerun with cryptsetup 2.8.7 and LVM 2.03.42 compiled from
the pinned source archives. That lab runtime still copied labelled host-library
fallbacks for a few dependencies; `install-security-runtime.sh` refuses host
fallbacks unless a lab override is explicit, and writes a provenance marker
that `build-secureboot-assets.sh` checks. A release asset requires a complete
source-built runtime with `host_library_fallbacks=no`.

To rebuild the signed asset bundle, provide the existing signed shim and GRUB
plus the db key/certificate:

```sh
AETHER_SB_KEYDIR=/path/to/keys \
AETHER_SB_SIGNED_DIR=/path/to/signed/shim-and-grub \
build/desktop/scripts/build-secureboot-assets.sh
```

The root must contain a `/usr/share/aether/security-runtime/source-built`
marker produced by `install-security-runtime.sh`; the builder rejects a missing
marker or one with host-library fallbacks. `AETHER_ALLOW_LAB_CRYPTO=1` is only
for a disposable lab asset. Install the runtime from a completed security root
before the desktop boot/asset stage:

```sh
AETHER_SECURITY_ROOT=/opt/aether/security-system \
build/desktop/scripts/install-security-runtime.sh /opt/aether/desktop-system
AETHER_REQUIRE_ENCRYPTED_BOOT=1 \
build/desktop/scripts/finish-desktop.sh
```

The security-edition package stage (`build/security/build-security-packages.py`)
now builds both the device-mapper libraries and the LVM2 command-line tools.
The encrypted backend/boot fixture can be rerun without the GUI:

```sh
AETHER_TEST_ROOT=/path/to/live/root AETHER_TEST_UEFI=1 \
AETHER_TEST_ENCRYPT=1 build/desktop/scripts/test-installer-backend.sh
python3 build/desktop/scripts/test-encrypted-boot.py --passphrase storage
python3 build/desktop/scripts/test-encrypted-boot.py --passphrase recovery
```

The fixture creates a disposable OVMF variable store from the public `db.crt`
and does not use a private key. It reads generated credentials from the
root-only file written by the backend test.

`build/desktop/scripts/build-desktop-iso.sh` builds the signed live UKI, signed
EFI El Torito image and the complete ISO. It requires `ukify`, `mtools`,
`xorriso`, `sbsign`/`sbverify` and the private db key; it fails rather than
silently producing an unsigned Secure Boot image.

## Installed initramfs and encrypted roots

The graphical installer creates a BIOS-boot partition, an EFI system partition,
a separate unencrypted `/boot`, and a data partition. The data partition is a
LUKS2 container formatted with `aes-cbc-essiv:sha256` (the desktop kernel has
AES, CBC and SHA-256 built in, while XTS is not enabled). It can contain the
ext4 root directly or an LVM physical volume with the `aether/root` logical
volume. A separate recovery passphrase is added to a second LUKS keyslot; both the normal and recovery passphrases unlocked the OVMF fixture.

Because the db private key is not present on live media, the installed UKI is
not re-signed per install. It is a fixed, signed UKI whose initramfs resolves
the `AETHER_ROOT` filesystem label after unlocking the optional `AETHER_CRYPT`
LUKS label and activating LVM. The login passphrase is not embedded in the
image; it is entered at boot.

An OVMF Secure Boot lab fixture installed a 20 GiB disk through the real backend
with encryption and LVM enabled. OVMF verified shim, GRUB and the installed UKI,
the initramfs reported `AETHER_ENCRYPTED_ROOT_MOUNTED` and
`AETHER_INITRAMFS_SWITCHING_TO_ROOT`, and the installed system reached
`aether login:` on the serial console. This is virtual-machine evidence only;
physical encrypted installs have not yet been certified.

## Limits

- `/boot` is not encrypted.
- There is no TPM enrollment, measured boot or attestation.
- Production key revocation and SBAT updates are not implemented or shipped.
  The disposable OVMF lab fixture above executes both mechanisms; it does not
  make them production features or certify physical firmware.
- The fixture's dbx update is applied offline through `virt-fw-vars`; firmware
  authenticated-update enforcement is not exercised by that fixture.
- Secure Boot proves the boot chain was signed; it does not make an unaudited
  development snapshot suitable for sensitive data.
