#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Install and select Aether Glass for the current desktop user. No root required."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import wave

THEME = "AetherGlass"


def locations():
    data = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    state = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "aether-sounds"
    if not data.is_absolute() or not state.is_absolute():
        raise ValueError("XDG data and state directories must be absolute")
    return data, state


def validate(root):
    root = Path(root)
    if root.is_symlink():
        raise ValueError("A sound theme must not be a symbolic link")
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("theme") != THEME or len(manifest.get("sounds", [])) != 42:
        raise ValueError("Unexpected sound-theme manifest")
    seen = set()
    for entry in manifest["sounds"]:
        name = entry["event"]
        if not name or any(c not in "abcdefghijklmnopqrstuvwxyz-" for c in name) or name in seen:
            raise ValueError("Invalid or duplicate sound event")
        seen.add(name)
        if entry["file"] != "stereo/" + name + ".wav":
            raise ValueError("Invalid sound path")
        path = root / entry["file"]
        if path.is_symlink() or path.parent.is_symlink():
            raise ValueError("Symbolic links are not allowed in a sound theme")
        raw = path.read_bytes()
        if len(raw) > 2_000_000 or hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise ValueError("Sound checksum or size mismatch: " + name)
        with wave.open(str(path), "rb") as f:
            if (f.getnchannels(), f.getsampwidth(), f.getframerate(), f.getcomptype()) != (1, 2, 48000, "NONE"):
                raise ValueError("Unexpected audio format: " + name)
    expected = {"index.theme", "manifest.json", "COPYING", "generate.py"} | {x["file"] for x in manifest["sounds"]}
    if any(p.is_symlink() for p in root.rglob("*")):
        raise ValueError("Symbolic links are not allowed in a sound theme")
    if {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()} != expected:
        raise ValueError("Unexpected files in theme")
    if "Name=Aether Glass" not in (root / "index.theme").read_text(encoding="utf-8"):
        raise ValueError("Missing theme identity")
    return manifest


def installed_theme():
    data, _ = locations()
    roots = [data] + [Path(p) for p in os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(os.pathsep) if p]
    for root in roots:
        theme = root / "sounds" / THEME
        if root.is_absolute() and (theme / "manifest.json").is_file():
            return theme
    raise RuntimeError("Aether Glass is not installed")


def kde_read(key, default):
    tool = shutil.which("kreadconfig6")
    if not tool:
        raise RuntimeError("kreadconfig6 is required; choose Aether Glass in System Settings instead")
    return subprocess.check_output([tool, "--file", "kdeglobals", "--group", "Sounds",
                                    "--key", key, "--default", default], text=True, timeout=10).strip()


def kde_write(key, value):
    tool = shutil.which("kwriteconfig6")
    if not tool:
        raise RuntimeError("kwriteconfig6 is required; choose Aether Glass in System Settings instead")
    args = [tool, "--file", "kdeglobals", "--group", "Sounds", "--key", key]
    help_text = subprocess.check_output([tool, "--help"], text=True, timeout=10)
    if "--notify" in help_text:
        args.append("--notify")
    if key == "Enable":
        args.extend(["--type", "bool"])
    subprocess.run(args + [value], check=True, timeout=10)


def save_state(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise ValueError("Refusing a symbolic-link state file")
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=".state-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(value, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def activate():
    data, state = locations()
    validate(installed_theme())
    previous = state / "previous-theme.json"
    if not previous.exists():
        save_state(previous, {"Theme": kde_read("Theme", "ocean")})
    kde_write("Theme", THEME)
    # Deliberately preserve Sounds/Enable, DND, event preferences and device volume.


def install(source):
    validate(source)
    data, _ = locations()
    parent = data / "sounds"
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / THEME
    if target.is_symlink():
        raise ValueError("Refusing to replace a symbolic-link theme directory")
    with tempfile.TemporaryDirectory(prefix=".aether-sounds-", dir=parent) as temp:
        staged = Path(temp) / THEME
        shutil.copytree(source, staged)
        validate(staged)
        backup = None
        if target.exists():
            backup = parent / (".AetherGlass.backup-" + str(time.time_ns()))
            target.rename(backup)
        try:
            staged.rename(target)
        except Exception:
            if backup:
                backup.rename(target)
            raise
    applications = data / "applications"
    applications.mkdir(parents=True, exist_ok=True)
    desktop = applications / "org.aether.Sounds.desktop"
    if desktop.is_symlink():
        raise ValueError("Refusing a symbolic-link desktop entry")
    desktop.write_text("[Desktop Entry]\nType=Application\nName=Aether Sounds\n"
        "Comment=Choose, preview or mute desktop sound effects\n"
        "Exec=kcmshell6 kcm_soundtheme\nTryExec=kcmshell6\n"
        "Icon=preferences-desktop-sound\nTerminal=false\nCategories=Settings;AudioVideo;\n",
        encoding="utf-8")
    print("Installed:", target)
    if backup:
        print("Previous theme files preserved:", backup)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--install", type=Path, metavar="THEME_DIRECTORY")
    group.add_argument("--activate", action="store_true")
    group.add_argument("--mute", action="store_true")
    group.add_argument("--unmute", action="store_true")
    group.add_argument("--restore", action="store_true")
    group.add_argument("--status", action="store_true")
    group.add_argument("--preview", metavar="EVENT")
    args = p.parse_args()
    if sys.platform != "linux":
        p.error("Installation and desktop controls must run inside Aether/Linux")
    if os.geteuid() == 0:
        p.error("Run this as your desktop user, without sudo")
    data, state = locations()
    if args.install:
        install(args.install)
    elif args.activate:
        activate()
        print("Aether Glass selected. Existing mute and volume settings preserved.")
    elif args.mute or args.unmute:
        kde_write("Enable", "false" if args.mute else "true")
    elif args.restore:
        previous = json.loads((state / "previous-theme.json").read_text(encoding="utf-8"))
        kde_write("Theme", previous["Theme"])
    elif args.status:
        try:
            installed = installed_theme().is_dir()
        except RuntimeError:
            installed = False
        print(json.dumps({"theme": kde_read("Theme", "ocean"), "enabled": kde_read("Enable", "true"),
                          "installed": installed}))
    elif args.preview:
        theme = installed_theme()
        manifest = validate(theme)
        sound = next((x for x in manifest["sounds"] if x["event"] == args.preview), None)
        if sound is None:
            raise ValueError("Unknown sound event")
        player = shutil.which("pw-play") or shutil.which("paplay")
        if not player:
            raise RuntimeError("Neither pw-play nor paplay is installed")
        subprocess.run([player, str(theme / sound["file"])], check=True, timeout=15)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print("Aether Sounds:", error, file=sys.stderr)
        sys.exit(1)
