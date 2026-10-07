# October 6 development update

Aether is gaining a central place to manage everyday desktop features. This
work is a development candidate, not a completed stable release.

## Added in source and the candidate filesystem

- **Aether Settings:** first-run setup, updates, applications, recovery, backups,
  performance, privacy, accessibility, phone connection and firmware controls.
- **Applications:** native Flatpak and a rebuilt Discover with Flatpak support.
  Flathub is an explicit per-user opt-in. Permission controls use KDE's installed
  application-permissions module.
- **Local AI:** socket activation, idle unloading, a device-wide off switch,
  opt-in text-folder search, attachment previews and conversation deletion.
  Documents are never automatically submitted to the model.
- **Lightweight mode:** reversible animation, blur and indexing preferences.
- **Accessibility:** keyboard navigation, accessible control names, screen reader,
  font, scaling and contrast settings.
- **Phone connection:** KDE Connect, with explicit private-network firewall access.
  Pairing remains a user action. Private-address rules are not a trusted-network
  detector; turn them off on networks where discovery should not be allowed.
- **Firmware:** native fwupd/LVFS support, device inspection and explicit update
  approval. No automatic flashing or automatic hardware reports.
- **OS update preparation:** signed metadata and package verification, automatic
  checks, desktop notifications, explicit installation and no automatic restart.
  The trial system uses a separate ext4 system copy with shared user homes.

## Release trust remains unconfigured

The installed checker cannot use a public OS repository until an administrator
provisions reviewed public trust files. No disposable test key becomes release
trust, and no publisher credential is shipped. The [local key setup procedure](../src/updates/LOCAL-KEY-SETUP.md)
uses hidden passphrase prompts and explains offline key custody.

Application updates from an explicitly enabled Flatpak source are separate from
Aether OS updates. This build does not add Ubuntu or Arch binary repositories.

## Validation so far

The native builds completed using all 16 build-VM CPUs. Thirteen upstream
components were packaged individually and installed/configured successfully.
The Aether integration package also installed and rebuilt the initramfs.

Inside Aether's filesystem, 24 signature/TUF regressions and 25 feature tests
pass. New systemd units pass offline verification. The first ISO boot test
reached the desktop and passed the unprivileged Flatpak sandbox check; it caught
a launcher line-ending defect that has since been corrected. That first ISO is
not a release candidate for publication.

Rebuilt-image BIOS/UEFI checks, trial-boot recovery and interrupted-installation
testing are still required before these changes replace a user's disk. Native
phone pairing, physical firmware flashing and assistive hardware have not been
tested. Some older base libraries lack complete package ownership records; core
OS updates must remain gated until that inventory is reconciled.

The current desktop target remains x86_64 (also called x64). Historical 32-bit
x86 and ARM prototypes are preserved; these changes do not claim completed ports.

## Build interruption

The Ubuntu build VM powered off during the rebuilt-image work. The newer images
have not passed their final checks and are not published. Source and completed
validation work are preserved. Resume from the candidate workspace, inspect any
partial artifacts, and repeat the affected image and recovery checks before release.
