# Aether Secure Boot assets

Public trust material only; no private key is stored here.

- `shimx64.efi` and `grubx64.efi` are signed with the Aether db key.
- The installed UKI embeds the initramfs at build time. The embedded tools
  must come from the source-built security runtime; a release rebuild requires
  a runtime with no host-library fallbacks.
- `aether-installed.efi` is the signed installed UKI. It embeds the unlock/LVM initramfs and uses the `AETHER_ROOT` filesystem label, with optional LUKS label `AETHER_CRYPT`.
- `PK.auth`, `KEK.auth`, `db.auth` and the `.esl` files enroll the Aether key hierarchy.
- `grub-installed.cfg` chainloads the signed UKI.

Rebuild with `build/desktop/scripts/build-secureboot-assets.sh` and an external
`AETHER_SB_KEYDIR`. Never copy `db.key`, `KEK.key` or `PK.key` into this tree.
