#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Synthesize Aether Glass from original note recipes; no sampled audio."""
import argparse
import array
import concurrent.futures
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import wave

RATE = 48000
THEME = "AetherGlass"
# Event name, MIDI notes, note spacing, note decay, timbre, peak dBFS.
BANK = [
    ("desktop-login", [62, 69, 74, 78], .16, .9, "glass", -12),
    ("desktop-logout", [74, 69, 62], .15, .65, "soft", -15),
    ("desktop-screen-lock", [69, 62], .08, .28, "soft", -17),
    ("desktop-screen-unlock", [62, 69], .09, .35, "glass", -16),
    ("system-ready", [62, 74], .18, .55, "glass", -14),
    ("system-bootup", [50, 62, 69, 74], .2, .95, "soft", -14),
    ("system-shutdown", [74, 69, 62, 50], .17, .7, "soft", -15),
    ("dialog-information", [74, 81], .085, .35, "glass", -16),
    ("dialog-question", [69, 74], .11, .4, "soft", -15),
    ("dialog-warning", [66, 62, 66], .16, .3, "round", -13),
    ("dialog-error", [62, 58], .13, .38, "round", -12),
    ("dialog-ok", [69, 74, 78], .065, .3, "glass", -16),
    ("dialog-cancel", [69, 62], .065, .23, "soft", -18),
    ("message", [81], .1, .4, "glass", -17),
    ("message-new-instant", [78, 81], .075, .3, "glass", -17),
    ("message-new-email", [74, 78, 81], .1, .38, "glass", -16),
    ("message-sent-instant", [69, 74], .055, .22, "soft", -18),
    ("device-added", [62, 74], .085, .32, "round", -16),
    ("device-removed", [74, 62], .085, .3, "round", -16),
    ("network-connectivity-established", [62, 69, 74], .06, .28, "soft", -17),
    ("network-connectivity-lost", [74, 66], .1, .35, "round", -15),
    ("network-connectivity-error", [66, 58], .13, .33, "round", -13),
    ("power-plug", [50, 62, 69], .05, .35, "soft", -17),
    ("power-unplug", [69, 62, 50], .06, .3, "soft", -18),
    ("battery-caution", [62, 66], .18, .35, "round", -15),
    ("battery-low", [66, 62, 66, 62], .2, .32, "round", -12),
    ("battery-full", [69, 74, 81], .09, .38, "glass", -17),
    ("power-unplug-battery-low", [69, 62, 58], .18, .4, "round", -12),
    ("suspend-start", [69, 62, 50], .12, .45, "soft", -18),
    ("suspend-resume", [50, 62, 69], .12, .5, "glass", -16),
    ("suspend-error", [66, 58, 62], .15, .4, "round", -13),
    ("software-update-available", [62, 66, 69, 74], .075, .4, "glass", -16),
    ("software-update-urgent", [66, 69, 66, 74], .16, .4, "round", -13),
    ("complete", [62, 69, 78], .1, .5, "glass", -15),
    ("trash-empty", [74, 69, 62], .045, .18, "round", -20),
    ("screen-capture", [86, 74], .025, .12, "glass", -20),
    ("bell", [74], .1, .55, "glass", -16),
    ("alarm-clock-elapsed", [74, 81, 74, 81], .25, .35, "round", -12),
    ("aether-search-open", [74, 81], .045, .18, "soft", -20),
    ("aether-assistant-complete", [69, 74, 81], .09, .45, "glass", -16),
    ("button-toggle-on", [74, 81], .035, .12, "round", -22),
    ("button-toggle-off", [81, 74], .035, .12, "round", -22),
]


def synth(recipe):
    name, notes, spacing, decay, voice, peak_db = recipe
    duration = (len(notes) - 1) * spacing + decay + .18
    values = [0.0] * round(duration * RATE)
    partials = {"soft": [(1, 1), (2, .10)],
                "glass": [(1, 1), (2, .17), (3, .055)],
                "round": [(1, 1), (2, .19), (3, .08)]}[voice]
    for number, note in enumerate(notes):
        frequency = 440 * 2 ** ((note - 69) / 12)
        start = round(number * spacing * RATE)
        for i in range(round(decay * RATE)):
            t = i / RATE
            attack = min(t / .012, 1)
            release = min((decay - t) / .065, 1)
            envelope = math.sin(attack * math.pi / 2) ** 2 * release ** 2 * math.exp(-4.5 * t / decay)
            value = sum(gain * math.sin(2 * math.pi * frequency * ratio * t)
                        for ratio, gain in partials) * envelope
            values[start + i] += value
            # A short, quiet, fixed echo gives the theme space without long tails.
            echo = start + i + round(.071 * RATE)
            if echo < len(values):
                values[echo] += value * .12
    scale = 10 ** (peak_db / 20) * 32767 / max(map(abs, values))
    pcm = array.array("h", (round(v * scale) for v in values))
    pcm[0] = pcm[-1] = 0
    if sys.byteorder != "little":
        pcm.byteswap()
    return name, pcm.tobytes(), duration, peak_db


def write_wav(path, data):
    with wave.open(str(path), "wb") as stream:
        stream.setparams((1, 2, RATE, 0, "NONE", "not compressed"))
        stream.writeframes(data)


def generate(destination, jobs=1):
    root = Path(destination) / THEME
    audio = root / "stereo"
    audio.mkdir(parents=True, exist_ok=True)
    records = []
    if jobs > 1:
        with concurrent.futures.ProcessPoolExecutor(max_workers=min(jobs, len(BANK))) as pool:
            rendered = list(pool.map(synth, BANK))
    else:
        rendered = list(map(synth, BANK))
    for name, pcm, duration, peak in rendered:
        path = audio / (name + ".wav")
        write_wav(path, pcm)
        records.append({"event": name, "file": "stereo/" + path.name,
                        "duration_seconds": round(duration, 3), "peak_dbfs": peak,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    (root / "index.theme").write_text(
        "[Sound Theme]\nName=Aether Glass\nComment=Original, quiet chimes for the Aether desktop\n"
        "Inherits=freedesktop\nDirectories=stereo\nExample=desktop-login\n\n"
        "[stereo]\nOutputProfile=stereo\n", encoding="utf-8")
    source = Path(__file__).resolve()
    license_file = next((p for p in (source.with_name("COPYING"), source.with_name("LICENSE"),
                                    source.parents[2] / "LICENSE") if p.is_file()), None)
    if license_file is None:
        raise ValueError("The GPL licence text must accompany the generator")
    (root / "COPYING").write_bytes(license_file.read_bytes())
    (root / "generate.py").write_bytes(source.read_bytes())
    (root / "manifest.json").write_text(json.dumps({"theme": THEME, "version": "0.1.0",
        "license": "GPL-3.0-or-later", "sample_rate": RATE, "channels": 1,
        "sounds": records}, indent=2) + "\n", encoding="utf-8")
    # Native preview, with silence between excerpts. No spoken or borrowed samples.
    selected = {"desktop-login", "dialog-information", "dialog-warning", "dialog-error",
                "message-new-email", "device-added", "battery-low", "complete",
                "aether-assistant-complete", "desktop-logout"}
    medley = b"".join(pcm + b"\0\0" * (RATE // 3)
                       for name, pcm, _, _ in rendered if name in selected)
    write_wav(Path(destination) / "aether-glass-preview.wav", medley)
    return root


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    print(generate(args.output, args.jobs))
