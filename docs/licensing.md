# Licensing

This repository covers **Aether's own code and assets**. The full system
contains many third-party components under many different licences, and the
honest answer is that Aether is not single-licensed.

## In this repository

Aether's first-party source and artwork are licensed under:

**GNU General Public License v3.0 or later** — see [`../LICENSE`](../LICENSE).

SPDX identifier: `GPL-3.0-or-later`.

This covers:

- `src/desktop/` — Vector, the greeter, the installer, the Plasma shell layout,
  the power menu plasmoid
- `src/nimbrel/` — the Nimbrel client, gateway, engine wiring
- `src/security/` — firewall, AppArmor, PAM and backup tooling
- `src/updates/` — signing and TUF repository tooling
- `src/assets/` — wallpapers, colour schemes, screensavers, Plymouth themes

## The GPL-3 / GPL-2 problem — read this

**The Linux kernel is GPL-2.0-only.** GPL-3.0 is *not* compatible with
GPL-2.0-only code. There is no relicensing of the kernel to GPL-3 that would
make a GPL-3.0-only distribution possible.

This does not make the current arrangement invalid, but it does mean:

- Aether's own code is `GPL-3.0-or-later`.
- Kernel-derived components remain **GPL-2.0-only**.
- Anything statically or dynamically linked against GPL-2.0-only code must
  respect GPL-2.0-only terms.

For practical purposes: **GPL-2.0-only code cannot be incorporated into
GPL-3.0-only first-party code.** If you plan to contribute code that links
against GPL-2.0-only libraries, raise an issue first.

Reviewing a distribution's overall licensing is a real legal question, not a
detail. For anything beyond personal experimentation, get advice from a
qualified lawyer.

## The package manager: dpkg and apt

Aether's base image is source-built, so it ships with **no package database of
any kind** — no `var/lib/pacman/local`, no `var/lib/dpkg/status`, no
`var/lib/rpm/Packages`. To give the image a package manager, dpkg and apt are
built from upstream source inside the image and the ownership database is
synthesised from the files already present.

This is a compatible choice, and it was verified against the actual tarballs
rather than assumed:

| Component | Upstream licence | GPL-2.0-only files |
|---|---|---|
| dpkg 1.23.11 | `GPL-2+` throughout | **0** |
| apt 3.3.3 | `GPL-2+` | **0** |

- **dpkg 1.23.11.** Every licensing header in the tarball carries the
  "or (at your option) any later version" clause. The machine-readable
  copyright file contains only `GPL-2+` short names; there is not a single
  `GPL-2` (i.e. GPL-2.0-only) entry.
- **apt 3.3.3.** The copyright file has one umbrella `Files: *` stanza marked
  `GPL-2+`, which covers everything shipped. The single separate `GPL-2` stanza
  covers `CMake/Documentation.cmake`, a build-time helper that is never linked
  into `apt` or `apt-ftparchive`; it does not affect the shipped binaries.

Because both are `GPL-2.0-or-later`, they may be combined with Aether's
`GPL-3.0-or-later` first-party code. Neither contributes a GPL-2.0-only
component, so the apt chain does not add to the kernel problem described above.

The libraries apt links against are permissive or LGPL and carry no additional
constraint on the GPL-3 grant:

| Library | Licence | Why apt needs it |
|---|---|---|
| Berkeley DB 5.3.28 | Sleepycat/Oracle (BSD-style) | `find_package(Berkeley REQUIRED)` |
| xxHash 0.8.2 | BSD-2-Clause | `find_package(XXHASH REQUIRED)` |
| triehash 0.3 | MIT | `find_program`, `FATAL_ERROR` if absent |
| libarchive, libcurl, GnuTLS, gpgme, liblz4, liblzma, zlib, libsqlite3 | BSD / MIT / LGPL / GPL-2+-or-later | already in the image |

Note on Berkeley DB: upstream 5.3.28 is Oracle-licensed and its licence is not
GPL. It is used as an unmodified shared library, dynamically linked, which
leaves Aether's own code under GPL-3.0 and places no copyleft obligation on it.

### What the synthetic database does and does not do

Generating `/var/lib/dpkg/status` and `/var/lib/dpkg/info/*.list` lets the
package manager **reason about** the system: `dpkg -S` resolves a path to its
owner, `dpkg -l` enumerates what is installed, and file-change detection works.

It is **not** a route to upgrading the base. The image was not produced by dpkg,
so there is no version history, no maintainer metadata, and no dependency
graph. Treating a synthetic entry as a dpkg-installed package and then letting
`apt upgrade` replace it would substitute an unverified binary for a
source-built one. See [`../build/AETHER-UPDATE-POLICY.md`](../build/AETHER-UPDATE-POLICY.md)
for the update policy that follows from this.

## Bundled third-party components

These ship inside the Aether image under their own terms, including but not
limited to:

| Component | Licence |
|---|---|
| Linux kernel | GPL-2.0-only |
| dpkg | GPL-2.0-or-later |
| apt | GPL-2.0-or-later |
| Berkeley DB | Sleepycat/Oracle (BSD-style, non-GPL) |
| xxHash | BSD-2-Clause |
| triehash | MIT |
| systemd | LGPL-2.1-or-later (with GPL-2.0-or-later parts) |
| Qt (open source) | LGPL-3.0 / GPL-2.0 / GPL-3.0 (tri-licensed) |
| KDE Frameworks, Plasma, KDE apps | LGPL-2.1-or-later / GPL |
| GMP, MPFR, MPC | LGPL-3.0-or-later (with GPL exceptions) |
| nftables | GPL-2.0 |
| AppArmor | GPL-2.0 |
| restic | BSD-3-Clause |
| cryptsetup / LUKS2 | GPL-2.0-or-later (cryptsetup), LGPL-2.1+ (libcryptsetup) |
| llama.cpp | MIT |
| Tesseract OCR | Apache-2.0 |
| **Qwen3.5 0.8B** (model weights) | **Apache-2.0** |

Note that the **model weights are Apache-2.0**, not GPL. That is a separate,
permissive grant from the inference engine's MIT licence. Provenance is pinned
in [`../src/nimbrel/model.json`](../src/nimbrel/model.json).

## Per-component licensing

Each upstream package retains its own licence file inside the image. Aether does
not relicense upstream work. If you produce a derivative image, you are
responsible for carrying the correct per-component notices — Aether's `LICENSE`
file at the repository root does not supersede any of them.

## Contributions

Contributions to first-party code are accepted under
`GPL-3.0-or-later`, matching the rest of the repository. By contributing you
confirm you have the right to license the work that way. See
[`../CONTRIBUTING.md`](../CONTRIBUTING.md).