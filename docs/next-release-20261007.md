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
