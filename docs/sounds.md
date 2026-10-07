# Aether sound theme — development status

Aether Glass adds 42 original effects, generated from source with Python's
standard library. It integrates with Plasma's existing sound-theme controls.

- Source, build and installation: [src/sounds](../src/sounds/README.md)
- Listening preview: [Aether Glass WAV](../media/audio/aether-glass-preview.wav)
- No external samples, no network service, no change to the master volume.
- Existing mute settings are preserved; no constant click or typing sounds.
- Asset generation and eight automated tests passed on Windows on 2026-10-06.
- Guest audio playback is not yet confirmed.
- Unified image rebuild status is in [release verification](release-20261006.md).

This status is intentionally separate from source availability: publishing the
sound pack is not proof that it has been installed or heard in a guest VM.
