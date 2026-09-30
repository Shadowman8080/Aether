"""GnuPG package signing helpers; no private-key generation or storage."""
from __future__ import annotations

import re
import os
import subprocess
from pathlib import Path


def tool_path(path: Path, executable: str) -> str:
    """Git for Windows bundles MSYS GnuPG, which expects POSIX paths."""
    value = path.resolve().as_posix()
    if os.name == "nt" and "/git/usr/bin/" in executable.replace("\\", "/").lower():
        return "/" + value[0].lower() + value[2:]
    return str(path.resolve())


def check_fingerprint(fingerprint):
    if not re.fullmatch(r"[A-F0-9]{40}|[A-F0-9]{64}", fingerprint):
        raise ValueError("A full uppercase signing-key fingerprint is required")


def sign_package(package: Path, home: Path, fingerprint: str, *, gpg="gpg") -> Path:
    check_fingerprint(fingerprint)
    if not package.name.endswith((".pkg.tar.zst", ".pkg.tar.xz", ".pkg.tar.gz")):
        raise ValueError("Expected a pacman package archive")
    if not package.is_file() or package.is_symlink():
        raise ValueError("Package must be a regular file")
    signature = Path(str(package) + ".sig")
    if signature.exists():
        raise FileExistsError("Refusing to replace an existing signature")
    # Passphrases, if used, go through the operator's GnuPG agent/pinentry.
    # Never accept a passphrase through command-line arguments or chat.
    subprocess.run([gpg, "--homedir", tool_path(home, gpg), "--batch", "--local-user", fingerprint,
        "--output", tool_path(signature, gpg), "--detach-sign", tool_path(package, gpg)], check=True,
        stdout=subprocess.DEVNULL)
    return signature


def verify_package(package: Path, public_keyring: Path, fingerprint: str, *, gpgv="gpgv"):
    check_fingerprint(fingerprint)
    signature = Path(str(package) + ".sig")
    if not signature.is_file() or signature.is_symlink():
        raise ValueError("Detached package signature is missing")
    result = subprocess.run([gpgv, "--status-fd", "1", "--keyring", tool_path(public_keyring, gpgv),
        tool_path(signature, gpgv), tool_path(package, gpgv)], capture_output=True, text=True)
    if result.returncode:
        raise ValueError("Package signature verification failed")
    valid = [line.split() for line in result.stdout.splitlines() if line.startswith("[GNUPG:] VALIDSIG ")]
    if not any(fingerprint in (fields[2], fields[-1]) for fields in valid):
        raise ValueError("Package was not signed by the pinned signing key")
