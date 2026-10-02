# ISO assembly

These scripts turn the `apt-root` chroot (the desktop rootfs plus the
package-manager chain from [`..`](..)) into bootable live ISOs. They are the
last step of the chain documented in [`../README.md`](../README.md), which
covers how dpkg, apt, AppStream, PackageKit and Plasma Discover were built.

Nothing here publishes anything. See
[`../../../docs/licensing.md`](../../../docs/licensing.md) for the licensing
review and the caveats about Red Hat's `libdnf`/`rpm` (deliberately absent).

## What this produced

Built on the 0.3 tree (`BASE=/opt/aether`):

| ISO | Bytes | Notes |
| --- | --- | --- |
| `aether-0.3-x86_64.iso` | 1,358,888,960 | desktop + package manager, from `apt-root` |
| `aether-0.3-x86_64-unified.iso` | 1,987,491,840 | desktop + Nimbrel AI + Vector + package manager |

The unified image is deliberately under GitHub Releases' 2 GiB per-asset cap
(2,147,483,648 bytes).

`aether-0.3-x86_64.iso`:

```
sha256 069263926051efc6fdaa3b584318798bc52b939dbe9073e52c3eb2dda3fac73d
```

`aether-0.3-x86_64-unified.iso`:

```
sha256 4c118ee9cc8e87ed58d9696dcc35b4e4dbe0a0e661416c5b3646178ccc82bfb3
```

## Order

1. `build-package-manager-iso.sh` — rebuild the desktop ISO from `apt-root`.
2. `build-unified-iso.sh` — merge that package manager into the AI image.
3. `smoke-boot.py bios|uefi <iso>` — boot it to a login prompt.
4. `cpu-probe.sh <iso>` — run the chain under an emulated baseline CPU.

Each script writes its transcript to `$BASE/logs/apt/NNN-*.log`.

## Why the unified image is a union, not a rebuild

The build trees for the Vector, Nimbrel and local-ai images no longer exist —
only their finished ISOs survive. `local-ai` is the most complete of them (it
is already desktop + Nimbrel AI + Vector); the only files `apt-root` has that
it lacks are the package-manager chain. So `build-unified-iso.sh` unsquashes
`local-ai`, adds exactly the `apt-root`-only files, and repacks.

That is honest about what it is: the unified ISO is a **runtime-tree union**,
not a from-source rebuild of one tree. The boot machinery, kernel and initrd
are local-ai's; the `rootfs.squashfs` is local-ai plus the overlaid chain.

The overlay is filtered to keep it to the chain: `root/` is dropped so no
operator key material (`root/.ssh`, `root/.gnupg`) can ship, along with
`var/cache/`, `var/log/`, headers and CMake files. The script refuses to
continue if `root/.ssh` or `root/.gnupg` appears in the merged tree.

## The image-`ldconfig` gotcha

After merging, the dynamic-loader cache **must** be regenerated with the
image's own loader:

```sh
chroot "$AIROOT" /sbin/ldconfig
```

Do **not** use the host's `ldconfig -r "$AIROOT"`. This image is LFS, and its
libraries live in both `/usr/lib` and `/usr/lib64`; the host's `ldconfig`
omits the `/usr/lib64` search path, so `libapt-private.so.0.0` is invisible
and `apt-get` dies with:

```
apt-get: error while loading shared libraries: libapt-private.so.0.0
```

The script runs the image's `ldconfig` and then sanity-checks `apt-get`,
`dpkg` (package count), `plasma-discover`, `plasmashell` and `nimbrel` before
packing.

## Validation performed

Against `aether-0.3-x86_64-unified.iso`:

- **Contents**: 221,632 squashfs entries; all markers present — `plasmashell`,
  `nimbrel`, `vector`, `/opt/nimbrel/model.gguf` (563,036,064 bytes),
  `plasma-discover`, `dpkg`, `apt-get`, `packagekitd`,
  `libpk_backend_apt.so`.
- **Package DB**: 422 `ii` records, matching the synthetic database; no proof
  stubs.
- **No unresolved libraries** in discover, `packagekitd`, the apt backend,
  nimbrel, vector or plasmashell.
- **Boot**: reached `aether login:` under firmware both ways (`132-smoke-*`).
- **CPU baseline**: `apt-get 3.3.3`, `dpkg 1.23.11`, `appstreamcli 1.0.5`,
  `packagekitd 1.4.0` and `plasma-discover 6.3.6` all run under
  `qemu-x86_64 -cpu qemu64` with no illegal instruction, and the whole system
  boots under `-cpu qemu64`.

CPU compatibility is a property of the build flags (`-march=x86-64
-mtune=generic`, baseline x86-64 / v1) plus these probes; it is not achieved by
rebuilding per microarchitecture. So the single x86_64 image runs on all
modern x86-64 CPUs, and the ARM64 console image is separate and untouched.
This is *not* a claim of certification on physical hardware; it is emulated
baseline evidence.

## Known caveats

- `plasmashell --version` exits 139 (SIGSEGV) under qemu-user emulation in a
  bare chroot. The original local-ai image does exactly the same there, so it
  is an emulation artifact (no session bus / odd `XDG_RUNTIME_DIR`), not a
  CPU-feature or union regression. The real check is the boot smoke test.
- `nimbrel` and `vector` are long-running servers; `--help` under the probe
  simply times out (exit 124), which is expected and not a failure.
- The interactive Discover UI was not exercised at runtime: the persistent
  credential file applies only to the 0.2 disk image, so an automated login
  returns "Login incorrect". Do not read this record as proof the GUI store
  was clicked through.
