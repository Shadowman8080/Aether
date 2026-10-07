# Optional USB protection

This feature is under development for the next Aether image. It is not included
in the published 0.3.2 image. It stays disabled until an administrator chooses
to enable it.

USBGuard can block newly connected USB devices. It does not establish whether
an allowed device has trustworthy firmware, and it cannot prevent every attack
from a device that imitates an allowed identity.

## Try protection

Open **Aether Settings → USB protection → Try USB protection**. Connect your
trusted keyboard, mouse and other required USB devices first. Authenticate with
your administrator password, then type `TRIAL`.

Aether prepares a policy from the devices currently connected and starts a
60-second trial. Test your keyboard and mouse, then type `KEEP` before the trial
expires. An independent timer restores the previous configuration if you do not
confirm. Canceling also restores it. Existing enabled protection or a custom
policy is preserved rather than replaced.

Only a confirmed trial enables protection on future boots. An interrupted trial
is recovered at startup; device authorization values from an earlier boot are
never applied to newly numbered devices.

## Review a new device

Use `sudo usbguard list-devices` to inspect blocked devices. Verify the physical
device before using `sudo usbguard allow-device DEVICE_ID`. That command grants
access for the current connection; review USBGuard's policy tools separately
when you need a persistent rule. Never blindly allow every blocked device.

## Disable or recover

**Disable on next boot** requires typing `DISABLE`. Protection stays active for
the current session; restart manually when ready.

If input is blocked, append `aether.usbguard=off` to Aether's kernel command line
in GRUB for one boot. This bypasses the USBGuard service. Keep an Aether recovery
ISO available in case you cannot edit the boot entry.

Virtual USB tests cannot certify every physical keyboard, dock, Bluetooth
adapter or USB controller. Always complete the trial on the actual computer
before keeping protection enabled.
