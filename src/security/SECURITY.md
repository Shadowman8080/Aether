# Aether security integration — development build

This is an incomplete implementation of the requested 192-item checklist, not
a security certification or a claim that Aether is production-ready. The JSON
checklist preserves every requested item and distinguishes pending work from
implemented and tested behavior. Hardware, deployment and operational controls
cannot be established by installing packages alone.

## Implemented source recipes (runtime test results recorded separately)

- Linux 6.18.54-aether4: nftables, AppArmor, Yama and Landlock; stack-offset
  randomization, hardened/randomized slab allocation, hardened usercopy,
  FORTIFY, allocation initialization, IOMMU defaults and zram. Module signature
  support is available but signatures are **not enforced**. Secure Boot remains
  disabled and the kernel/initramfs are not a verified signed boot chain.
- Source-built nftables 1.1.7 and its libraries; stateful IPv4/IPv6 incoming and
  forwarding default-deny policy. DNS, DHCP, IPv6 discovery and normal outgoing
  client traffic remain possible. Firewall reload owns only its own table.
  Explicitly opened ports apply on all networks. VPN/container-specific rules,
  interface trust profiles and outbound allowlists need separate integration.
- AppArmor 4.1.8 parser and library, with a selected timesyncd policy and a
  negative-access test. Most desktop applications remain unconfined. Policy
  availability must never be presented as universal application protection.
- PAM login delay and temporary lockout after five failures (two minutes),
  yescrypt password changes and quality checks for new passwords. Existing
  user passwords are preserved. The live development account remains a known
  credential and must never be treated as a secure deployed identity.
- sudo uses a pseudo-terminal, a five-minute authentication lifetime and private
  file defaults. Root stays locked. Permanent input/audio/video group membership
  is replaced by logind's active-seat access; desktop tests must verify this.
- Private home/file defaults; bounded persistent journal; no stored core dumps;
  kernel log/pointer/tracing restrictions; discovery disabled. SSH is not
  installed/enabled by this build; a restrictive SSH configuration is provided
  for later explicitly configured remote administration.
- Disk-backed swap disabled; compressed RAM swap offered. Hibernation disabled
  pending an encrypted resume design. Old plaintext data already written to
  existing disks is not retroactively erased or encrypted.
- Five-minute idle locking, lock-on-resume defaults, minimal nonpersistent
  clipboard history, removable-media automount disabled and sensitive filename
  indexing exclusions. VMware still selects X11 for requested clipboard support;
  this weakens isolation between applications sharing that session. Native
  VMware clipboard/window-autofit and suspend/resume need hardware/UI tests.
- Source-built cryptsetup/LUKS2 and an interactive x86_64 live installer. The
  installer requires explicit disk erasure confirmation, offers encryption,
  adds a separate recovery passphrase, requires a personal account password,
  and asks for a backup destination. It does not convert an existing disk in
  place. /boot remains unencrypted; verified boot is separate unfinished work.
- Source-built restic 0.19.1, explicit encrypted backup setup, a daily timer,
  repository consistency checking and restoration to a new directory. Backup
  credentials are root-readable local files for unattended operation, so root
  compromise can expose them. Recovery passphrases must also be kept offline.
  History is retained; automatic destructive pruning is not enabled.

## Day-to-day controls

Open **Aether Security** or run `sudo aether-security-status --text`. A normal
user may be unable to inspect the active firewall or AppArmor profiles; the
tool reports that as unverified, not as disabled or healthy.

Use `sudo aether-firewall status`, `allow-tcp PORT`, `allow-udp PORT`,
`remove-tcp PORT` or `remove-udp PORT` for deliberate incoming exposure.
The root-only configuration is `/etc/aether-security/firewall.json`. Other
software's nftables tables are preserved. Forwarding is denied by default, so
container routing and VPN gateways need an explicit reviewed policy.

Use **Set Up Encrypted Backups** or `sudo aether-backup setup`. The user chooses
the destination and enters a new backup passphrase locally. No backup is
enabled until that setup succeeds. Then run `sudo aether-backup run`,
`sudo aether-backup check` and inspect `sudo aether-backup snapshots`.
Restore with `sudo aether-backup restore SNAPSHOT /new/empty-destination`.
Compare restored contents before replacing current files. Backups cover /home
and /etc without crossing filesystem boundaries; separately mounted user data
requires explicit inclusion and testing.

For this user's VMware setup, the requested Windows folder is
`C:\Users\User\OneDrive\Desktop\Aether Encrypted Backups`, exposed as the
single share `AetherEncryptedBackups`. Its guest path is
`/mnt/aether-shares/AetherEncryptedBackups`. No broader host directory needs to
be shared. Writable OneDrive synchronization is not an offline/immutable copy.
An unavailable mount must cause backup failure, never fallback onto the root
disk. Copying or syncing the restic repository while it is being changed can
produce an incomplete remote copy; validate the remotely recovered repository.

## Recovery and incident handling

Keep the previous working VMDK/ISO offline until this build is accepted.
Configuration changes are developed on a copy-on-write test disk. Do not apply
them to a running VM disk. A failed firewall service prevents NetworkManager
startup; local login and the console remain available for diagnosis.

For temporary authentication lockout, wait two minutes or use an already
authorized administrator session to run `faillock --user USER --reset`.
This does not unlock encrypted storage. If storage keys are lost, use the
separately recorded recovery passphrase; there is no encryption bypass.

If compromise is suspected, disconnect the VM's virtual network adapter,
preserve the disk/logs, and rotate affected credentials from a trusted machine.
Do not erase evidence through cleanup scripts. Reinstall from verified media
and restore reviewed data. A lost but unlocked device can expose encryption
keys; revoke external sessions/tokens as well as local credentials.

## Still required before claiming the complete checklist

Release signing ownership and trust enrollment; signed UKIs and revocation;
TPM enrollment/attestation; authenticated production repositories, full package
inventory and maintained automatic security updates; firmware/microcode update
coverage; broad MAC/application sandbox coverage and a maintained browser;
Flatpak permission UI and enforced device/capture controls; tested multi-user
screen-lock/suspend/accessibility boundaries; FIDO/central identity/biometrics;
USB/Thunderbolt enrollment; network-profile/VPN policies; audited update
rollback; protected remote logs and detections; independent immutable backups;
fleet ownership, tamper/lost-device procedures, incident contacts and an
independent security assessment. Required credentials/endpoints must come from
the deployment owner. No compliance certification or validated cryptographic
mode is claimed. ARM and 32-bit desktop security images are not validated by
an x86_64 test run.

Sources are pinned in `sources.json`. Some archives have upstream published
SHA256 verification; others were obtained from upstream HTTPS with a pinned
digest and, where available, a BLFS checksum cross-check. That is not a claim
that every upstream signing key or complete supply chain was independently
authenticated. Restic Go dependencies are checked against its go.sum.

References: Linux kernel sysctl/self-protection documentation; nftables project
workstation rules; AppArmor upstream documentation; systemd execution controls;
Linux-PAM module manuals; cryptsetup upstream documentation; restic backup and
restore documentation. Implementations must be tested on each release.
