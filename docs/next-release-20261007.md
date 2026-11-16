# Next release implementation record

This work follows the 0.3.2 development release. Items below are accepted scope,
not claims that they are complete. Existing published images remain unchanged
until new source is compiled, integrated, tested and packaged.

## Acceptance criteria

1. **Production updates:** reconcile installed package ownership; generate a
   component inventory; verify signed metadata and expiry; document key custody
   and rotation. Production trust requires operator-owned keys and reviewed enrollment.
2. **Verified boot:** build and sign unified kernel images; test rejection of
   tampered images and boot approved images. Never enroll keys into the host firmware automatically.
3. **Hardware-backed unlocking:** optional TPM2/PIN or FIDO2 enrollment with a
   tested recovery passphrase. Preserve passphrase access on unsupported hardware.
4. **Application protection:** tested AppArmor profiles and portal permissions,
   including negative-access checks and normal application operations.
5. **Network/device trust:** per-connection public/home policies and optional USB
   enrollment, with fail-safe keyboard/mouse recovery and no silent allow-all fallback.
6. **Backup protection:** independently protected destination, restricted writer
   credentials and restoration tests. Local encrypted backups alone do not meet this criterion.
7. **Browser and passwords:** a maintained browser with verified update delivery,
   password-manager integration and a documented maintenance owner/process.
8. **Recovery assistant:** graphical checkpoint selection, file restoration into
   a new destination and allowlisted diagnostics that exclude secrets and user content.
9. **Laptop/display behavior:** battery profiles and tested docking, scaling,
   lock-on-resume and suspend on actual supported hardware; VM tests are supplemental.
10. **Installer:** partition selection, offline installation and recovery guidance.
    Dual-boot testing must preserve another OS on disposable test disks before user disks are touched.
11. **Nimbrel models:** verified model downloads, storage/selection controls,
    hardware checks and optional acceleration/dictation with explicit downloads.
12. **Release automation:** source regression CI plus disposable-image boot,
    install, update, recovery and guest-integration checks that block publication on failure.

## Work log

- Added a GitHub Actions workflow for existing TUF/signature, privacy/preferences
  and sound regressions. It uses SHA-pinned actions, read-only repository access,
  no deployment secrets and no persistent checkout credentials. [First CI run passed](https://github.com/Shadowman8080/Aether/actions/runs/37590220231).
- Ubuntu is connected again with 16 CPUs. Verified temporary personal images were retired from the build host; Windows backups and published downloads are preserved.
- Added a read-only critical-runtime ownership inventory and seven passing path-boundary tests. The audit reports 435 package records, 1,216 critical runtime files without ownership and ten ownership conflicts; generated boot files are among the unowned entries.
- Found systemd built without TPM2, FIDO2, cryptsetup, seccomp and AppArmor integration; these are prerequisites for several requested protections.
- No production signing keys, enrollment or public update-feed activation performed.

Source CI is not an image-boot test and does not certify real hardware. Each
item needs an explicit result before it can be marked complete. New release
assets must match their source revision and verification checksums.

- FIDO2, CBOR and TPM2 libraries built natively. Rebuilt systemd reports AppArmor,
  seccomp, FIDO2, TPM2 and cryptsetup/plugin support enabled; candidate boot testing remains pending.
- Added Home/Public connection policy source and eight passing firewall rule tests.
  GUI, dispatcher and live transition validation remain pending.
- Added a digest-checked BIOS/UEFI image workflow. Both hosted boot tests passed
  for the existing 0.3.2 ISO: [boot evidence](https://github.com/Shadowman8080/Aether/actions/runs/37592223484).
- Compiled the updated Settings interface with graphical checkpoint selection
  and diagnostic export. Inspected its offscreen recovery-page capture; full desktop interaction testing remains pending.
- Six diagnostic tests pass, including private output permissions, refusal to
  overwrite files or follow output symlinks, and exclusion of extra service fields.
- Live disposable-network tests pass for Home access, Public rejection of new
  connections, termination of Home-dependent inbound traffic on trust removal,
  and preservation of explicitly configured global ports. The build host's
  networking and firewall were not changed.
- [Expanded hosted source checks passed](https://github.com/Shadowman8080/Aether/actions/runs/37593208566),
  including diagnostic privacy and live firewall transition tests.
- Rebuilt systemd and its native security dependencies now install into a
  separate candidate root. The initial overlay/package attempt failed: the
  hardware database belonged to `hwdata`, and overlay rollback hit stale inode
  handles. The corrected build preserves `hwdata` ownership and uses a standalone
  candidate filesystem. The current VM disk and published images were not changed.
- A disposable-key Secure Boot fixture passed under OVMF: the signed Aether
  kernel and native systemd EFI stub booted with Secure Boot, integrity lockdown
  and module-signature enforcement enabled. A modified UKI failed both signature
  verification and firmware boot. This probe uses a minimal test initramfs;
  it does not certify the desktop, production key custody or hardware enrollment.
- Initial desktop candidate boots reached graphical login, but failed the
  on-demand AI assertion. Replacing systemd removed the empty machine-ID
  template, which triggered first-boot presets and enabled Nimbrel directly.
  Added an explicit desktop service allowlist with optional services disabled
  by default, plus a real `systemctl --root` regression covering AI and console
  instance enablement. The corrected image passed BIOS and UEFI integration tests.
- Candidate ISO SHA-256: `0b9025f0195b5f5dd05eb912d1bfd7f1632b8e727dbc1b94d05090068ba6eaed`.
  [Recorded checks](verification/20261007/) cover graphical-login service startup,
  idle/on-demand AI, a real UEFI-guest AI answer, firewall/dispatcher activation,
  diagnostic export, sandboxing and no failed services. A separate native-CPU
  inference test passed in 104.47 seconds. This is not a performance guarantee.
- All 210 newly built ELF executables/libraries resolve dependencies in their
  documented loader context. The initial test harness incorrectly assumed
  systemd was on PATH; the final run uses Aether's actual installed path.
- This remains an internal candidate. No new VMDK or public release has been
  published, and the remaining acceptance criteria above are still outstanding.
- Built USBGuard 1.1.4 and its native dependencies with all available build CPUs.
  Four upstream test suites and eleven Aether trial/recovery tests pass.
  Added an opt-in Settings page and [recovery instructions](usb-protection.md).
- A disposable Aether guest passed USB policy tests: default-off state, automatic
  rollback, trusted-keyboard access, unknown-mouse blocking, explicit device
  approval, and disabling protection for the next manual reboot.
  [Guest checks](verification/20261007/usb-guest-checks.json) record the results.
  The first run exposed systemd's default timer tolerance; setting one-second
  timer accuracy fixed the rollback deadline. Physical USB hardware and
  interrupted-trial reboot behavior still require integration testing.
- Installed the tested USB packages into the separate candidate root, leaving
  USBGuard disabled. All 315 staged ELF files passed dependency resolution;
  the Settings page compiled and its offscreen layout was inspected.
  [Hosted source checks passed](https://github.com/Shadowman8080/Aether/actions/runs/37600668388)
  with the USB regression suite included.
- The candidate's restic 0.19.1 passed a disposable encrypted-repository test:
  restore contents, private-file permissions and symlinks, then reject deliberately
  corrupted encrypted data. [Backup engine evidence](verification/20261007/backup-roundtrip.json)
  does not imply an independently protected destination has been configured.
  Added the same round-trip test to hosted CI with Ubuntu's packaged restic.
- The first hosted backup test could not deliberately alter restic's read-only
  test pack as an unprivileged user. The fixture now changes only that disposable
  file's permissions before corruption. [The corrected source run passed](https://github.com/Shadowman8080/Aether/actions/runs/37601479072).
- Rebuilt the integrated USB candidate ISO using 16 build CPUs. SHA-256:
  `1a505811a06d7b2c1d077637b74743e98651498a9c6c1ff2ca002ff3db1d6fd9`.
  [BIOS checks](verification/20261007/usb-iso-bios.json) and
  [UEFI checks](verification/20261007/usb-iso-uefi.json) pass, including opt-in USB
  defaults, interrupted-trial recovery configuration, graphical-login services,
  firewall, diagnostic export and no failed units. UEFI also returned a real local
  AI answer. This remains a development candidate, not a completed twelve-item release.
- Added **Aether Beam** (`src/beam/`): a plan-validated install scheduler that
  downloads and verifies in a worker pool and commits one package transaction at
  a time under a file lock, with dependency ordering, blocked-dependant reporting,
  a resumable journal and a private receipt. The offline suite (21 tests) measures
  real overlap instead of trusting the scheduler's report: preparation must run in
  parallel, commits must not, and a failed application must not stop independent
  ones. Wrong-architecture plans are refused. No image contains it and its flatpak
  and `dpkg` paths are untested against a real package database.
- Added **Aether Pilot** (`src/pilot/`), the Copilot-style layer: a fixed action
  catalog with typed parameters, single-use expiring confirmations, a separate
  root helper that rebuilds argv from a root-owned catalog, and a `0600` audit
  log. Forged or malformed model proposals, shell metacharacters, undeclared
  parameters and non-admin ids are rejected by the offline suite (27 tests).
  Nimbrel gained an `assist` task whose only privilege is naming one catalog
  action; the person still confirms it. No image contains Pilot and the `pkexec`
  hand-off is untested.
- Recorded the multi-architecture position in [ARM64 status](arm64.md): first-party
  install and update code now maps and rejects architectures consistently, but
  there is still no ARM64 userspace build, boot image or boot result.
- Aether Settings gained "Install apps in parallel" and "Aether Pilot" pages.
  They are compiled by the existing hosted desktop check; they have not been
  clicked through on a booted image.
- Published the refreshed 2026-11-16 development download. It does not complete
  items 1-7 or 9-12 above: there is still no deployed update repository or
  production trust, no physical-hardware validation, and the UEFI graphical
  session was not confirmed. The VM is deliberately BIOS-only for this snapshot.
