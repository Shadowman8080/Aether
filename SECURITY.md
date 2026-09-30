# Security Policy

## ⚠️ Read this before reporting anything

**Aether Linux is a work-in-progress development snapshot. It is not audited,
not certified, and not hardened for adversarial use.**

Nothing in this repository is a security certification or a compliance claim.
Installing Aether on a machine holding sensitive or irreplaceable data is your
own decision to make and your own risk to carry.

If you are evaluating Aether for real use, assume it will fail a security
review. It would.

## Reporting a vulnerability

There is **no published security contact address yet**. Setting one up requires
a domain the project controls and a monitored inbox; publishing an address that
nobody watches would be worse than admitting the gap.

Until one exists:

1. Open a **private** channel with the maintainer on GitHub rather than a public
   issue.
2. Do **not** open a public issue for an unfixed vulnerability.
3. Give a concrete reproduction, the affected component, and the impact you
   believe it has.

Public disclosure before a fix exists is not a violation of policy here, because
no coordinated-disclosure deadline has ever been offered. That is a gap in the
project, not a permission slip.

## Already-known problems

These are documented on purpose. They are not discoveries.

### Cryptography and boot

- **Secure Boot is unsupported** and the kernel/initramfs are not a verified
  signed boot chain.
- **Kernel module signature support is compiled in but signatures are not
  enforced.**
- `/boot` is **not encrypted**; only the root filesystem is covered by LUKS2.
- Hibernation is disabled pending an encrypted-resume design. Old plaintext data
  already written to existing disks is not retroactively erased or encrypted.
- There is no TPM enrollment or attestation.

### Application confinement

- **Most desktop applications remain unconfined** by AppArmor. A small number of
  policies ship, including one for `timesyncd` plus a negative-access test.
- Policy availability must never be read as universal application protection.

### Credentials and keys

- The build and test environments use **known development credentials**. These
  are not secrets and must never be published.
- Backup credentials are **root-readable local files** so unattended operation
  works. Root compromise therefore exposes them.
- Update signing keys, TUF role keys and object-storage upload credentials are
  **not yet separated into independent custody**. Two keys on one online builder
  do not provide compromise resilience.
- The object-storage bucket used during development is **private development
  storage**, not a production update repository, and its token has expired.

### Exposure

- **SSH is not installed or enabled** by this build.
- The installer does **not** convert an existing disk in place; it is whole-disk.
- The live ISO makes **no persistent changes** — and equally offers no rollback.
- Selecting X11 to obtain VMware clipboard support **weakens isolation** between
  applications sharing that session.

### Operational

- Forwarding is denied by default, so **container routing and VPN gateways need
  an explicit reviewed policy**. Treat this as a footgun, not a feature.
- No independent security assessment has been performed.
- No compliance certification is claimed and no validated cryptographic mode is
  claimed.

## What's actually implemented

The security work is an **incomplete implementation of a 192-item checklist**.
The itemised status — distinguishing implemented behaviour from pending work —
lives in [`src/security/SECURITY.md`](src/security/SECURITY.md). Read it before
relying on anything security-related.

Implemented and tested:

- Linux 6.18.54-aether4 with nftables, AppArmor, Yama, Landlock, FORTIFY,
  hardened usercopy, allocation initialisation, IOMMU defaults, zram
- Source-built nftables 1.1.7, stateful IPv4/IPv6 incoming and forwarding
  default-deny. A firewall reload owns only its own table; other software's
  nftables tables are preserved.
- PAM login delay and temporary lockout after five failures (two minutes);
  yescrypt password hashing; new-password quality checks
- sudo with a pseudo-terminal, a five-minute authentication lifetime and private
  file defaults. Root stays locked.
- Private home and file defaults; bounded persistent journal; no stored core
  dumps; kernel log, pointer and tracing restrictions; discovery disabled
- Disk-backed swap disabled; compressed RAM swap offered
- Five-minute idle locking, lock-on-resume, minimal nonpersistent clipboard
  history, removable-media automount disabled
- Source-built cryptsetup/LUKS2 and an interactive x86_64 live installer
- Source-built restic 0.19.1 with explicit encrypted backup setup, a daily
  timer, repository consistency checking and restore to a new directory

## Day-to-day commands

```sh
aether-security-status --text       # or open the Aether Security app
aether-firewall status
aether-firewall allow-tcp 8080      # deliberate exposure, on purpose
aether-backup run
aether-backup check
aether-backup snapshots
aether-backup restore SNAPSHOT /new/empty-destination
```

A normal user may be unable to inspect the active firewall or AppArmor profiles.
**The tooling reports that as unverified, not as healthy.**

## Honest reminder

Compiling from source with pinned digests protects against accidental drift. It
does not prove that every upstream signing key or the complete supply chain was
independently authenticated, and it is not a substitute for review.