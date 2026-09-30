"""Verify Aether update metadata and stage artifacts, without installing them."""
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from tuf.ngclient import Updater, UpdaterConfig

from repository import safe_target

POLICY = {"automatic_checks": True, "automatic_installation": False, "automatic_restart": False}


class AetherUpdateClient:
    def __init__(self, state: Path, pinned_root: bytes, base_url: str, *, fetcher=None,
                 allow_local_test=False):
        parsed = urlsplit(base_url)
        local = allow_local_test and parsed.hostname in ("localhost", "127.0.0.1", "::1")
        if (parsed.scheme != "https" and not (local and parsed.scheme == "http")) or not parsed.hostname:
            raise ValueError("HTTPS is required")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Credentials, queries and fragments are forbidden in repository URLs")
        if state.is_symlink():
            raise ValueError("Update state must not be a symlink")
        state.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name == "posix":
            st = state.stat()
            if st.st_uid != os.geteuid() or st.st_mode & 0o077:
                raise PermissionError("Update state must be owned by the caller with mode 0700")
        metadata = state / "metadata"
        self.downloads = state / "downloads"
        for p in (metadata, self.downloads):
            if p.is_symlink():
                raise ValueError("Update directories must not be symlinks")
            p.mkdir(exist_ok=True, mode=0o700)
        # The bootstrap is supplied out of band (eventually embedded in the ISO).
        # Never obtain first trust from the same server being authenticated.
        self.updater = Updater(str(metadata), base_url.rstrip("/") + "/metadata/",
            target_dir=str(self.downloads), target_base_url=base_url.rstrip("/") + "/targets/",
            fetcher=fetcher, bootstrap=pinned_root, config=UpdaterConfig())
        self.refreshed = False

    def refresh(self):
        self.refreshed = False
        self.updater.refresh()
        self.refreshed = True

    def stage(self, name: str) -> Path:
        if not self.refreshed:
            raise RuntimeError("A successful metadata refresh is required first")
        safe_target(name)
        info = self.updater.get_targetinfo(name)
        if info is None:
            raise ValueError("Artifact is not authorized by signed metadata")
        cached = self.updater.find_cached_target(info)
        result = Path(cached or self.updater.download_target(info))
        # Verify again before returning a previously cached file.
        with result.open("rb") as stream:
            info.verify_length_and_hashes(stream)
        return result

    def catalog(self, architecture: str, channel: str) -> dict:
        result = json.loads(self.stage("aether/catalog.json").read_text())
        if result.get("schema") != 1 or result.get("architecture") != architecture or result.get("channel") != channel:
            raise ValueError("Catalog schema, architecture or channel mismatch")
        return result
