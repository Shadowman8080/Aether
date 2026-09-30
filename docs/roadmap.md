# Roadmap

Aether 0.3 is a development snapshot. This is what would have to happen before
it could honestly be called a release, roughly in dependency order.

## Blocking a first real release

1. **A deployed, authenticated update repository.** The signing and TUF tooling
   is built and tested; the infrastructure is empty. Nothing updates today.
2. **A verified boot chain.** Secure Boot support, signed kernel/initramfs,
   signed unified kernel images, and a documented revocation story.
3. **Key custody.** Public-release root keys held independently, offline or
   hardware-backed, with an independently recoverable backup and a *tested*
   rotation and revocation procedure. Two keys on one online builder is not
   resilience.
4. **Actual CI.** Every check in [`verification.md`](verification.md) is manual
   today.
5. **Physical-hardware testing.** Every result so far is virtualised or emulated.
   Until real machines are exercised, the project has no hardware support
   policy.

## Security work

- AppArmor coverage for the desktop applications that currently run unconfined.
- MAC policy for containers and VMs; network-profile and VPN policies.
- Firmware and microcode update coverage.
- A maintained browser.
- Flatpak (or equivalent) sandboxed app distribution with a real permission UI,
  plus enforced device and capture controls.
- Multi-user testing of screen lock, suspend and accessibility boundaries.
- FIDO2 / central identity / biometrics.
- USB and Thunderbolt device enrollment.
- Audited update rollback.
- Protected remote logging and detections.
- Independent, immutable backups separate from the restic repository.
- An independent security assessment by someone outside the project.

## Installation

- Partitioned installs — the current installer is **whole-disk only**.
- Convert or migrate an existing installation without erasing it.
- Separate `/boot` encryption, then encrypted hibernation.
- Offline and unattended install modes.

## Architecture

- An ARM64 desktop image, plus a stated support policy.
- Secure Boot on real hardware.
- Hardware-accelerated inference, and a larger model than 0.8B.

## Update behaviour

The policy is already recorded and should not be renegotiated quietly:

> **Check automatically. Ask before installing. Never auto-restart.**

Also needed: automated `timestamp` refresh before its one-day expiry, with
monitoring that turns an expired-metadata condition into a **visible failure**
rather than a misleading "no updates available". Bucket-scoped read-only
credentials must be provisioned separately from the publisher credential; the
publisher credential must never be embedded in an ISO, VMDK or client.

## Quality of life

- On-device model updates and model selection in the UI.
- Screen reader pass over the greeter and first-party apps.
- HDR/VRR validation.
- Suspend/resume behaviour, once encrypted resume exists.

## Explicitly not planned

- Becoming a fork of an existing distribution.
- Shipping prebuilt binary packages of the base system. Compiling from source
  is the core of the project.
- Claiming certification or compliance without an independent assessment.