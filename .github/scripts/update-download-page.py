#!/usr/bin/env python3
"""Build docs/release.json from a GitHub release.

Used by .github/workflows/update-download-page.yml when a release is
published. The download page reads the same manifest at runtime, so the page
itself does not need to be regenerated or edited for each release.

The script uses only the Python standard library so the workflow needs no
extra dependencies. It deliberately fails instead of writing a partial
manifest when the ISO or SHA256SUMS asset is missing.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API_DEFAULT = "https://api.github.com"
ASSET_SUMS = "sha256sums"
CHECKSUM_RE = re.compile(r"^([0-9a-fA-F]{64})\s+\*?(.+?)\s*$")


class ReleaseError(RuntimeError):
    pass


def api_request(url: str, token: str | None) -> bytes:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "aether-download-page",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        detail = error.read(500).decode("utf-8", "replace")
        raise ReleaseError(f"GitHub API returned HTTP {error.code}: {detail}") from error
    except urllib.error.URLError as error:
        raise ReleaseError(f"GitHub API request failed: {error.reason}") from error


def get_release(api: str, repository: str, tag: str | None, token: str | None) -> dict:
    if tag:
        path = f"/repos/{repository}/releases/tags/{urllib.parse.quote(tag, safe='')}"
        release = json.loads(api_request(api + path, token))
    else:
        path = f"/repos/{repository}/releases?per_page=20"
        releases = json.loads(api_request(api + path, token))
        published = [r for r in releases if not r.get("draft") and r.get("published_at")]
        if not published:
            raise ReleaseError("No published release was found.")
        # This intentionally includes prereleases; Aether's current download is
        # a development snapshot and /releases/latest excludes prereleases.
        release = published[0]
    if release.get("draft"):
        raise ReleaseError(f"Release {release.get('tag_name')} is still a draft.")
    if not release.get("published_at"):
        raise ReleaseError(f"Release {release.get('tag_name')} is not published.")
    return release


def find_asset(assets: list[dict], predicate, description: str) -> dict:
    matches = [asset for asset in assets if predicate(asset.get("name", ""))]
    if not matches:
        raise ReleaseError(f"No {description} asset was found in this release.")
    if len(matches) > 1:
        names = ", ".join(asset["name"] for asset in matches)
        raise ReleaseError(f"More than one {description} asset was found: {names}")
    return matches[0]


def parse_checksums(text: str) -> dict[str, str]:
    checksums: dict[str, str] = {}
    for line in text.splitlines():
        match = CHECKSUM_RE.match(line.strip())
        if match:
            digest, name = match.groups()
            checksums[Path(name).name] = digest.lower()
    return checksums


def download_asset(asset: dict, token: str | None) -> bytes:
    return api_request(asset["browser_download_url"], token)


def display_version(tag: str) -> str:
    match = re.match(r"^[vV]?(\d+\.\d+\.\d+)", tag)
    return match.group(1) if match else tag


def build_manifest(release: dict, checksums_text: str) -> dict:
    assets = release.get("assets", [])
    iso = find_asset(
        assets,
        lambda name: name.lower().endswith(".iso") and "x86_64" in name.lower(),
        "x86_64 ISO",
    )
    vm = find_asset(
        assets,
        lambda name: name.lower().endswith((".tar.xz", ".vmdk"))
        and "x86_64" in name.lower()
        and ("vm" in name.lower() or name.lower().endswith(".vmdk")),
        "x86_64 virtual-machine",
    )
    checksums = find_asset(
        assets,
        lambda name: name.lower() == ASSET_SUMS,
        "SHA256SUMS",
    )
    checksum_map = parse_checksums(checksums_text)
    iso_hash = checksum_map.get(iso["name"])
    if not iso_hash:
        raise ReleaseError(f"SHA256SUMS does not contain an entry for {iso['name']}.")
    vm_hash = checksum_map.get(vm["name"])

    def asset_entry(asset: dict, digest: str | None = None) -> dict:
        entry = {
            "name": asset["name"],
            "size": int(asset["size"]),
            "download_url": asset["browser_download_url"],
        }
        if digest:
            entry["sha256"] = digest
        return entry

    tag = release["tag_name"]
    return {
        "tag": tag,
        "name": release.get("name") or tag,
        "display_version": display_version(tag),
        "published_at": release["published_at"],
        "prerelease": bool(release.get("prerelease")),
        "html_url": release["html_url"],
        "assets": {
            "iso": asset_entry(iso, iso_hash),
            "vm": asset_entry(vm, vm_hash),
            "checksums": asset_entry(checksums),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", help="release tag; defaults to the newest published release")
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--api", default=os.environ.get("GITHUB_API_URL", API_DEFAULT))
    parser.add_argument("--token", default=os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"))
    parser.add_argument("--output", type=Path, default=Path("docs/release.json"))
    parser.add_argument("--dry-run", action="store_true", help="print the manifest instead of writing it")
    parser.add_argument("--release-json", type=Path, help="read a saved API response instead of calling GitHub")
    parser.add_argument("--checksums-file", type=Path, help="read saved SHA256SUMS text instead of downloading it")
    args = parser.parse_args()

    if not args.repository and not args.release_json:
        parser.error("--repository or GITHUB_REPOSITORY is required unless --release-json is used")
    try:
        if args.release_json:
            release = json.loads(args.release_json.read_text(encoding="utf-8"))
            if release.get("draft") or not release.get("published_at"):
                raise ReleaseError("The supplied release fixture is not published.")
        else:
            release = get_release(args.api.rstrip("/"), args.repository, args.tag, args.token)
        checksums = find_asset(
            release.get("assets", []),
            lambda name: name.lower() == ASSET_SUMS,
            "SHA256SUMS",
        )
        if args.checksums_file:
            checksums_text = args.checksums_file.read_text(encoding="utf-8")
        else:
            # The release asset is public; do not forward the API token to
            # GitHub's object-storage redirect target.
            checksums_text = download_asset(checksums, None).decode("utf-8")
        manifest = build_manifest(release, checksums_text)
    except (ReleaseError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(f"update-download-page: {error}", file=sys.stderr)
        return 1

    rendered = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if args.dry_run:
        sys.stdout.write(rendered)
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"Wrote {args.output} for {manifest['tag']} ({manifest['assets']['iso']['name']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
