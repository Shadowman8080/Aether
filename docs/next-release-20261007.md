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
