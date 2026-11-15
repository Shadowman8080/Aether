# Screenshot gallery

Every image on this page is a live capture from an Aether virtual machine. They
are not mockups, design renders or staged dialogs. The complete set, capture
notes and provenance are in [`media/README.md`](../media/README.md); the files
live under [`media/screenshots/`](../media/screenshots/).

## Desktop

![Aether Plasma desktop with the Aether theme](../media/screenshots/01-desktop.png)

Aether 0.3 on KDE Plasma. The panel, wallpaper, colour scheme and application
menu are the ones shipped in the image.

<table>
  <tr>
    <td width="50%"><img src="../media/screenshots/02-aurasearch.png" alt="AuraSearch launcher with an inline calculation"></td>
    <td width="50%"><img src="../media/screenshots/03-nimbrel-ai.png" alt="Nimbrel answering on-device"></td>
  </tr>
  <tr>
    <td><strong>AuraSearch</strong>: applications, files and settings, with inline calculations.</td>
    <td><strong>Nimbrel</strong>: an on-device answer from the small local model. The answer is shown unedited.</td>
  </tr>
</table>

![Vector showing the installed applications](../media/screenshots/08-vector-applications.png)

Vector, the file and application browser, showing the installed application
grid.

## Sign-in and session

<table>
  <tr>
    <td width="50%"><img src="../media/screenshots/06-login-greeter.png" alt="Aether login greeter"></td>
    <td width="50%"><img src="../media/screenshots/26-lock-screen.png" alt="Aether lock screen"></td>
  </tr>
  <tr>
    <td>The greeter. Password fields in this gallery are empty or masked.</td>
    <td>The lock screen after a session is locked.</td>
  </tr>
</table>

## Installation

![Aether installer welcome page](../media/screenshots/15-installer.png)

The installer states its whole-disk limitation before anything is changed.

<table>
  <tr>
    <td width="50%"><img src="../media/screenshots/17-installer-region.png" alt="Region, keyboard and time zone"></td>
    <td width="50%"><img src="../media/screenshots/18-installer-account.png" alt="Account and storage passphrases"></td>
  </tr>
  <tr>
    <td>Region, keyboard and time zone.</td>
    <td>Account, LUKS2 storage passphrase and separate recovery passphrase.</td>
  </tr>
  <tr>
    <td><img src="../media/screenshots/19-installer-review.png" alt="Installer review page confirming disk erasure"></td>
    <td><img src="../media/screenshots/20-installer-complete.png" alt="Installation complete"></td>
  </tr>
  <tr>
    <td>Review requires the exact <code>ERASE /dev/…</code> confirmation.</td>
    <td>The installed bootloader and the finished installation.</td>
  </tr>
</table>

## Encryption and security

<table>
  <tr>
    <td width="50%"><img src="../media/screenshots/22-encrypted-unlock.png" alt="LUKS2 unlock prompt during boot"></td>
    <td width="50%"><img src="../media/screenshots/21-security-center.png" alt="Aether Security Center"></td>
  </tr>
  <tr>
    <td>LUKS2 unlock for the encrypted root filesystem.</td>
    <td>Security Center separates what is protected, unverified and unsupported.</td>
  </tr>
</table>

The encrypted-root install protects the root filesystem. The EFI system
partition and `/boot` remain unencrypted in the current released image; this
gallery does not claim otherwise. See
[Secure Boot and encrypted roots](secure-boot.md#limits).

## Boot and first start

<table>
  <tr>
    <td width="50%"><img src="../media/screenshots/29-boot-menu.png" alt="Aether GRUB menu"></td>
    <td width="50%"><img src="../media/screenshots/30-boot-splash.png" alt="Aether Plymouth boot splash"></td>
  </tr>
  <tr>
    <td>The UEFI GRUB menu.</td>
    <td>The Plymouth boot splash.</td>
  </tr>
</table>

![First boot from the installed disk](../media/screenshots/24-installed-desktop.png)

First start from the installed disk.

## What these images do and do not prove

- They were captured from the running guest framebuffer, not from a separate
  design tool.
- They show the interface as it appeared. They do not certify every feature in
  every environment.
- They contain no passwords, tokens or private keys. The installer account name
  visible in an installation capture is a throwaway test account.
- Virtual-machine captures are not physical-hardware certification. See the
  [physical Secure Boot test plan](secure-boot-physical-test-plan.md).
