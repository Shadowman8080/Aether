# VMware and VirtualBox guest compatibility

What the Aether 0.3 image provides inside a virtual machine, and how to install
the vendor tools. Kernel drivers are part of the image; the vendor userspace is
not installed by default.

## Kernel drivers (built in)

`build-desktop-kernel.sh` builds and *asserts* these options, so an image that
misses one fails its kernel stage instead of shipping silently:

| Option | What it provides |
| --- | --- |
| `CONFIG_MOUSE_PS2_VMMOUSE=y` | absolute pointer: cursor crosses the VM boundary without Ctrl+Alt |
| `CONFIG_VMWARE_VMCI=y` | VMware host/guest RPC channel used by vmtoolsd |
| `CONFIG_VMWARE_VMCI_VSOCKETS=y`, `CONFIG_VSOCKETS=y` | vsock transport for guest operations |
| `CONFIG_VMWARE_BALLOON=y` | memory balloon driver, lets the host reclaim guest RAM |
| `CONFIG_VMXNET3=m` | VMware paravirtual network adapter |
| `CONFIG_DRM_VMWGFX=m` | VMware SVGA/KMS display driver, resizing and 3D |
| `CONFIG_VBOXGUEST=y` | VirtualBox guest core, shared folders and guest properties |
| `CONFIG_VBOXSF_FS=y` | VirtualBox shared folders |
| `CONFIG_DRM_VBOXVIDEO=y` | VirtualBox display resizing and KMS |

Display, mouse integration, networking and shared folders work with these alone.
Clipboard sharing, drag-and-drop and dynamic resizing of the *desktop* need the
vendor userspace below.

## Installing the vendor tools

The image ships a build-ready kernel tree, because both installers compile
modules against the running kernel:

- `/usr/src/linux-6.18.54` — the exact source plus `Module.symvers`, `.config`
  and generated headers from the build that produced the running kernel
  (installed by `scripts/install-guest-build-support.sh`)
- `/usr/lib/modules/6.18.54-aether3/build` and `.../source` — symlinks the
  installers look for
- `gcc`, `make`, `perl`, `pkg-config` and the X11/xcb development headers

### VirtualBox Guest Additions

Mount the Guest Additions ISO inside the guest and run:

```sh
sudo ./VBoxLinuxAdditions.run
```

`vboxguest`, `vboxsf` and `vboxvideo` already exist in the kernel, so the
installer only builds its userspace (`VBoxService`, `VBoxClient`,
`mount.vboxsf`). If it warns that the X11 drivers were skipped, the Xorg server
headers are absent; the desktop itself keeps working through `vboxvideo` KMS,
and clipboard support still comes from `VBoxClient`.

Host side, for the features to reach the guest: enable **Shared Clipboard =
Bidirectional**, **Drag and Drop = Bidirectional**, **Mouse Integration**, and
select **VMSVGA** graphics.

### VMware Tools

Either install the distribution package build of open-vm-tools, or run the
installer shipped with VMware:

```sh
sudo ./vmware-install.pl --default
```

The first boot already selects the **X11** session under VMware, because
open-vm-tools clipboard and drag-and-drop exist only in X11; Wayland gets
neither. After installing, `aether-vmware-tools` reports what is present:

```sh
aether-vmware-tools            # hypervisor, components, services, session
sudo aether-vmware-tools enable  # start services, select the X11 session
aether-vmware-tools check      # exit non-zero unless integration is active
```

`aether-vmware-tools` only inspects and enables; it installs nothing and makes
no network request. When open-vm-tools is absent the image stage prints a
warning and continues instead of failing the build.

## Live ISO versus installed system

The live ISO mounts its root as a read-only squashfs. Installing either vendor
toolset there compiles modules into a filesystem that disappears on reboot, so
run the installer on the installed system (or accept that the live session
loses it). The kernel drivers, display, pointer and networking work in both.

VirtualBox's default **VMSVGA** graphics adapter is driven by `vmwgfx`, the same
driver used for VMware; `vboxvideo` covers the older VBoxSVGA/VBoxVGA choice.

## Status

Kernel options are configured but the final image has not been booted with
them, and neither installer has been run inside Aether. Treat this as
implemented, not certified. The image still ships no open-vm-tools or
VirtualBox userspace; the session configuration degrades to a warning when
those components are absent instead of failing the build.
