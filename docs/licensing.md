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

## Bundled third-party components

These ship inside the Aether image under their own terms, including but not
limited to:

| Component | Licence |
|---|---|
| Linux kernel | GPL-2.0-only |
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