# Aether Beam — several installs at once

Beam is Aether's install scheduler. It answers a simple question: *why does
installing five applications take as long as installing them one after another?*

Because the slow part is the network. The unsafe part is the package database.
Beam splits every install into two stages and threads only the safe one.

| Stage | Runs | Concurrency | Why |
|---|---|---|---|
| `prepare` | download and verify | up to `--workers` (default = CPU count, capped at 8) | Network and disk wait; nothing is mutated. |
| `commit` | install | exactly one at a time, dependency ordered | `dpkg` has one writer and flatpak refuses a concurrent deploy. A half-written package database is far worse than a slower install. |

Commits are also guarded by a file lock, so a second `aether-beam` process (or a
second user) waits instead of racing.

## Plan format

```json
{
  "schema": 1,
  "apps": [
    {"id": "firefox", "source": "flatpak", "ref": "org.mozilla.firefox", "remote": "flathub"},
    {"id": "python3", "source": "deb", "file": "/var/cache/aether-update/python3_3.13.deb",
     "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
     "depends": ["firefox"]}
  ]
}
```

`id` is a local name, not a package name. `depends` refers to other `id`s in the
same plan: a dependent's commit waits until its dependency is installed, and is
reported as `blocked` if that dependency failed. `arch` is optional; it must be
`all` or match this machine, and a mismatched plan is refused before anything is
downloaded.

A `deb` entry must live under `/var/cache/aether-update` and carry a digest.
Beam does not download `.deb` files itself: `aether-update` stages and verifies
signed packages, and Beam then installs them. That keeps one trust boundary.

## Commands

```sh
aether-beam plan install.json     # validate and print, install nothing
aether-beam install install.json  # prepare in parallel, commit in order
aether-beam install install.json --events   # JSON progress lines on stderr
aether-beam status                # the last receipt
```

Exit status is `0` when every application is installed, `1` when any application
failed, was blocked or was cancelled, and `2` for an invalid plan. The receipt is
written to the state directory (`0600`) and lists every application's final
state, its error if any, and the worker count actually used.

Re-running the same plan resumes: an application recorded as installed in the
journal is not downloaded again. `--fresh` ignores the journal.

## What Beam refuses

- Duplicate ids, unknown dependencies and dependency cycles.
- Flatpak references, remotes, ids or paths containing shell metacharacters,
  spaces, or anything outside a narrow pattern. Every argument is a list element;
  there is no shell at any point.
- `.deb` paths outside the verified cache, and paths containing `..`.
- Plans over 64 applications or 256 KiB.
- A plan whose architecture does not match the machine.

## Status

Implemented and unit-tested offline (`test_beam.py`) with an injected backend, so
the tests measure real overlap rather than trusting the scheduler's own report:
downloads must overlap, commits must not, dependencies must commit in order, a
failed application must not stop independent ones, cancellation and resume must
be recorded. `SystemBackend` and its exact argv are covered separately.

Not done: no booted Aether image contains Beam; the flatpak `--no-deploy` path and
the `pkexec dpkg` path have not been exercised against a real package database;
there is no GUI queue view beyond the receipt; and Beam does not resolve
dependencies from repository metadata, so a plan must name them.
