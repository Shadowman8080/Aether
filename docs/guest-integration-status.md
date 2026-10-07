# Guest integration status

The source tree bundles open-vm-tools desktop integration and VirtualBox Guest
Additions. Their presence in source does not prove that a particular installed
image contains the latest configuration or has working host/guest transfers.

The LightDM boot hook now selects the X11 compatibility session for both VMware
and VirtualBox (`systemd-detect-virt` reports `oracle`). Previously it selected
X11 only for VMware, while the VirtualBox desktop helper refused to start outside
X11. The existing managed configuration filename retains `vmware` for upgrade
compatibility. Other hypervisors retain their normal session defaults.

The guest kernel configuration enables `CONFIG_MOUSE_PS2_VMMOUSE` and
`CONFIG_VBOXGUEST`. These must also be present in the **running** kernel. A system
Tools daemon alone does not establish working clipboard integration; the logged-in
desktop helper must run too.

Host settings also apply:

- VMware: enable copy/paste and drag-and-drop in Guest Isolation; enable automatic
  mouse grab/ungrab and guest autofit in the host application preferences.
- VirtualBox: enable Mouse Integration, select a USB Tablet pointing device and
  VMSVGA graphics, and enable bidirectional Shared Clipboard and Drag and Drop.
  Do not confuse seamless-window mode with automatic mouse release.

See [Broadcom's clipboard guidance](https://knowledge.broadcom.com/external/article/320995)
and [Oracle's Guest Additions guide](https://docs.oracle.com/en/virtualization/virtualbox/7.2/user/guestadditions.html).

Validation on October 6, 2026: the generated boot hook was exercised in an isolated
fixture for VMware, VirtualBox, KVM and no hypervisor, including repeated runs and
preservation of an unrelated user setting. This is not a guest boot test.
Installation into the user's running VM, kernel verification, bidirectional text
and file transfer, automatic pointer release and resizing remain unverified.
The updated image builds and boot checks are recorded in [release verification](release-20261006.md).

The current VMware guest was subsequently verified on kernel build #9 with
`CONFIG_MOUSE_PS2_VMMOUSE=y`, an absolute VMMouse device, an X11 desktop and the
`vmtoolsd -n vmusr` helper. The user confirmed bidirectional clipboard sharing
and automatic mouse release after enabling host auto-grab/ungrab and disabling
gaming mouse mode. VirtualBox end-to-end testing remains outstanding.
