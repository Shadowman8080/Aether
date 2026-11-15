# ARM64 and 32-bit x86 status

Aether's desktop is built for **x86_64** only. ARM64 is a stated target, not a
shipped port, and this page exists so that gap is not quietly ignored.

## What exists today

| Piece | x86_64 | ARM64 |
|---|---|---|
| Kernel configuration | built and booted | `build/configs/linux-arm64.config` and `aether_arm64_defconfig` exist; no image |
| Base overlay | built | `build/overlay-arm64/` exists; not exercised by a current build |
| Console prototype | historical | historical `build/scripts/*arm64*` prototypes, not current desktop ports |
| Boot loader / ISO | GRUB, BIOS and UEFI images | none |
| Userspace (Qt, KDE, Plasma) | compiled from pinned source | not built |
| First-party code | built | architecture-neutral Python; untested on ARM64 |

A successful x86_64 build is not evidence that any of this works on ARM64, and
neither is the presence of a configuration file.

## What first-party code does for multiple architectures

Aether's own install and update tooling is written to be architecture-neutral and
to refuse a mismatch rather than silently install the wrong binaries:

- `src/beam/beam.py` maps `x86_64`/`amd64` and `aarch64`/`arm64`, rejects a plan
  whose architecture does not match the machine, and reports the native
  architecture in every install receipt.
- `src/updates/runtime.py` already validates a signed catalog against
  `platform.machine()` and the same architecture map.
- `src/pilot/pilot.py` takes architecture-specific commands from a data catalog,
  so adding an ARM64 action is a data change, not a rewrite.

That is portability groundwork. It is not an ARM64 port.

## What an ARM64 desktop image still needs

1. **A userspace build target.** The full Qt/KDE/Plasma chain must be compiled for
   `aarch64` from the same pinned sources with the same baseline-ISA discipline
   (generic armv8-a, not host-tuned).
2. **A bootable image.** `arm64-efi` GRUB or a UEFI unified kernel image, an
   initramfs built by the same recipe, and a device-tree strategy for boards that
   need one.
3. **Kernel validation.** The ARM64 config has never been booted; enabling
   plug-and-play driver classes, AppArmor, Landlock and the same hardening options
   needs an actual boot result, not a `make olddefconfig`.
4. **Runtime testing.** Graphical login, Plasma Wayland, audio, network, on-device
   inference speed (a 0.8B model on a small ARM board is much slower than on a
   desktop CPU, and no performance claim should be made before measuring).
5. **A recorded verification entry.** Same rule as everywhere else in this
   repository: emulation and configuration files are not a hardware result.

## 32-bit x86

Same shape of gap. `aether_x86_defconfig` and historical console images exist;
there is no current i686 desktop, and `i386`/`i686` mapping in the install tooling
is only there so a wrong-architecture package is rejected cleanly.
