#!/bin/bash
# Rebuild the public Secure Boot assets used by the installer and live image.
# Private keys stay outside the repository and are never copied here.
set -euo pipefail
base=/opt/aether
keydir=${AETHER_SB_KEYDIR:-$base/secureboot/keys}
signed=${AETHER_SB_SIGNED_DIR:-$base/secureboot/out}
root=${AETHER_SB_ROOT:-$base/desktop-system}
dest=${AETHER_SB_ASSETS:-$base/desktop/assets/usr/share/aether/secureboot}
root_label=AETHER_ROOT
luks_label=AETHER_CRYPT

for file in "$keydir/db.key" "$keydir/db.crt" "$keydir/PK.auth" "$keydir/KEK.auth" \
            "$keydir/db.auth" "$keydir/PK.esl" "$keydir/KEK.esl" "$keydir/db.esl" \
            "$signed/shimx64.efi" "$signed/grubx64.efi"; do
    test -f "$file" || { echo "Missing Secure Boot input: $file" >&2; exit 1; }
done
kernel=$(find "$root/boot" -maxdepth 1 -name 'vmlinuz-*' -printf '%p\n' | sort | tail -1)
test -n "$kernel" || { echo "No kernel in $root/boot" >&2; exit 1; }

mkdir -p "$dest"
install -m644 "$signed/shimx64.efi" "$dest/shimx64.efi"
install -m644 "$signed/grubx64.efi" "$dest/grubx64.efi"
for name in db.crt db.esl PK.esl KEK.esl PK.auth KEK.auth db.auth; do
    install -m644 "$keydir/$name" "$dest/$name"
done

cat >"$dest/grub-installed.cfg" <<'CFG'
set default=0
set timeout=3
menuentry 'Aether Linux 0.3' {
  chainloader /EFI/aether/aether.efi
}
CFG

release=$(basename "$kernel" | sed 's/^vmlinuz-//')
initrd="$root/boot/initramfs-$release.img"
test -f "$initrd" || {
    echo "Missing installed initramfs: $initrd" >&2
    echo "Build it with aether-mkinitramfs before assembling the signed UKI." >&2
    exit 1
}
runtime_marker="$root/usr/share/aether/security-runtime/source-built"
if [ ! -f "$runtime_marker" ] && [ "${AETHER_ALLOW_LAB_CRYPTO:-0}" != 1 ]; then
    echo "No source-built security runtime marker: $runtime_marker" >&2
    echo 'Install it with build/desktop/scripts/install-security-runtime.sh.' >&2
    echo 'AETHER_ALLOW_LAB_CRYPTO=1 is only for a disposable lab asset.' >&2
    exit 1
fi
if [ -f "$runtime_marker" ] && ! grep -qx 'source=security-system' "$runtime_marker" \
        && [ "${AETHER_ALLOW_LAB_CRYPTO:-0}" != 1 ]; then
    echo "Security runtime marker has no security-system provenance: $runtime_marker" >&2
    exit 1
fi
if [ -f "$runtime_marker" ] && grep -qx 'host_library_fallbacks=yes' "$runtime_marker" \
        && [ "${AETHER_ALLOW_LAB_CRYPTO:-0}" != 1 ]; then
    echo "Security runtime contains host-library fallbacks: $runtime_marker" >&2
    echo 'Build a complete source runtime, or use AETHER_ALLOW_LAB_CRYPTO=1 for a labelled lab asset.' >&2
    exit 1
fi
/usr/bin/ukify build \
    --linux "$kernel" \
    --initrd "$initrd" \
    --cmdline "root=LABEL=$root_label aether.luks=LABEL=$luks_label ro rootwait quiet console=tty0 console=ttyS0,115200n8" \
    --uname "$release" \
    --output "$dest/aether-installed.efi" \
    --secureboot-private-key "$keydir/db.key" \
    --secureboot-certificate "$keydir/db.crt"

cat >"$dest/README.md" <<'MD'
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
MD

chmod 644 "$dest"/*
sbverify --cert "$keydir/db.crt" "$dest/shimx64.efi"
sbverify --cert "$keydir/db.crt" "$dest/grubx64.efi"
sbverify --cert "$keydir/db.crt" "$dest/aether-installed.efi"
echo "SECUREBOOT_ASSETS_PASS"
