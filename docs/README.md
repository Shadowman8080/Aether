# Aether documentation

Welcome to Aether's documentation. Start here to try the desktop, understand its
features, or work on the source. **Aether is a work in progress.** The current
desktop release is 0.3.2 development for x86_64 (also called x64).

[Project home](../README.md) · [Development downloads](https://github.com/Shadowman8080/Aether/releases/tag/0.3.2-dev.20261006)

## Start using Aether

- [Getting started](getting-started.md): downloads, VMware setup, login and first steps.
- [Current features and verified results](modern-desktop-20261006.md): Settings,
  applications, local AI, recovery and the limits of current testing.
- [VMware and VirtualBox integration](guest-integration-status.md): clipboard,
  mouse integration and host settings.
- [Nimbrel local AI](../src/nimbrel/README.md): how the assistant works and its limits.
- [Sounds](sounds.md) and [icon motion](icon-motion.md): desktop feedback and reduced motion.

## Security, updates and recovery

- [Update and recovery implementation](../src/updates/README.md): signed metadata,
  package verification, trial systems and automatic checks.
- [Release signing-key setup](../src/updates/LOCAL-KEY-SETUP.md): operator procedures
  for establishing release trust. Ordinary users do not need publisher keys.
- [Security implementation](../src/security/SECURITY.md): protection mechanisms and limitations.
- [Report a vulnerability](../SECURITY.md): the project's reporting policy.

Public OS update trust is not configured. Automatic checks do not mean a
production update feed is available. Flatpak sources are a separate, explicit opt-in.

## Build and contribute

- [Build overview](build.md) and [current build recipes](../build/modern-20261006/README.md).
- [System architecture](architecture.md).
- [Contributing](../CONTRIBUTING.md), [code of conduct](../CODE_OF_CONDUCT.md)
  and [licensing](licensing.md).
- [Screenshots and videos](../media/README.md).

## Release records and future work

- [0.3.2 development record](modern-desktop-20261006.md) is the current validation summary.
  Its release includes `VERIFICATION.json` and `SHA256SUMS` for the exact images.
- [0.3.1 build record](release-20261006.md) describes an unpublished, superseded draft.
- [Earlier 0.3 verification](verification.md) and [original roadmap](roadmap.md)
  provide historical context; consult the current record for completed work.

The desktop currently targets x86_64. Historical x86 and ARM prototypes are not
current desktop ports. VM tests do not certify physical hardware or Secure Boot.

## Improving these docs

Documentation lives in this repository's `docs/` folder, with implementation
notes beside the relevant source. Submit corrections through the contribution
process and identify the Aether version being described. Keep links relative so
navigation works both on GitHub and in a checkout.
