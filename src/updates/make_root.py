#!/usr/bin/env python3
"""Bootstrap ceremony for the Aether TUF trust root.

Creates the four TUF role keys and a self-signed root metadata file:

    python make_root.py --output DIR [--root-signers N] [--no-encrypt]

Layout written under DIR:

    root/root-1.pem .. root/root-N.pem   root private keys  (MOVE OFFLINE)
    signers/targets.pem                  online role keys  (mode 0600)
    signers/snapshot.pem
    signers/timestamp.pem
    trusted-root.json                    the trust anchor to pin/publish

Root keys are the trust anchors. Keep them on separate, offline media; two keys
generated on one machine do not provide compromise resilience. This script
exists to bootstrap a development root, or to prepare keys that the operator
then moves into independent custody. It never uploads anything and never
installs software.

Encrypted key output uses the passphrase in AETHER_KEY_PASSPHRASE (a local
prompt is intentionally avoided so the command is scriptable); pass
--no-encrypt to write unencrypted PEMs for a throwaway test root.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from securesystemslib.signer import CryptoSigner

from repository import ROLES, create_root


def new_signer():
    key = ed25519.Ed25519PrivateKey.generate()
    return key, CryptoSigner(key)


def write_private(path: Path, key, *, encrypt: bool) -> None:
    if encrypt:
        passphrase = os.environ.get("AETHER_KEY_PASSPHRASE")
        if not passphrase:
            raise SystemExit("Set AETHER_KEY_PASSPHRASE, or pass --no-encrypt")
        encryption = serialization.BestAvailableEncryption(passphrase.encode())
    else:
        encryption = serialization.NoEncryption()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        encryption,
    ))
    os.chmod(path, 0o600)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--root-signers", type=int, default=2)
    parser.add_argument("--no-encrypt", action="store_true")
    args = parser.parse_args()
    if args.root_signers < 2:
        parser.error("at least two root signers are required")

    keys, signers = {}, {}
    for role in ROLES:
        key, signer = new_signer()
        keys[role] = key
        signers[role] = [signer]
    for index in range(2, args.root_signers + 1):
        key, signer = new_signer()
        keys[f"root-{index}"] = key
        signers["root"].append(signer)

    root = create_root(signers, root_threshold=args.root_signers)

    output = args.output
    output.mkdir(parents=True, exist_ok=True)

    signer_dir = output / "signers"
    signer_dir.mkdir(mode=0o700, exist_ok=True)
    os.chmod(signer_dir, 0o700)
    for role in ("targets", "snapshot", "timestamp"):
        write_private(signer_dir / f"{role}.pem", keys[role], encrypt=not args.no_encrypt)

    root_dir = output / "root"
    root_dir.mkdir(mode=0o700, exist_ok=True)
    os.chmod(root_dir, 0o700)
    for name in sorted(k for k in keys if k.startswith("root")):
        number = "1" if name == "root" else name.split("-", 1)[1]
        write_private(root_dir / f"root-{number}.pem", keys[name], encrypt=not args.no_encrypt)

    (output / "trusted-root.json").write_bytes(root.to_bytes())
    threshold = root.signed.roles["root"].threshold
    print(f"root version {root.signed.version}: {args.root_signers} signers, threshold {threshold}")
    print(f"wrote {output / 'trusted-root.json'}")
    print(f"online role keys in {signer_dir}/ (mode 0700)")
    print("MOVE root/*.pem to independent offline custody; publish/pin trusted-root.json")
    print("A root generated on one machine is a bootstrap/dev root, not independent custody.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
