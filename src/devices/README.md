# Aether Devices — plug-and-play device management

Aether Devices is Aether's answer to the **Windows Device Manager**. It is not
a driver store: drivers in Aether are kernel modules, loaded automatically by
systemd-udev when a device appears (modalias → modprobe). Aether Devices is the
human interface to that same udev device tree — plus the desktop plumbing that
makes hotplug feel like Windows.

## What is delivered in this tree

| Piece | Location on a built image |
|---|---|
| `aether-devices` | device manager GUI (`/usr/bin/aether-devices`) |
| `aether-device-notify` | hotplug notification helper (`/usr/bin/aether-device-notify`) |
| `60-aether-pnp.rules` | udev policy (`/etc/udev/rules.d/`) |
| `aether-pnp.conf` | static module list (`/etc/modules-load.d/`) |
| `aether-device-rescan` | "Scan for hardware changes" helper (`/usr/libexec/`) |
| `org.aether.devices.desktop` | app menu entry (`/usr/share/applications/`) |
| `aether-device-notify.desktop` | session autostart (`/etc/xdg/autostart/`) |

### The manager (`main.cpp`)

Qt Widgets application with no privilege requirement for reading:

- **Device tree.** Enumerated live from `udevadm info -e` and grouped by class
  (Storage, Network, Sound, Input, Cameras, Graphics, USB, PCI, Serial, sensors
  and everything else) exactly the way Windows groups a device tree by type.
- **Properties panel.** Every udev property of the selected device, plus its
  sysfs `devpath`/devnode/class in the tree tooltip.
- **Live refresh.** A `udevadm monitor --property` netlink stream drives a
  debounced re-enumeration, so the tree tracks plug/unplug in real time.
- **Hotplug log.** The raw add/remove/change events, timestamped, in a
  toggleable panel.
- **Scan for hardware changes.** `pkexec /usr/libexec/aether-device-rescan`
  re-triggers udev for every subsystem and device (`udevadm trigger` +
  `udevadm settle`) — the Windows Device Manager menu item, verbatim.
- **Export.** Selected device properties can be saved, for bug reports.

### The notifier (`notify/main.cpp`)

A quiet session helper, started from `/etc/xdg/autostart/`. It watches the
same udev stream and posts an `org.freedesktop.Notifications` toast on
device connect/disconnect. Kernel-virtual and bus-internal events
(`usb_interface` under a `usb_device`) are suppressed, and toasts are
rate-limited, so a physical plug produces exactly one friendly message.

### udev policy (`60-aether-pnp.rules`)

Tags hotplug devices for the Aether layer, exposes all partitions of removable
block media (`OPTIONS+="all_partitions"`), and keeps joystick nodes in the
login seat. It deliberately does not try to load drivers — systemd's own rule
set already turns a hotplug event into a `modprobe` by modalias; our rule set
must never fight that.

### Kernel side

`build/desktop/configs/kernel-pnp.delta.config` is merged by
`build-desktop-kernel.sh` ahead of `make olddefconfig` (applied through the
kernel's own `scripts/config` tool) and covers the Windows-familiar device
classes that
were missing from the guest profile: USB Video Class webcams, USB serial
converters (FTDI/PL2303/CH34x, ACM), SD/MMC card readers, NTFS/exFAT
filesystems for removable media, Thunderbolt/USB4 docks, the CMOS RTC and
joysticks. Modules are `=m` where the driver is hotpluggable, so udev only
loads a driver when the matching device is present.

### Build wiring

`build-aether-devices.py` cross-compiles the two binaries in the native build
root (Qt6, Widgets/DBus, `-fstack-protector-strong`, `-Wl,-z,relro,-z,now`)
and copies the assets to their image paths. `build-desktop-pnp-utils.py` builds
`pciutils` (lspci) and `usbutils` (lsusb) from the pinned sources so the
console has canonical PCI/USB naming too. Both recipes are invoked from
`build-desktop-apps.py` after the Plasma round. `build-desktop-iso.sh`
regenerates the binary hardware database (`systemd-hwdb update`) inside the
image root before squashing, so `hwdata` + systemd's udev hwdb entries are
merged into `/usr/lib/udev/hwdb.bin` for offline device naming.

`src/devices/aether-devices/` is the source of record; `build/desktop/devices/`
is the build-tree copy the native recipe stages (the same convention the
`vector` desktop app uses).

## Honest status

- The source, recipes, rules and documentation are implemented.
- Nothing in this tree has been compiled yet — like the rest of Aether, the
  desktop build and the ISO rewrite happen on the Linux build host, and the
  resulting image needs boot-time verification.
- Device naming quality depends on `hwdata` and the hardware databases; actual
  hardware testing is still required (see `docs/roadmap.md`).