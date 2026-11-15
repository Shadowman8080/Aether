# Installing several applications at once

Beam installs more than one application in the time it used to take for one,
without risking the package database.

Every install has two halves. **Preparation** (download and verification) waits on
the network and is safe to run several times at once. **Installation** writes the
package database and must happen one application at a time — `dpkg` has a single
writer, and flatpak refuses a concurrent deploy. Beam runs the slow half in
parallel and the unsafe half strictly in order.

```sh
aether-beam plan install.json     # check a plan without installing
aether-beam install install.json  # install it
aether-beam status                # what happened last time
```

Aether Settings has the same controls under **Install apps in parallel**.

## A plan

```json
{
  "schema": 1,
  "apps": [
    {"id": "firefox", "source": "flatpak", "ref": "org.mozilla.firefox"},
    {"id": "tool", "source": "deb", "file": "/var/cache/aether-update/tool.deb",
     "sha256": "<64 hex characters>", "depends": ["firefox"]}
  ]
}
```

- `id` is a name inside your plan, not a package name.
- `depends` lists other `id`s. The dependent installs after them, and is reported
  as **blocked** if one fails instead of being half-installed.
- `arch` is optional and must be `all` or match this machine. A plan for the wrong
  architecture is refused before anything downloads.
- A `deb` must already be staged in `/var/cache/aether-update` with a digest.
  Signed downloads stay `aether-update`'s job; Beam installs what that verified.

## What it will not do

- It will not run two package transactions together, however many workers you ask
  for.
- It will not accept a reference, path or name containing shell characters. No
  shell is used anywhere in Beam.
- It will not claim success: the exit status is non-zero if any application
  failed, was blocked or was cancelled, and the receipt lists each final state.

Interrupt an install and run it again: applications already installed are not
downloaded a second time.

## Status

Beam is implemented in `src/beam/` and its scheduler is unit-tested offline,
including checks that downloads really do overlap and installs really do not. No
published Aether image contains it yet, and its flatpak and `dpkg` paths have not
been run against a real package database. See
[`../src/beam/README.md`](../src/beam/README.md).
