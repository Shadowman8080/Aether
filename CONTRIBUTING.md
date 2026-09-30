# Contributing to Aether

Thanks for looking. Before you spend an evening on something, read this page —
Aether's build system is opinionated and some perfectly reasonable changes will
be declined.

## Project shape

- **Everything is built from pinned upstream source.** There is no binary
  tarball of the base system and no other distribution is bootstrapped. If your
  change would replace a source build with a binary package, it will be declined.
- **x86_64 only.** There is no ARM64, i686 or Raspberry Pi desktop image. Do not
  add architecture-conditional hacks for targets that are not built.
- **The first-party surface is small.** `src/desktop` (Vector, greeter, installer,
  Plasma layout, power menu), `src/nimbrel`, `src/security`, `src/updates` and
  `src/assets`. Upstream KDE/Qt code is *not* vendored here.
- **Honesty is a feature.** If something is unfinished, the docs say so. Keep it
  that way.

## Licence

Contributions are accepted under **`GPL-3.0-or-later`**, matching this
repository. Do not contribute code linked against **GPL-2.0-only** libraries —
that is incompatible, and the Linux kernel is the obvious trap. See
[`docs/licensing.md`](docs/licensing.md).

## What will be accepted

- Fixes to Aether's own code in `src/`
- Documentation that makes a limitation *more* accurate
- Build recipes that are reproducible and use all available CPUs
- Tests that fail before your change and pass after it
- Visual assets under `src/assets/`
- Reports of real bugs, with reproduction steps

## What will be declined

- Claims of certification, compliance or "production ready" without an
  independent assessment
- Marking a feature "verified" when it was only compiled, or only tested under
  emulation
- Enabling services, schedulers or network exposure by default
- Committing binaries, disk images, ISOs or model weights to git
- Anything that weakens the default-deny network posture without a written
  justification
- Flattening honest caveats out of the docs

## Before you open a pull request

- [ ] `git diff` contains **no secrets**: no SSH keys, no `known_hosts`, no
      `known_hosts`, no credentials files, no publisher or R2 configuration, no
      `.vmdk`, no `.iso`
- [ ] Your change is confined to `src/` or `docs/`
- [ ] Any claim you make is something you personally observed
- [ ] You state **exactly what you re-ran**, since there is no CI
- [ ] New code matches the surrounding style — the existing code is terse and
      dense, and matching it is a courtesy
- [ ] Anything you could not test is labelled as untested

## Build and test expectations

There is no CI. Your pull request is unverified until a human reads it and runs
things. If your change affects the desktop, expect the manual checks in
[`docs/verification.md`](docs/verification.md) to be the acceptance criteria.

Use all available CPUs for builds. Do not reduce thread counts to "be nice".

## Security reports

**Do not open a public issue for a vulnerability.** See
[`SECURITY.md`](SECURITY.md).

## Honest state of the project

This is a 0.3 development snapshot. It boots, logs in, and runs a real desktop
with on-device AI. It is not finished, and the docs enumerate precisely what is
missing. If you want to help with something on that list, that is probably the
most valuable contribution available.

## Code of conduct

[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) applies everywhere, including issues,
pull requests and any community space.