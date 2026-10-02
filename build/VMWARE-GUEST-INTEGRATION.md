# VMware guest integration

How Aether behaves inside VMware Workstation, ESXi or Fusion, and what is
required for copy/paste, drag-and-drop and the seamless pointer.

## Components

- **open-vm-tools 13.1.0-25218885**, source-built (see `build/GUEST-BUILDS.md`).
  - Graphless/console and ARM64 images use the package with `--without-x`.
  - The graphical x86/x86_64 image adds the GTK3 desktop plugins
    (`libdndcp.so`, `libresolutionSet.so`) and `/usr/bin/vmware-user-suid-wrapper`.
- **vmtoolsd.service** and **vmware-vmblock.service** start only when
  `systemd-detect-virt --vm` reports `vmware`.
- **`/usr/bin/aether-vmware-tools`** reports the integration state and, with
  `enable`, starts the services and selects the X11 session. It installs nothing
  and makes no network request.

## Session requirement: X11

Host <-> guest copy/paste and drag-and-drop in open-vm-tools use the X11
selection/clipboard model. They do **not** work in a Wayland session; this is an
upstream limitation (open-vm-tools issues #660, #721, #792; KDE bug 510225), not
an Aether defect. Installing any VMware Tools variant does not change it.

Aether therefore runs the X11 session on VMware:

- The greeter preselects `plasmax11` when `/sys/class/dmi/id/sys_vendor`
  contains `VMware`.
- `/usr/libexec/aether-guest-display-setup` writes
  `/etc/lightdm/lightdm.conf.d/60-aether-vmware-session.conf` before LightDM
  starts, pinning the default session to X11 on VMware.
- `/usr/bin/aether-vmware-tools enable` writes the same default again, so a
  user who has drifted to Wayland can recover with one command.
- LightDM stores the last chosen session per user in `~/.dmrc` as `Session=`
  (capital S), and that value overrides the seat default. A guest that once
  logged in to Wayland therefore keeps starting Wayland no matter what the
  seat default says. On VMware, both `/usr/libexec/aether-guest-display-setup`
  (at LightDM start) and `aether-vmware-tools enable` rewrite `<home>/.dmrc`
  `Session=` to the X11 key, so a saved Wayland choice cannot keep clipboard
  broken. This is the bug that produced the first support report.

The desktop integration autostarts through
`/etc/xdg/autostart/vmware-user.desktop`, whose `Exec` is
`/usr/bin/aether-vmware-session`. That wrapper exits unless the hypervisor is
VMware and the session type is `x11`, then executes
`/usr/bin/vmware-user-suid-wrapper`.

## Seamless pointer

The ungrabbed pointer (the cursor crossing between host and guest without
Ctrl+Alt) needs the absolute-pointer device that the hypervisor exposes.

Aether enables the **in-kernel** driver:

```
CONFIG_MOUSE_PS2_VMMOUSE=y
```

in every x86/x86_64 guest kernel configuration and enforces it in the kernel
build scripts. The kernel driver works with `xf86-input-libinput` in both X11
and Wayland.

The userspace `xf86-input-vmmouse` driver is intentionally **not** built. It is
not in BLFS 13.1, and upstream's `MOUSE_PS2_VMMOUSE` help text requires that the
kernel driver and the userspace driver not be mixed. The userspace driver is
also x86-only.

The option depends on `X86 && HYPERVISOR_GUEST`, so it cannot be enabled on
ARM64. ARM64 guest images have no seamless pointer; use Ctrl+Alt to release the
pointer.

## Using `aether-vmware-tools`

```sh
aether-vmware-tools            # status: components, services, session
sudo aether-vmware-tools enable  # start services, select the X11 session
aether-vmware-tools check      # exit non-zero unless integration is active
```

Typical results:

- `MISSING .../libdndcp.so` on a console or ARM64 image is expected: those
  profiles build open-vm-tools without X11 and have no clipboard feature.
- `user daemon: not running` in an X11 session means the session autostart did
  not run; `sudo aether-vmware-tools enable`, then log out and back in.
- `XDG_SESSION_TYPE: wayland` is the one case no VMware tool can fix. Log out and
  choose the X11 entry.

## Verification (not yet run on this change)

Changing a kernel configuration requires a kernel and image rebuild. After
rebuilding, verify:

1. `grep -qx 'CONFIG_MOUSE_PS2_VMMOUSE=y' /boot/config-$(uname -r)`.
2. Boot in VMware. The greeter's session list shows `aether` (X11) selected.
3. `aether-vmware-tools check` prints `PASS`.
4. Paste host -> guest and guest -> host, and drag a file both ways.
5. Move the pointer across the VM boundary; it should cross without Ctrl+Alt.

Until this is run and recorded, treat the integration as implemented but not
certified. Do not claim physical-hardware or non-VMware hypervisor support.

## Shared folders

`vmhgfs-fuse` is present in every profile. `build/next` also ships
`aether-mount-share`, which mounts a named host share under
`/mnt/aether-shares/`. Aether shares no folder automatically.
