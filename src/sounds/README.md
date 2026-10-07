# Aether Glass

**A softer sound for Aether.** Forty-two original, short effects: warm startup
chimes, light notification tones, and distinct warning and error cues.

The sounds are synthesized from the note recipes in `generate.py`. No samples
from macOS, Windows, commercial sound libraries, recordings or AI services are
used. The generator and generated theme are GPL-3.0-or-later.

## Build

Python 3, standard library only. No compiler, downloaded dependencies or model
weights are needed. The default generator uses the available CPUs.

```sh
python3 src/sounds/generate.py --output /tmp/aether-sounds
python3 src/sounds/test_sounds.py
```

Output includes an XDG sound theme, its source and licence, a checksum manifest,
and a short listening preview. WAV files are 48 kHz, 16-bit mono; the `stereo`
theme directory is the standard output-profile lookup location, not a claim
that the files have two channels. Peak levels range from -22 to -12 dBFS.
Device volume still determines listening loudness.

## Install in your running Aether session

Run as your desktop user, **without sudo**. This changes user files and the
selected sound theme; it does not modify a virtual disk from the host, restart
the desktop, change the firewall or change the master speaker volume.

```sh
python3 src/sounds/manage.py --install /tmp/aether-sounds/AetherGlass
python3 src/sounds/manage.py --activate
python3 src/sounds/manage.py --status
```

Open **Aether Sounds** from Vector/AuraSearch, or use Plasma's **System Settings
→ Sound Theme**, to select and preview the theme. Use the system audio controls
for volume and the notification settings for individual application events.
The existing global sound-enabled/muted setting is preserved on activation.

```sh
python3 src/sounds/manage.py --preview desktop-login
python3 src/sounds/manage.py --mute
python3 src/sounds/manage.py --unmute
python3 src/sounds/manage.py --restore
```

An explicit `--preview` plays the requested WAV at the current device volume;
it is a listening test, independent of notification muting. `--restore` restores
the theme that was selected before the first activation, without changing mute
or volume preferences. Upgrading an existing Aether Glass installation preserves
its old files in a timestamped `.AetherGlass.backup-*` sibling directory.

## The sound palette

- **Sessions:** login, logout, lock, unlock, startup, ready and shutdown.
- **Notifications:** information, question, warning, error, confirmation, cancel,
  message, instant message, email and sent message.
- **Devices and connectivity:** device connected/disconnected, network restored,
  lost and failed.
- **Power:** plugged/unplugged, battery caution/low/full, unplugged with low
  battery, suspend/resume and suspend failure.
- **Work:** updates available/urgent, completion, empty trash, screen capture,
  bell and alarm.
- **Optional Aether cues:** search opened, assistant response complete, toggle
  on and toggle off.

## What this does and does not enable

This is a **theme**, not an event-monitoring daemon. Standard event names follow
the [freedesktop sound naming specification](https://specifications.freedesktop.org/sound-naming-spec/latest/).
Applications must request an event for it to play. KDE's existing notification
policies remain in charge, including quiet mode where supported by that app.
No always-on keyboard, mouse, menu, search or per-token AI sound hooks are added.
The two `aether-*` cues are available assets; applications do not emit them yet.
An early-boot or shutdown sound is not promised merely because its file exists.

The preview pack is architecture-independent data. That does **not** establish
ARM or 32-bit desktop support. It is not a signed OS update, and this change does
not make Aether's production updater complete.

## Validation

Automated tests cover all 42 unique files, format, duration, digital peak level,
silent tails, DC offset, sample discontinuities, tampering and path rejection,
upgrade backup preservation, and preservation of the previous theme and mute
setting. Desktop activation and actual audio output must additionally be tested
inside Aether. See the current delivery notes for that deployment status.
