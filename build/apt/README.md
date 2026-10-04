# The apt chain and the synthetic package database

The Aether base image is Linux From Scratch / BLFS built by **jhalfs**. It ships
with no package database at all: no `var/lib/dpkg/status`, no
`var/lib/pacman/local`, no `var/lib/rpm/Packages`. This directory records how a
real package manager was added on top of that source-built base, and how the
ownership database those tools need was synthesised from the build metadata
that survived.

Nothing here is a route to upgrading the base. See
[`../../docs/licensing.md`](../../docs/licensing.md) for the licensing review and
[`../AETHER-UPDATE-POLICY.md`](../AETHER-UPDATE-POLICY.md) for what updates are
allowed to do.

## What was built

Everything below was compiled **inside a chroot of the extracted desktop
rootfs** (glibc 2.44, libstdc++ 6.0.36, GCC 16.2.0, CMake 4.4.2), not on the
guest and not by attaching a binary distribution's repositories. No Arch or
Ubuntu package source is used; every component is upstream source built for
`-march=x86-64 -mtune=generic`, matching the rest of the image.

Build order (each step depends on the previous):

| # | Component | Version | Role |
|---|---|---|---|
| 1 | xxHash | 0.8.2 | apt dependency (`find_package(XXHASH)`) |
| 2 | Berkeley DB | 5.3.28 | apt dependency (`find_package(Berkeley)`); only the library and headers |
| 3 | triehash | 0.3 | apt build-time tool (`find_program`, fatal if absent) |
| 4 | libmd | 1.1.0 | provides the top-level `md5.h` dpkg needs |
| 5 | **dpkg** | 1.23.11 | package installer and ownership database |
| 6 | **apt** | 3.3.3 | package manager / `apt-get`, `apt-cache`, `apt-ftparchive` |
| 7 | libyaml | 0.2.5 | libxmlb / AppStream dependency |
| 8 | libxmlb | 0.3.29 | AppStream dependency |
| 9 | jansson | 2.15.1 | PackageKit dependency |
| 10 | **AppStream** | 1.0.5 | metadata; built with `-Dqt=true` for `AppStreamQt` (Qt 6) |
| 11 | **PackageKit** | 1.4.0 | package abstraction daemon, apt backend |
| 12 | **PackageKit-Qt** | 1.1.4 | Qt 6 bindings used by Plasma Discover |
| 13 | **plasma-discover** | 6.3.6 | the software store itself |

Notes that cost real time and should not be rediscovered:

- **libmd, not libbsd.** dpkg's `md5.h` lookup fails with the libbsd layout;
  libmd installs a top-level `include/md5.h`, which is what the build wants.
- **The Berkeley DB command-line utilities were removed.** apt uses only
  `libdb`; shipping `db_*` tools would claim files with no purpose.
- **`liblfs`, `libfuse3`, `libpcre2`, `libseccomp` and `libselinux` are not apt
  dependencies here.** `FindLFS.cmake` tests `sizeof(off_t) >= 8` natively,
  which is already true on x86_64, so the LFS shim is never required.
- **`aptdaemon` was dropped.** PackageKit 1.4.0's apt backend links
  `dependency('apt-pkg', '>=1.9.2')` directly. The working chain is
  **dpkg → apt → PackageKit (apt backend) → plasma-discover**; there is no
  aptdaemon in it.
- **apt CMake options:** `-DUSE_NLS=OFF -DWITH_DOC=OFF -DWITH_TESTS=OFF
  -DBUILD_FOR_DEB=OFF`.
- **PackageKit meson options:** apt backend only; systemd, elogind,
  offline_update, legacy_tools, introspection, bash_completion,
  gstreamer_plugin, gtk_module, cron, python_backend, man_pages and gtk_doc all
  off.
- **plasma-discover** has only `WITH_KCM` and `WITH_NOTIFIER` options (both
  default on); its backends are selected by dependency detection. Two fixes
  were required:
  1. add `#include <QQmlEngine>` to `kcm/updates.cpp`;
  2. configure with `-DCOMPILER_HAS_HIDDEN_VISIBILITY=TRUE
     -DCOMPILER_HAS_HIDDEN_INLINE_VISIBILITY=TRUE`. Without this, CMake's
     `GenerateExportHeader` produced empty export macros under ECM's
     `-fvisibility=hidden`, so the plugins linked against an empty
     `libDiscoverCommon`.
- **AppStream** was rebuilt with `-Dqt=true` (`qt-versions` defaults to `['6']`)
  to produce `libAppStreamQt`.

## The synthetic ownership database

`gen-dpkg-db.py` writes a synthetic `/var/lib/dpkg/status` and
`/var/lib/dpkg/info/*.{list,md5sums}` describing the files already present. It
takes per-file ownership from the build metadata that survived:

- `native-build-metadata/jhalfs/installed-files/` — exact LFS chapter-8 lists;
- `var/lib/jhalfs/BLFS/instpkg.xml` — LFS+BLFS names and versions;
- `native-desktop/logs/*.log` — installed paths parsed from CMake
  `-- Installing:`, meson `Installing X to DIR`, autotools/libtool install
  commands, symlink blocks and Boost.Build `common.copy`;
- explicit pattern sets for the apt-chain packages this work added.

Result on the 0.3 desktop rootfs: **422 packages**, **404,049 ownership
records**, **374,499 md5sum entries**, covering **158,025 of 177,515** real
files. `dpkg -l`, `dpkg --audit` and `dpkg -V` are clean, `dpkg -S` resolves
paths, and `apt-cache stats` reads all 422 as normal packages. The unowned
remainder is man/doc/perl/python/grub files whose packages left no file list.

It is explicitly synthetic: `Section: aether-synthetic`, a generated
`Maintainer`, and one package per built component. It exists so the tools can
*reason about* the system, not so `apt upgrade` can replace source-built
packages with unverified binaries.

## Verification

`proof-chain.sh` runs inside the chroot and proves the chain end to end:

1. builds real `.deb` packages with `dpkg-deb`;
2. `dpkg -i`, `dpkg -s`, `dpkg -L`, runs the installed binary;
3. `dpkg -V` detects an intentionally modified file (`??5?????? /usr/bin/...`);
4. `dpkg` refuses to overwrite a file owned by another package;
5. `dpkg -r` removes cleanly;
6. a local `file:` apt repository is indexed with `apt-ftparchive`, and
   `apt-get update` / `install` (selecting the newest of two versions) /
   `remove` all work;
7. the transient repository and test packages are removed again.

All checks pass. See `logs/apt/` on the build host for the captured transcripts.

## Running it: what is checked, and what is not

The chain is **built and shipped in `aether-0.3-x86_64-unified.iso`**. That is a
build-time claim. This section is the runtime one, and it is deliberately blunt
about the difference.

`aether-apt-check` (installed at `/usr/bin/aether-apt-check`) is the runtime
check, and the boot self-test (`S99aether`) runs it on every
`aether.selftest=1` boot. It verifies that:

- `dpkg`, `apt-get` and `apt-cache` **execute**, not merely exist. This is the
  check that matters: with a wrongly regenerated loader cache `apt-get` is
  present and still dies on `libapt-private.so.0.0`.
- `/var/lib/dpkg/status` is present and reports installed packages, so dpkg and
  apt are reasoning about a populated system.
- `dpkg --audit` is clean. `--audit` exits 0 even when it reports damage, so its
  output is what gets checked.
- the PackageKit pieces Discover needs are in place: the unit, the D-Bus
  activation file, `libpk_backend_apt.so`, and `plasma-discover`.
- **no package repository is attached.** This is asserted, not assumed. Aether
  attaches no Arch or Ubuntu repository by policy, so a source appearing in
  `sources.list` or `sources.list.d` fails the check.

Exit status is `0` healthy, `1` present but broken, `2` no chain on this profile.
The self-test reports `1` as FAIL and `2` as an explicit SKIP, so an absent
chain can never be mistaken for a passing one.

Its test suite runs offline against a throwaway tree and needs no dpkg:

```
sh build/scripts/test-apt-check.sh
PASS=20 FAIL=0
```

Cases include the broken-loader-cache failure, an empty dpkg database, audit
damage, a repository attached in either `sources.list` or `sources.list.d`, and
a comment-only file correctly *not* counting as a repository.

### Honest gaps

- **Nothing has been booted.** The chain was proven in a chroot
  (`proof-chain.sh`) and by inspection of the ISO contents, but
  `aether-apt-check` has never run inside a booted Aether. The ARM64 console
  image has no package chain and will report SKIP, which is correct.
- **No repository exists**, so `apt-get install` cannot fetch anything. The
  chain can install a local `.deb` and nothing more. Aether's own signed
  repository is still unimplemented; see [`../src/updates`](../../src/updates).
- **The Discover UI was never clicked through**, so "the store works" is not
  claimed. PackageKit is D-Bus activated and is deliberately *not*
  `systemctl enable`d.
- `build-unified-iso.sh` now fails the build if `apt-get` will not execute or
  dpkg reports no packages, instead of printing the result and continuing.

## Reproducing

The steps are incremental and were driven per stage against the chroot created
from the extracted desktop ISO; `gen-dpkg-db.py` and `proof-chain.sh` here are
the two artifacts that are worth re-running as-is. `docs/licensing.md`
documents the GPL-2+ / GPL-2.0-only boundary that made dpkg and apt usable
alongside Aether's `GPL-3.0-or-later` code.

## Shipping it

The chain reaches a bootable image through the scripts in [`iso/`](iso/): one
rebuilds the desktop ISO from this chroot, one merges the chain into the
AI image to make the single x86_64 `aether-0.3-x86_64-unified.iso`, and two
prove it (serial boot to login, and a baseline-CPU probe). See
[`iso/README.md`](iso/README.md) for the sizes, digests, the union method and
the image-`ldconfig` trap that silently breaks `apt-get`.
