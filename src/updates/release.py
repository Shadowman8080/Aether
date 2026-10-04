#!/usr/bin/env python3
"""Assemble already-signed Aether packages into a TUF publication directory.

Usage: python release.py --plan release-plan.json --root trusted-root.json
         --signer-directory /protected/online-signers --output /staging/release-1

Only targets/snapshot/timestamp keys are needed. Root keys stay offline.
This tool neither uploads artifacts nor installs software.
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import io
import json
import os
import re
import stat
import tarfile
import tempfile
from pathlib import Path

from cryptography.hazmat.primitives.serialization import load_pem_private_key
from securesystemslib.signer import CryptoSigner
from tuf.api.metadata import Metadata

from package_signing import verify_package
from repository import build_repository


def load_signers(directory: Path) -> dict:
    if os.name != "posix":
        raise RuntimeError("Operational signer loading requires a Linux filesystem; Windows tests use disposable keys")
    info = directory.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
        raise PermissionError("Signer directory must be owned by the caller, mode 0700")
    signers = {}
    for role in ("targets", "snapshot", "timestamp"):
        keyfile = directory / f"{role}.pem"
        info = keyfile.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise PermissionError(f"Unsafe permissions for {role} signer")
        data = keyfile.read_bytes()
        password = None
        if b"ENCRYPTED PRIVATE KEY" in data:
            password = getpass.getpass(f"Unlock {role} signer locally: ").encode()
        signers[role] = [CryptoSigner(load_pem_private_key(data, password))]
    return signers


def ar_members(data: bytes):
    """Yield (name, payload) for each member of a Unix `ar` archive.

    A .deb is an ar archive of debian-binary, control.tar.* and data.tar.*.
    """
    if not data.startswith(b"!<arch>\n"):
        raise ValueError("Package is not a dpkg archive")
    offset = 8
    while offset < len(data):
        header = data[offset:offset + 60]
        if len(header) < 60:
            raise ValueError("Truncated dpkg archive header")
        name = header[0:16].decode("ascii", "replace").strip().rstrip("/")
        try:
            size = int(header[48:58].decode("ascii").strip())
        except ValueError:
            raise ValueError("Invalid dpkg archive member header") from None
        start = offset + 60
        payload = data[start:start + size]
        if len(payload) != size:
            raise ValueError("Truncated dpkg archive member")
        yield name, payload
        offset = start + size + (size % 2)


def inspect_package(path: Path) -> dict:
    """Read Package/Version/Architecture from a .deb's control member."""
    control = None
    for name, payload in ar_members(path.read_bytes()):
        if name.startswith("control.tar"):
            control = payload
            break
    if control is None:
        raise ValueError("Package has no control member")
    with tarfile.open(fileobj=io.BytesIO(control), mode="r:*") as archive:
        item = next((m for m in archive.getmembers() if m.name.lstrip("./") == "control"), None)
        if item is None or not item.isfile() or item.size > 65536:
            raise ValueError("Invalid package metadata")
        content = archive.extractfile(item).read().decode("utf-8")
    result = {}
    for line in content.splitlines():
        if ":" in line and line[:1] not in (" ", "\t"):
            key, value = line.split(":", 1)
            if key in ("Package", "Version", "Architecture"):
                if key in result:
                    raise ValueError("Duplicate package identity field")
                result[key] = value.strip()
    return result


def prepare_files(plan: dict, temporary: Path, *, gpgv="gpgv") -> dict:
    if plan["channel"] not in ("development", "testing", "stable"):
        raise ValueError("Unknown release channel")
    if plan["architecture"] not in ("i686", "x86_64", "aarch64", "armv7h"):
        raise ValueError("Unknown architecture; x64 is an alias of x86_64")
    files, packages, names = {}, [], set()
    for entry in plan["packages"]:
        archive = Path(entry["archive"])
        if archive.is_symlink() or not archive.is_file():
            raise ValueError("Package must be a regular file")
        archive = archive.resolve()
        if archive.name in names or not re.fullmatch(r"[A-Za-z0-9_.+:%~-]+\.deb", archive.name):
            raise ValueError("Duplicate or invalid package filename")
        names.add(archive.name)
        if archive.is_symlink() or not archive.is_file():
            raise ValueError("Package must be a regular file")
        data = archive.read_bytes()
        if hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise ValueError("Package differs from the reviewed release plan")
        verify_package(archive, Path(plan["public_keyring"]), plan["signer_fingerprint"], gpgv=gpgv)
        identity = inspect_package(archive)
        if identity.get("Package") != entry["name"] or identity.get("Version") != entry["version"]:
            raise ValueError("Package name or version differs from release plan")
        if identity.get("Architecture") not in ("all", plan["architecture"]):
            raise ValueError("Package architecture differs from release channel")
        target = "packages/" + archive.name
        # Copy the verified bytes into a private staging directory so later
        # changes to source artifacts cannot silently change this release.
        frozen = temporary / archive.name
        frozen.write_bytes(data)
        sig = Path(str(archive) + ".sig").read_bytes()
        frozen_sig = Path(str(frozen) + ".sig")
        frozen_sig.write_bytes(sig)
        verify_package(frozen, Path(plan["public_keyring"]), plan["signer_fingerprint"], gpgv=gpgv)
        files[target], files[target + ".sig"] = frozen, frozen_sig
        packages.append({"name": entry["name"], "version": entry["version"], "target": target,
            "sha256": entry["sha256"], "architecture": identity["Architecture"]})
    if not packages:
        raise ValueError("No packages in release plan")
    catalog = temporary / "catalog.json"
    catalog.write_text(json.dumps({"schema": 1, "architecture": plan["architecture"],
        "channel": plan["channel"], "packages": packages}, indent=2) + "\n")
    files["aether/catalog.json"] = catalog
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("plan", "root", "signer-directory", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    root = Metadata.from_file(str(args.root))
    signers = load_signers(args.signer_directory)
    with tempfile.TemporaryDirectory(prefix="aether-release-") as temp:
        files = prepare_files(plan, Path(temp))
        receipt = build_repository(args.output, files, root, signers, version=plan["version"])
    print(f"Verified and staged release version {receipt['version']}; no upload or installation performed")


if __name__ == "__main__":
    main()
