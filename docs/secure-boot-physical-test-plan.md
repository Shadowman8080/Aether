# Physical UEFI Secure Boot test plan

**Status:** test plan only. No physical UEFI result is claimed by this document.
The current evidence is QEMU/OVMF, VMware Workstation and VirtualBox; see
[Secure Boot](secure-boot.md) and [Verification](verification.md).

**Tester materials:** [printable checklist](secure-boot-physical-checklist.html)
· [JSON evidence template](secure-boot-evidence-template.json)

This plan tests the signed Aether Secure Boot chain on real x86_64 UEFI
firmware:

1. firmware key state and negative controls;
2. Aether key enrollment through the installer;
3. signed live-media boot with Secure Boot enabled;
4. installation and boot of the installed signed chain;
5. revocation of the Aether db certificate and recovery.

It is written for a disposable test machine. It is not a production key
custody, rotation or revocation procedure.

## What is supported today

The shipped `aether-secureboot-enroll` helper writes the authenticated
`PK`, `KEK` and `db` variables from
`/usr/share/aether/secureboot`. The installer calls it through `pkexec` when
firmware reports **Setup Mode**. The signed live and installed media use:

```
shimx64.efi -> grubx64.efi -> aether-live.efi or aether-installed.efi
```

The following are **not** implemented in this build and must not be reported
as passing Aether features:

- no Aether `dbx` update command or signed `dbx.auth` release artifact;
- no SBAT revocation update;
- no production key rotation or independent key custody;
- no TPM measured boot or attestation.

Physical revocation checks therefore test firmware enforcement and a
laboratory key hierarchy, not an Aether revocation feature. Record those
distinctions in every result.

The repository also has a disposable OVMF lab fixture,
`build/desktop/scripts/test-secureboot-revocation.py`, which executes signed
dbx and SBAT revocation with test keys. It is not a shipped update, does not
replace the physical `efi-updatevar` check below, and must not be applied to a
production machine. See [Secure Boot](secure-boot.md#lab-revocation-fixture).

The encrypted backend/boot fixture
(`test-installer-backend.sh` plus `test-encrypted-boot.py`) exercises the real
installer and both LUKS passphrases under OVMF. It uses only the public
db certificate to build a disposable firmware variable store; it is lab
evidence, not a substitute for this physical plan.

## Safety and prerequisites

### Hardware

Use a machine that can be erased and recovered:

- x86_64 UEFI firmware with CSM disabled and Secure Boot capable;
- firmware that exposes **Setup Mode**, custom key management and, ideally, a
  **dbx** or forbidden-signature database;
- at least 16 GiB of install disk (the installer refuses smaller disks);
- at least 6 GiB RAM, a wired keyboard and a display;
- a second machine or a known vendor firmware-recovery method;
- no production disks, no dual-boot operating system and no device encryption
  that depends on Secure Boot or the TPM.

At least one test system must allow clearing the platform key and entering
Setup Mode. A second system from a different firmware vendor is recommended;
results apply only to the firmware models actually tested.

### Firmware and data precautions

Clearing Secure Boot keys is destructive to the existing trust hierarchy.
Before starting:

- back up all data and record the vendor, model and firmware version;
- disable BitLocker, LUKS, TPM-bound unlocking or similar protection, and keep
  the recovery key available;
- disable CSM/legacy boot and Fast Boot, and enable UEFI boot;
- record whether the firmware can restore vendor keys;
- remove or disconnect every disk that is not the disposable test target;
- do not use release signing keys or the build host's private keys on the
  test machine. Use a disposable test hierarchy for signed update tests.

If the firmware has no way to restore vendor keys and the machine is not
disposable, stop. Do not clear the keys.

### Image and media

Use the exact release ISO and verify it before writing:

```sh
sha256sum aether-0.3-x86_64-desktop.iso
# Expected for the tested signed image:
# f8eabb694fe5089c7863d70ebb0c1d8502e8e495c38804c37e0a76ff8cbd5805
```

Write the whole USB device, not a partition:

```sh
lsblk
sudo dd if=aether-0.3-x86_64-desktop.iso of=/dev/sdX bs=4M \
  status=progress conv=fsync
sync
```

Keep a second copy of the ISO and a trusted host copy of the public `db.crt`,
`db.der` and the public `PK.auth`, `KEK.auth` and `db.auth`. These are public
assets; never put `PK.key`, `KEK.key` or `db.key` on the test media.

Useful public assets are under
`/usr/share/aether/secureboot` on the live image and
`build/desktop/assets/usr/share/aether/secureboot` in the source tree.

## Test matrix

| ID | Test | Secure Boot state | Expected result |
|---|---|---|---|
| FW-01 | Firmware baseline and Setup Mode | Off/Setup Mode | State recorded and reversible |
| FW-02 | Unsigned EFI binary rejected | On | Firmware refuses to execute it |
| ENROLL-01 | Enrollment status before enrollment | Off/Setup Mode | `setup_mode=true`, `can_enroll=true` |
| ENROLL-02 | Installer GUI enrollment | Off/Setup Mode | `AETHER_SECUREBOOT_ENROLLED`; Aether cert in db |
| ENROLL-03 | Enrollment on a non-Setup-Mode machine | Off (vendor keys) | Helper refuses; no key change |
| LIVE-01 | Signed live ISO boot | On | Live LightDM session, no firmware violation |
| LIVE-02 | Missing Aether db | On | Aether live media rejected |
| INSTALL-01 | Signed install | On | Installer reports enabled/enrolled chain |
| INSTALL-02 | Installed boot | On | `aether login:` and desktop; signed ESP files |
| INSTALL-03 | Repeat installed boot | On | Same result after reboot |
| REVOKE-01 | Add Aether db to firmware dbx | On | Live and installed media rejected |
| REVOKE-02 | Unsigned dbx update | On | Update refused; dbx unchanged |
| REVOKE-03 | Signed dbx update (lab only) | On | Update accepted; test image rejected |
| REVOKE-04 | Recovery and re-enrollment | On | Known-good Aether boot restored |
| SBAT-01 | SBAT revocation | On | **Unsupported for shipped Aether media**; the disposable OVMF lab fixture covers the mechanism separately |

`PASS`, `FAIL`, `BLOCKED` and `UNSUPPORTED` are distinct. A test that was not
run is not a pass.

## Procedure

### 1. Record the firmware baseline

1. Enter firmware setup. Disable CSM/legacy support, enable UEFI, disable Fast
   Boot and enable Secure Boot if the firmware offers it.
2. Record the Secure Boot mode, current key state and firmware version. Take a
   photograph of each relevant screen.
3. Boot a known unsigned EFI test binary from a separate FAT32 USB. It must be
   rejected by firmware. A typical test is an unsigned
   `systemd-bootx64.efi` placed at `EFI/BOOT/BOOTX64.EFI`; verify it is not
   already signed by a trusted key before relying on it. Record the exact
   firmware message (for example "Security Violation" or "Access Denied").
4. If the unsigned binary boots, **stop**. Secure Boot is not enforcing
   signatures; do not continue with the Aether tests.
5. With the vendor keys still in place and Secure Boot enabled, try the Aether
   live USB. It must be rejected because Aether's key is not enrolled, unless
   the vendor db already includes Aether's certificate; record which case
   applies. Do not clear the keys before this check.

### 2. Enter Setup Mode and enroll Aether

1. In firmware key management, clear/delete all Secure Boot keys. Confirm the
   machine is in **Setup Mode**; Secure Boot will usually be off.
2. Boot the Aether ISO in UEFI mode with Secure Boot off. Confirm it is the
   signed ISO with the hash above.
3. Open a terminal in the live session and inspect the helper state:

   ```sh
   pkexec /usr/libexec/aether-secureboot-enroll --status
   ```

   Expected before enrollment: `available=true`, `setup_mode=true`,
   `secure_boot=false`, `aether_key_enrolled=false`, `can_enroll=true`.

4. Open the installer and go to the disk page. The **Secure Boot key
   enrollment** card should be visible. Click **Enroll Aether Secure Boot
   key**, authenticate with `pkexec`, and record the dialog text.
5. Expected result: the helper prints `AETHER_SECUREBOOT_ENROLLED`, the dialog
   says the key was enrolled and asks for a reboot, and a second `--status`
   reports `aether_key_enrolled=true`.
6. Test the refusal path on a machine with an existing PK and Secure Boot
   **disabled**, so the Aether live media can boot without Aether's db. Run the
   helper. It must refuse with "Firmware is not in Setup Mode" and must not
   modify `PK`, `KEK` or `db`. Record the exact message. Do not use the machine
   whose keys were just cleared for this test.
7. Reboot into firmware setup. Enable Secure Boot. Verify `SetupMode=0` and
   `SecureBoot=1`; photograph the key screens.

Do not install yet. The signed live boot must be tested first.

### 3. Boot the signed live ISO with Secure Boot on

1. Boot the same USB in UEFI mode with Secure Boot enabled.
2. Confirm the Aether live session starts and reaches the graphical live
   desktop. Record `AETHER_LIVE_AUTOLOGIN` and `AETHER_LIGHTDM_START` if a
   serial console is available; otherwise photograph the desktop.
3. In a live terminal, verify the firmware and enrollment state:

   ```sh
   pkexec /usr/libexec/aether-secureboot-enroll --status
   ```

   Expected: `secure_boot=true`, `setup_mode=false`,
   `aether_key_enrolled=true`, `can_enroll=false`.

4. Record the kernel's Secure Boot and lockdown messages:

   ```sh
   sudo journalctl -b -k | grep -iE 'secure boot|lockdown|efi'
   sudo dmesg | grep -iE 'secure boot|lockdown'
   ```

5. Optional negative control: use a second USB with the Aether db removed or a
   deliberately modified signed UKI. Firmware must reject it before Aether
   starts. Do not modify the only release USB.
6. Record the result. If the live session starts only with Secure Boot off,
   the test fails even if the desktop itself works.

### 4. Install to the disposable disk

1. From the signed live session, open the installer.
2. Select the disposable target disk. Confirm the installer reports
   **Secure Boot is enabled and Aether's signed boot chain is enrolled** or the
   equivalent `Enabled (Aether signed chain)` status.
3. For the required baseline, leave LUKS/encryption **off**. The signed path
   also supports LUKS2 and optional LVM; encrypted boot is currently verified
   only under OVMF and is not part of this physical required-test count.
4. Confirm the erase action, install, and wait for completion. Record the
   completion message and any errors.
5. Shut down, remove the USB, and boot the installed disk in UEFI mode with
   Secure Boot still enabled.

### 5. Verify the installed signed chain

1. Sign in at `aether login:`. Complete the mandatory first-boot password
   change if prompted, then reach the Plasma desktop.
2. Verify firmware state from the installed system:

   ```sh
   pkexec /usr/libexec/aether-secureboot-enroll --status
   efibootmgr -v
   ```

   Expected: `secure_boot=true`, `aether_key_enrolled=true`; the Aether boot
   entry points to the signed ESP loader.
3. Inspect the installed files. On the installed system:

   ```sh
   sudo findmnt /boot/efi
   sudo ls -l /boot/efi/EFI/BOOT /boot/efi/EFI/aether
   ```

   Expected files include `BOOTX64.EFI`, `grubx64.efi`, `aether.efi` and the
   chainloader configuration. Record their SHA-256 hashes.
4. Verify signatures with `sbverify` from a trusted host or the live media.
   Mount the ESP read-only at `/mnt/esp` on the trusted host first:

   ```sh
   sbverify --cert db.crt /mnt/esp/EFI/BOOT/BOOTX64.EFI
   sbverify --cert db.crt /mnt/esp/EFI/BOOT/grubx64.efi
   sbverify --cert db.crt /mnt/esp/EFI/aether/aether.efi
   ```

   All three must pass. If `sbverify` is unavailable in the installed image,
   perform this from the build host and record the tool version.
5. Reboot a second time with Secure Boot enabled and confirm the installed
   system still reaches the login prompt. This checks that the result is not a
   one-time boot.

### 6. Revocation checks

Revocation is a destructive test. Complete the install and recovery steps
first, and keep the vendor firmware recovery path available.

#### 6A. Firmware dbx enrollment (physical test)

This tests whether firmware really rejects Aether after its certificate is
revoked. It requires a firmware UI that can append a certificate to the
forbidden signature database (`dbx`).

1. Convert the public certificate to DER on a trusted host:

   ```sh
   openssl x509 -in db.crt -outform DER -out aether-db.der
   ```

2. Put `aether-db.der` on a FAT32 USB. In firmware setup, open the Secure Boot
   key management screen and append it to **dbx** / **Forbidden Signature
   Database**. Save and reboot.
3. Attempt to boot both the Aether live USB and the installed disk with Secure
   Boot enabled. Both must be rejected by firmware before shim or GRUB runs.
   Photograph the exact message and record the firmware event log.
4. If either image still boots, **FAIL**: the revocation was not enforced. Stop
   and preserve the logs; do not continue to other revocation variants.
5. Record whether the firmware accepted the certificate, a hash, or an ESL.
   Firmware that cannot enroll a certificate into dbx is **BLOCKED** for this
   variant, not a pass.

#### 6B. Signed dbx update (laboratory only)

This verifies signed update enforcement and key rotation mechanics. It uses a
disposable test PKI, not Aether's release keys, and is not a shipped Aether
feature.

The OVMF fixture in `build/desktop/scripts/test-secureboot-revocation.py`
applies the same kind of signed dbx update offline with `virt-fw-vars` and
verifies that the test image is rejected. That is useful for reproducing the
revocation contents, but it is not a substitute for this section's firmware
`efi-updatevar` test, which exercises the firmware's authenticated-update
policy.

1. Generate a disposable PK/KEK/db hierarchy and enroll it on a test machine or
   disposable VM. Keep the private keys off the test media.
2. Build a dbx ESL containing the test db certificate, then sign the update
   with the test KEK:

   ```sh
   cert-to-efi-sig-list test-db.crt test-db.esl
   sign-efi-sig-list -k test-KEK.key -c test-KEK.crt \
     dbx test-db.esl test-db.auth
   ```

3. Apply the signed update:

   ```sh
   sudo efi-updatevar -f test-db.auth dbx
   ```

   Reboot and confirm the test image signed by that certificate is rejected.
4. Negative control: attempt the same update with an unsigned file or a file
   signed by the wrong KEK. Firmware must refuse it and leave `dbx` unchanged.
5. Rotation check: enroll a new test db certificate, sign a new test image with
   it, and confirm the old image is rejected while the new one boots. This tests
   firmware mechanics only; Aether has no production rotation procedure.

#### 6C. SBAT revocation

The shipped Aether media currently have no signed SBAT update artifact, so this
physical test remains **UNSUPPORTED** for those media. Do not mark it passed
because the shim boots, and do not apply an unsigned SBAT update to the test
machine.

- Record the SBAT metadata if a suitable tool is available:

  ```sh
  objcopy --dump-section .sbat=shim.sbat shimx64.efi
  strings shim.sbat
  ```

- The disposable OVMF lab fixture
  `build/desktop/scripts/test-secureboot-revocation.py` executes the signed
  mechanism with a test CA and two shim generations. It demonstrates that a
  signed `revocations.efi` can apply an `SbatLevel` that rejects `shim,4`, and
  that a wrong-key update is rejected. That result is evidence about shim/SBAT
  behavior only, not a physical-media or Aether-production result.
- A physical SBAT pass would require a separately reviewed, signed SBAT update
  for the Aether chain and a recovery procedure. None exists in this build.

#### 6D. Recovery and re-enrollment

1. After the revocation test, enter firmware setup. Delete the dbx entry if the
   firmware allows it, or clear all Secure Boot keys. Record exactly which
   operation was used.
2. Verify that `dbx` no longer contains Aether's certificate. If clearing keys
   left it in place, use the firmware's factory-key restore or reflash the
   firmware; Aether remains blocked until the revocation entry is gone.
3. If the intended end state is vendor-managed without Aether, restore vendor
   keys now and stop. Do not expect Aether to boot afterwards.
4. For the Aether recovery path, leave the machine in Setup Mode (or clear any
   remaining keys). Restoring vendor keys first would end Setup Mode and make
   Aether enrollment fail. Boot the Aether ISO with Secure Boot off, enroll
   Aether's public `PK.auth`/`KEK.auth`/`db.auth`, enable Secure Boot, and
   confirm both the signed live ISO and the installed disk boot again.
5. Record the recovery result separately from the initial enrollment result.
   Recovery proves the test machine is usable; it does not prove production key
   rotation or custody.

## Evidence to capture

Create one directory per machine and keep evidence immutable:

```text
physical-<vendor>-<model>-<date>/
  README.txt                 machine, firmware, tester, date, ISO hash
  secure-boot-physical-checklist.pdf
                             completed printed checklist
  result.json                structured outcomes
  firmware-before.jpg
  setup-mode.jpg
  unsigned-rejected.jpg
  enroll-status-before.txt
  enroll-gui.jpg
  enroll-status-after.txt
  efivars-secureboot.txt
  enroll-refusal.txt
  live-boot.jpg
  live-journal.txt
  live-missing-db-rejected.jpg
  install-complete.jpg
  installed-boot.jpg
  installed-reboot.jpg
  esp-files.txt
  sbverify.txt
  revocation-dbx.jpg
  revocation-boot-failure.jpg
  dbx-unsigned-refused.txt
  dbx-signed-lab.txt
  sbat-metadata.txt
  recovery-boot.jpg
  recovery-status.txt
  SHA256SUMS
```

Do not include passwords, private keys, TPM secrets or recovery keys. Public
certificates and firmware screenshots are acceptable.

Use the [JSON evidence template](secure-boot-evidence-template.json) as the
structured record. Copy it to `result.json` in the evidence directory, fill
every test, and keep its statuses and evidence links consistent with the
[printable checklist](secure-boot-physical-checklist.html). Do not add private
keys, passwords or recovery keys to the evidence directory.

The template uses `pass`, `fail`, `blocked`, `unsupported` and `not_run`. A test
that was not run is not a pass, and SBAT-01 starts as `unsupported`.

## Pass/fail criteria

A physical firmware model passes this plan only when:

- Setup Mode was reached and the unsigned EFI test binary was rejected;
- the installer enrolled Aether's key and the public certificate is present in
  `db`;
- the signed live ISO boots with Secure Boot enabled;
- the installer reports the signed chain as enabled and completes an install;
- the installed disk boots through the signed chain with Secure Boot enabled,
  and `sbverify` passes for the ESP loader, GRUB and installed UKI;
- after dbx revocation, both live and installed media are rejected by firmware;
- recovery restores a known-good Aether boot.

A failure in any required row blocks a physical Secure Boot claim for that
firmware model. Missing firmware dbx support is recorded as `BLOCKED`, not as a
pass. SBAT revocation is `UNSUPPORTED` for the shipped Aether media; the
separate OVMF lab fixture exercises the mechanism but is not a physical pass.

## Current limitations

- The Aether PK/KEK/db hierarchy is self-signed build-host material, not an
  HSM-backed release root. This plan does not change that.
- Aether has no production revocation, SBAT-update or key-rotation tooling.
  The disposable OVMF fixture exercises the dbx and SBAT mechanisms; physical
  revocation tests still exercise firmware behavior and a laboratory
  hierarchy.
- The installed signed UKI includes a generic initramfs and supports LUKS2
  and optional LVM roots, but encrypted boot has only OVMF lab evidence in
  this plan; it is not a physical-hardware pass.
- There is no TPM enrollment, measured boot or attestation.
- Results apply only to the exact machine, firmware version and ISO hash
  recorded. They do not certify other firmware or all PCs.
- ARM64, i686 and Raspberry Pi are not covered.

## References

- [Secure Boot implementation and current evidence](secure-boot.md)
- [Verification record](verification.md)
- [Installer source](../src/desktop/installer/main.cpp)
- [Enrollment helper](../build/desktop/assets/usr/libexec/aether-secureboot-enroll)
- [Installer backend](../build/desktop/assets/usr/libexec/aether-installer-backend)
- [Secure Boot assets](../build/desktop/assets/usr/share/aether/secureboot/README.md)
