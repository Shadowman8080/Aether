"""Build signed, versioned TUF metadata around Aether package artifacts.

Uses upstream TUF and cryptography implementations. Private keys are supplied
by a signer, never generated here or copied into the repository. Publication
and key custody are deliberately separate from metadata construction.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath

from tuf.api.metadata import Metadata, MetaFile, Root, Snapshot, Targets, TargetFile, Timestamp

ROLES = ("root", "targets", "snapshot", "timestamp")
LIFETIMES = {"root": 365, "targets": 30, "snapshot": 7, "timestamp": 1}


def safe_target(name: str) -> str:
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_./+-]+", name):
        raise ValueError("Invalid target path")
    parts = PurePosixPath(name).parts
    if not parts or name.startswith("/") or any(p in (".", "..") for p in name.split("/")):
        raise ValueError("Unsafe target path")
    if any(not p for p in name.split("/")):
        raise ValueError("Empty target path component")
    return name


def sign_checked(md: Metadata, role: str, signers: dict, root: Metadata) -> bytes:
    for signer in signers[role]:
        md.sign(signer, append=True)
    if not root.signed.get_verification_result(role, md.signed_bytes, md.signatures):
        raise ValueError(f"Insufficient authorized signatures for {role}")
    return md.to_bytes()


def create_root(signers: dict, *, root_threshold: int = 2, now=None) -> Metadata:
    """Create bootstrap metadata for an explicit signing ceremony.

    Production callers should supply independently held root signers. Unit tests
    use disposable, in-memory keys. This function does not persist any key.
    """
    now = now or datetime.now(timezone.utc)
    root = Metadata(Root(version=1, expires=now + timedelta(days=LIFETIMES["root"])))
    for role in ROLES:
        for signer in signers[role]:
            root.signed.add_key(signer.public_key, role)
    if root_threshold < 2 or len(root.signed.roles["root"].keyids) < root_threshold:
        raise ValueError("At least two distinct root signatures are required")
    root.signed.roles["root"].threshold = root_threshold
    sign_checked(root, "root", signers, root)
    return root


def build_repository(output: Path, files: dict[str, Path], root: Metadata, signers: dict,
                     *, version: int, now=None, expires=None) -> dict:
    """Create a new immutable publication directory; never modify an old one.

    The caller must persist monotonically increasing versions and publish target
    files and versioned metadata before timestamp.json. Clients enforce rollback
    protection. This builder alone is not a release authorization workflow.
    """
    now = now or datetime.now(timezone.utc)
    if version < 1 or not files:
        raise ValueError("Positive release version and targets are required")
    if output.exists():
        raise FileExistsError("Refusing to overwrite a publication directory")
    if not isinstance(root.signed, Root) or not root.signed.consistent_snapshot:
        raise ValueError("A consistent-snapshot root is required")
    if not root.signed.get_root_verification_result(None, root.signed_bytes, root.signatures):
        raise ValueError("Bootstrap root is not self-consistently signed")
    if root.signed.is_expired(now):
        raise ValueError("Root metadata is expired")

    # Read inputs before creating output. No symlink targets or directories.
    inputs = {}
    for name, path in files.items():
        safe_target(name)
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Not a regular artifact: {name}")
        inputs[name] = path.read_bytes()

    def expiry(role):
        return (expires or {}).get(role, now + timedelta(days=LIFETIMES[role]))

    targets = Metadata(Targets(version=version, expires=expiry("targets")))
    for name, data in inputs.items():
        targets.signed.targets[name] = TargetFile.from_data(name, data, ["sha256"])
    target_bytes = sign_checked(targets, "targets", signers, root)
    snapshot = Metadata(Snapshot(version=version, expires=expiry("snapshot"), meta={
        "targets.json": MetaFile.from_data(version, target_bytes, ["sha256"])
    }))
    snapshot_bytes = sign_checked(snapshot, "snapshot", signers, root)
    timestamp = Metadata(Timestamp(version=version, expires=expiry("timestamp"),
        snapshot_meta=MetaFile.from_data(version, snapshot_bytes, ["sha256"])))
    timestamp_bytes = sign_checked(timestamp, "timestamp", signers, root)
    metadata = output / "metadata"
    artifacts = output / "targets"
    metadata.mkdir(parents=True)
    artifacts.mkdir()
    (metadata / f"{root.signed.version}.root.json").write_bytes(root.to_bytes())
    (metadata / f"{version}.targets.json").write_bytes(target_bytes)
    (metadata / f"{version}.snapshot.json").write_bytes(snapshot_bytes)
    receipt = {"version": version, "targets": {}}
    for name, data in inputs.items():
        digest = hashlib.sha256(data).hexdigest()
        p = PurePosixPath(name)
        destination = artifacts / str(p.parent) / (digest + "." + p.name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        receipt["targets"][name] = {"sha256": digest, "length": len(data)}
    # Timestamp last: it is the commit point for repository publication.
    (metadata / "timestamp.json").write_bytes(timestamp_bytes)
    (output / "publication.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt
