# Media

Every image and video in this directory was recorded from a **live Aether 0.3
virtual machine**, not from mockups, design files or a developer's laptop. There
is no post-processing that changes what the system displayed: no compositing, no
retouching, no staged dialogs, no filler text. Where a frame looks plain, the
frame really was plain.

If a screenshot here contradicts the README, the README is wrong — please open
an issue.

## Screenshots — 33 files, `screenshots/`

Captured from the running guest with VMware's guest screen-capture facility, at
the guest's own framebuffer resolution. Most are 1280x800; a few are 1024x768
(installer and Security Center sessions) and two are the smaller framebuffers
Plymouth and the screensaver preview use.

Files are numbered in capture order, so the sequence roughly follows a session
from desktop → search → AI → installer → boot → lock. There are no gaps.

| | | |
|---|---|---|
| `01-desktop.png` | Desktop | Aether Plasma session, the hero image |
| `02-aurasearch.png` | AuraSearch | Launcher with an inline calculation |
| `03-nimbrel-ai.png` | Nimbrel | A real on-device answer, captured from the video below |
| `04-aurasearch-results.png` | AuraSearch | Search results across apps, files and settings |
| `05-aurasearch-launch.png` | AuraSearch | The launcher, captured from the video below |
| `06-login-greeter.png` | Greeter | The Aether login screen, password masked |
| `07-vector-file-manager.png` | Vector | Browsing `/home/aether` |
| `08-vector-applications.png` | Vector | The installed application grid |
| `09-power-menu.png` | Power menu | Lock, sleep, restart, shut down |
| `10-login-power-menu.png` | Greeter | Power menu reachable before login |
| `11-desktop-session.png` | Desktop | A second desktop session |
| `12-caps-lock-warning.png` | Greeter | Caps Lock warning, password masked |
| `13-shutdown-confirmation.png` | Power menu | Countdown before shutdown |
| `14-vmware-integration.png` | Desktop | VMware guest integration in the panel |
| `15-installer.png` | Installer | Welcome page, with the whole-disk limitation stated |
| `16-installer-welcome.png` | Installer | Welcome page |
| `17-installer-region.png` | Installer | Region, keyboard and time zone |
| `18-installer-account.png` | Installer | Account, LUKS2 and recovery passphrases |
| `19-installer-review.png` | Installer | Review page, `ERASE /dev/vda` confirmation |
| `20-installer-complete.png` | Installer | Installation finished, GRUB installed for both platforms |
| `21-security-center.png` | Security Center | What is working, what is not, what is unverified |
| `22-encrypted-unlock.png` | Boot | LUKS2 unlock prompt for encrypted storage |
| `23-security-encrypted-boot.png` | Boot | Kernel log from an encrypted boot, AppArmor and Landlock present |
| `24-installed-desktop.png` | Desktop | First boot from the installed disk |
| `25-desktop-panels.png` | Desktop | Panel layout |
| `26-lock-screen.png` | Lock screen | The lock screen clock and actions |
| `27-wrong-password.png` | Greeter | "Sign-in failed. Check your credentials" |
| `28-screensavers.png` | Settings | Screen saver previews |
| `29-boot-menu.png` | GRUB | The Aether GRUB menu, UEFI entries |
| `30-boot-splash.png` | Plymouth | The Aether boot splash |
| `31-vector-dark.png` | Vector | Vector in the dark colour scheme |
| `32-kate-editor.png` | Kate | The text editor on a desktop session |
| `33-greeter-current.png` | Greeter | The greeter in its current form |

### No credentials in these images

Screenshots that show a password field show it **masked or empty** — that is the
actual on-screen state. `06`, `12` and `33` show the greeter before a password is
entered; `27` shows a rejected attempt with an empty field and an error message.
No password, token or key appears in any file in this directory.

One installer screenshot shows the throwaway account name used during that test
install. It is a test account on a discarded VM, not a credential.

## Videos — 2 files, `videos/`

Recorded **inside the guest** with `ffmpeg`'s `x11grab` against the live X
display, at 1718x920 / 30 fps. The pointer and keyboard are real synthetic X11
input, so what you see typed is what Nimbrel received.

| | | |
|---|---|---|
| `01-nimbrel-on-device-ai.mp4` | 46 s | Nimbrel answering on-device, no network |
| `02-aurasearch-and-vector.mp4` | 26 s | AuraSearch and Vector |

Both are silent — the capture deliberately drops audio, so there is no
misleading soundtrack.

Video 01 is the important one: it types a question, waits, and shows a real
answer generated on the CPU at roughly 6.6 tokens/sec. **Nothing is pre-baked.**
The video runs against the same Unix-socket path described in
[`../src/nimbrel/README.md`](../src/nimbrel/README.md).

Note the model's answer in the video is **correct but thin** — 0.8B is a small
model. It is shown unedited, because a better-looking answer would misrepresent
what the system actually does. The UI's own *"Check important answers"* label is
visible in the recording.

`03-nimbrel-ai.png` and `05-aurasearch-launch.png` are stills from these two
videos, captured at the frames where the answer and the launcher are fully
rendered. They are the same pixels, not separate staged captures.

## How these were recorded

Reproducible in outline, if you want to make your own:

1. Boot the 0.3 image in a VM, log in, and unlock the session.
2. **Screenshots** — `vmrun captureScreen` against the running guest, which grabs
   the framebuffer directly. No screenshot key, no scaling, no recompression
   beyond PNG.
3. **Videos** — start `ffmpeg -f x11grab -draw_mouse 1 -framerate 30
   -video_size 1718x920 -i :0`, run a scripted scene, then stop the encoder
   cleanly so the file is playable.
4. **Synthetic input** — Aether ships no `xdotool` and has no package manager, so
   pointer and keyboard events were driven through `libXtst` via a small Python
   ctypes script. It is a real X11 input client; it just has no GUI of its own.
5. **Transcode** — the guest's ffmpeg has no H.264 encoder, so the VP9 capture
   was transcoded to H.264/AAC MP4 on the host for the widest browser support.

Screen text was verified by OCR rather than by eye, so captions in this file
match what the images actually say.

## Licensing

These images and videos are part of Aether's own work and are covered by the
repository's **GPL-3.0-or-later** licence, the same as the rest of the tree.
They contain no third-party artwork: the wallpapers, colour schemes and UI
elements in them are Aether's own, shipped in [`../src/assets/`](../src/assets/).

The model weights shown in video 01 are **not** included. They are pinned by
digest in [`../src/nimbrel/model.json`](../src/nimbrel/model.json) and remain
Apache-2.0 upstream.


## Audio: Aether Glass

`audio/aether-glass-preview.wav` is an original synthesized listening preview,
not a VM recording. It contains ten excerpts separated by silence: login,
logout, information, warning, error, email, device connection, low battery,
completion, and assistant completion. It is generated by
`src/sounds/generate.py` and covered by GPL-3.0-or-later. No external audio
samples are used. Playback through the running VM remains unverified.
