"""Security regression tests with disposable keys and an in-memory transport."""
from __future__ import annotations

import io
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit

from securesystemslib.signer import CryptoSigner
from tuf.api import exceptions
from tuf.api.metadata import Metadata
from tuf.ngclient.fetcher import FetcherInterface

from client import AetherUpdateClient, POLICY
from package_signing import sign_package, verify_package, tool_path
from repository import ROLES, build_repository, create_root, safe_target
from release import prepare_files
from r2_fetcher import R2Fetcher


class DirectoryFetcher(FetcherInterface):
    def __init__(self, directory):
        self.directory = directory

    def _fetch(self, url):
        path = self.directory / unquote(urlsplit(url).path).lstrip("/")
        if not path.is_file():
            raise exceptions.DownloadHTTPError("Missing test artifact", 404)
        yield path.read_bytes()


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aether-update-test-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.keys = {role: [CryptoSigner.generate_ed25519()] for role in ROLES}
        self.keys["root"] += [CryptoSigner.generate_ed25519(), CryptoSigner.generate_ed25519()]
        self.root = create_root(self.keys, root_threshold=2)
        self.catalog = self.base / "catalog.json"
        self.catalog.write_text(json.dumps({"schema": 1, "architecture": "x86_64", "channel": "development"}))
        self.package = self.base / "sample.pkg.tar.gz"
        self.package.write_bytes(b"test-only target bytes")
        self.files = {"aether/catalog.json": self.catalog, "packages/sample.pkg.tar.gz": self.package}
        self.repo = self.base / "repo"
        self.receipt = build_repository(self.repo, self.files, self.root, self.keys, version=1)
        self.transport = DirectoryFetcher(self.repo)

    def client(self, state="state", root=None):
        return AetherUpdateClient(self.base / state, (root or self.root).to_bytes(),
            "https://updates.example.invalid", fetcher=self.transport)

    def target_path(self):
        digest = self.receipt["targets"]["packages/sample.pkg.tar.gz"]["sha256"]
        return self.repo / "targets/packages" / (digest + ".sample.pkg.tar.gz")

    def test_valid_repository_and_download(self):
        client = self.client()
        client.refresh()
        self.assertEqual(client.stage("packages/sample.pkg.tar.gz").read_bytes(), self.package.read_bytes())
        self.assertEqual(client.catalog("x86_64", "development")["schema"], 1)

    def test_no_install_or_restart_policy(self):
        self.assertEqual(POLICY, {"automatic_checks": True, "automatic_installation": False, "automatic_restart": False})

    def test_requires_fresh_metadata_before_download(self):
        with self.assertRaises(RuntimeError):
            self.client().stage("packages/sample.pkg.tar.gz")

    def test_tampered_package_rejected(self):
        self.target_path().write_bytes(b"tampered")
        client = self.client()
        client.refresh()
        with self.assertRaises((exceptions.LengthOrHashMismatchError, exceptions.DownloadLengthMismatchError)):
            client.stage("packages/sample.pkg.tar.gz")

    def test_tampered_timestamp_rejected(self):
        path = self.repo / "metadata/timestamp.json"
        data = json.loads(path.read_bytes())
        data["signed"]["version"] = 1000
        path.write_text(json.dumps(data))
        with self.assertRaises(exceptions.UnsignedMetadataError):
            self.client().refresh()

    def test_unsigned_timestamp_rejected(self):
        path = self.repo / "metadata/timestamp.json"
        data = json.loads(path.read_bytes())
        data["signatures"] = []
        path.write_text(json.dumps(data))
        with self.assertRaises(exceptions.UnsignedMetadataError):
            self.client().refresh()

    def test_expired_metadata_rejected(self):
        expired = self.base / "expired"
        build_repository(expired, self.files, self.root, self.keys, version=2,
            expires={"timestamp": datetime.now(timezone.utc) - timedelta(hours=1)})
        self.transport.directory = expired
        with self.assertRaises(exceptions.ExpiredMetadataError):
            self.client().refresh()

    def test_rollback_rejected_across_client_restarts(self):
        newer = self.base / "newer"
        build_repository(newer, self.files, self.root, self.keys, version=2)
        self.transport.directory = newer
        self.client().refresh()
        self.transport.directory = self.repo
        with self.assertRaises(exceptions.BadVersionNumberError):
            self.client().refresh()

    def test_wrong_trust_root_rejected(self):
        other = {role: [CryptoSigner.generate_ed25519()] for role in ROLES}
        other["root"].append(CryptoSigner.generate_ed25519())
        with self.assertRaises(exceptions.UnsignedMetadataError):
            self.client(root=create_root(other)).refresh()

    def test_mix_and_match_rejected(self):
        newer = self.base / "newer"
        build_repository(newer, self.files, self.root, self.keys, version=2)
        shutil.copyfile(self.repo / "metadata/1.targets.json", newer / "metadata/2.targets.json")
        self.transport.directory = newer
        with self.assertRaises(exceptions.LengthOrHashMismatchError):
            self.client().refresh()

    def test_architecture_and_channel_mismatch_rejected(self):
        for arch, channel in [("aarch64", "development"), ("x86_64", "stable")]:
            with self.subTest(architecture=arch, channel=channel):
                client = self.client(arch + channel)
                client.refresh()
                with self.assertRaises(ValueError):
                    client.catalog(arch, channel)

    def test_unlisted_target_rejected(self):
        client = self.client()
        client.refresh()
        with self.assertRaises(ValueError):
            client.stage("packages/not-signed.pkg.tar.gz")

    def test_root_threshold_enforced(self):
        keys = dict(self.keys)
        keys["root"] = keys["root"][:1]
        with self.assertRaises(ValueError):
            create_root(keys)

    def test_root_with_missing_quorum_rejected(self):
        self.root.signatures = dict(list(self.root.signatures.items())[:1])
        with self.assertRaises(ValueError):
            build_repository(self.base / "bad-root", self.files, self.root, self.keys, version=2)

    def test_expired_root_rejected(self):
        expired = create_root(self.keys, now=datetime.now(timezone.utc) - timedelta(days=366))
        with self.assertRaises(ValueError):
            build_repository(self.base / "expired-root", self.files, expired, self.keys, version=2)

    def test_builder_rejects_unauthorized_signer(self):
        keys = dict(self.keys)
        keys["targets"] = [CryptoSigner.generate_ed25519()]
        with self.assertRaises(ValueError):
            build_repository(self.base / "bad-signature", self.files, self.root, keys, version=2)

    def test_existing_publication_never_overwritten(self):
        with self.assertRaises(FileExistsError):
            build_repository(self.repo, self.files, self.root, self.keys, version=2)

    def test_unsafe_paths_rejected(self):
        for name in ("../secret", "/absolute", "a/../b", "a//b", "a\\b", "a?secret", "a/%2e%2e/b"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                safe_target(name)

    def test_plain_http_and_url_credentials_rejected(self):
        for url in ("http://updates.example.invalid", "https://user:secret@example.invalid", "https://example.invalid?token=secret"):
            with self.subTest(url=url.split(":")[0]), self.assertRaises(ValueError):
                AetherUpdateClient(self.base / "state", self.root.to_bytes(), url)

    def test_cached_file_tampering_cannot_bypass_validation(self):
        client = self.client()
        client.refresh()
        path = client.stage("packages/sample.pkg.tar.gz")
        path.write_bytes(b"tampered")
        self.target_path().write_bytes(b"also tampered")
        with self.assertRaises((exceptions.LengthOrHashMismatchError, exceptions.DownloadLengthMismatchError)):
            client.stage("packages/sample.pkg.tar.gz")


class PackageSignatureTests(unittest.TestCase):
    def test_real_gnupg_package_signature(self):
        gpg = shutil.which("gpg") or "C:/Program Files/Git/usr/bin/gpg.exe"
        gpgv = shutil.which("gpgv") or "C:/Program Files/Git/usr/bin/gpgv.exe"
        if not Path(gpg).is_file() or not Path(gpgv).is_file():
            self.skipTest("GnuPG and gpgv are required")
        with tempfile.TemporaryDirectory(prefix="aether-disposable-signing-") as name:
            base = Path(name)
            home = base / "gnupg"
            home.mkdir(mode=0o700)
            command = [gpg, "--homedir", tool_path(home, gpg), "--batch"]
            # Disposable regression-test key only, never a release key.
            subprocess.run(command + ["--pinentry-mode", "loopback", "--passphrase", "",
                "--quick-generate-key", "Aether DISPOSABLE signing regression test", "ed25519", "sign", "1d"],
                check=True, capture_output=True)
            try:
                listed = subprocess.run(command + ["--with-colons", "--list-keys"], check=True, capture_output=True, text=True)
                fingerprint = next(line.split(":")[9] for line in listed.stdout.splitlines() if line.startswith("fpr:"))
                keyring = base / "public.gpg"
                keyring.write_bytes(subprocess.run(command + ["--export", fingerprint], check=True, capture_output=True).stdout)
                package = base / "aether-signing-smoke-0.1-1-any.pkg.tar.gz"
                with tarfile.open(package, "w:gz") as archive:
                    for path, data in {
                        ".PKGINFO": b"pkgname = aether-signing-smoke\npkgver = 0.1-1\npkgdesc = Disposable signing test\narch = any\nsize = 7\n",
                        "usr/share/aether-signing-smoke/result.txt": b"Aether\n",
                    }.items():
                        info = tarfile.TarInfo(path)
                        info.size, info.mode, info.mtime = len(data), 0o644, 0
                        archive.addfile(info, io.BytesIO(data))
                signature = sign_package(package, home, fingerprint, gpg=gpg)
                verify_package(package, keyring, fingerprint, gpgv=gpgv)
                plan = {"version": 1, "channel": "development", "architecture": "x86_64",
                    "public_keyring": str(keyring), "signer_fingerprint": fingerprint,
                    "packages": [{"name": "aether-signing-smoke", "version": "0.1-1",
                        "archive": str(package), "sha256": hashlib.sha256(package.read_bytes()).hexdigest()}]}
                frozen = base / "frozen"
                frozen.mkdir()
                files = prepare_files(plan, frozen, gpgv=gpgv)
                keys = {role: [CryptoSigner.generate_ed25519()] for role in ROLES}
                keys["root"].append(CryptoSigner.generate_ed25519())
                root = create_root(keys)
                repo = base / "repo"
                build_repository(repo, files, root, keys, version=1)
                client = AetherUpdateClient(base / "client", root.to_bytes(), "https://updates.example.invalid",
                    fetcher=DirectoryFetcher(repo))
                client.refresh()
                catalog = client.catalog("x86_64", "development")
                target = catalog["packages"][0]["target"]
                downloaded = client.stage(target)
                downloaded_signature = client.stage(target + ".sig")
                # ngclient uses URL-encoded local names. Copy to a conventional
                # sibling pair before handing the package to GnuPG/pacman.
                checked = base / "checked.pkg.tar.gz"
                checked.write_bytes(downloaded.read_bytes())
                Path(str(checked) + ".sig").write_bytes(downloaded_signature.read_bytes())
                verify_package(checked, keyring, fingerprint, gpgv=gpgv)
                self.assertEqual(checked.read_bytes(), package.read_bytes())
                with self.assertRaises(ValueError):
                    verify_package(package, keyring, "0" * 40, gpgv=gpgv)
                original = package.read_bytes()
                package.write_bytes(original + b"tampered")
                with self.assertRaises(ValueError):
                    verify_package(package, keyring, fingerprint, gpgv=gpgv)
                package.write_bytes(original)
                signature.unlink()
                with self.assertRaises(ValueError):
                    verify_package(package, keyring, fingerprint, gpgv=gpgv)
            finally:
                gpgconf = str(Path(gpg).with_name("gpgconf.exe" if os.name == "nt" else "gpgconf"))
                subprocess.run([gpgconf, "--homedir", tool_path(home, gpgconf), "--kill", "gpg-agent"], capture_output=True)


class R2TransportTests(unittest.TestCase):
    def test_private_prefix_and_response_close(self):
        class Body:
            closed = False
            def iter_chunks(self, chunk_size):
                yield b"verified by TUF later"
            def close(self):
                self.closed = True
        class S3:
            def get_object(self, **kwargs):
                self.request = kwargs
                self.body = Body()
                return {"Body": self.body}
        s3 = S3()
        fetcher = R2Fetcher(s3, "aether-updates", "repositories/development/x86_64", "https://aether.invalid")
        self.assertEqual(b"".join(fetcher.fetch("https://aether.invalid/metadata/timestamp.json")), b"verified by TUF later")
        self.assertEqual(s3.request, {"Bucket": "aether-updates", "Key": "repositories/development/x86_64/metadata/timestamp.json"})
        self.assertTrue(s3.body.closed)

    def test_other_hosts_and_path_escape_rejected(self):
        fetcher = R2Fetcher(None, "aether-updates", "repositories/development/x86_64", "https://aether.invalid")
        for url in ("https://attacker.invalid/metadata/timestamp.json", "http://aether.invalid/metadata/timestamp.json",
                    "https://aether.invalid/metadata/../secret", "https://aether.invalid/targets/%2e%2e/secret",
                    "https://aether.invalid/private/key", "https://aether.invalid/metadata/timestamp.json?secret=yes"):
            with self.subTest(url=url), self.assertRaises(exceptions.DownloadError):
                list(fetcher.fetch(url))

    def test_not_found_preserves_http_status_without_details(self):
        class NotFound(Exception):
            response = {"ResponseMetadata": {"HTTPStatusCode": 404}}
        class S3:
            def get_object(self, **kwargs):
                raise NotFound("private request details must not be logged")
        fetcher = R2Fetcher(S3(), "aether-updates", "repositories/development/x86_64", "https://aether.invalid")
        with self.assertRaises(exceptions.DownloadHTTPError) as raised:
            list(fetcher.fetch("https://aether.invalid/metadata/2.root.json"))
        self.assertEqual(raised.exception.status_code, 404)
        self.assertNotIn("private request details", str(raised.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
