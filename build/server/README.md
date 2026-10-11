# Aether Server build — 0.1 bring-up

The server edition is a second image target on top of the same source-built
Aether base, mirroring the desktop pipeline: an offline root is prepared and
finished, then squashed into a live ISO whose squashfs is used for both "try"
and "install".

```
build/server/
└── scripts/
    ├── install-server-assets.sh   copy assets, catalog, configs, backend and
    │                              launchers into an offline Aether root
    ├── configure-server.py        image facts: version marker, multi-user
    │                              target, firstboot enablement, role dirs,
    │                              default firewall.json
    ├── build-server-packages.py   catalog → source-build recipe plan
    │                              (scaffolding; nothing is compiled yet)
    ├── build-server-iso.sh        assemble the aether-server-0.1 ISO
    ├── test-server-roles.py       23-unit test suite for the catalog/backend
    └── test-server-roles.sh       thin wrapper for running the suite
```

## Pipeline

```
src/server  ──install-server-assets.sh──▶  offline server root
                                              (from the console base image)
                 configure-server.py   ─▶  server root finished for squashing
                 build-server-packages.py  builds role software into the base
                                           (bring-up; nothing built yet)
                 build-server-iso.sh    ─▶  aether-server-0.1-x86_64.iso
```

1. `install-server-assets.sh /path/to/offline/root` installs the versioned
   assets, the role catalog as `/usr/share/aether/server/roles.json`, the
   per-role templates, the `aether-server-install-backend` and `server_roles.py`
   under `/usr/libexec/`, and the `aether-server-setup` / `aether-directory`
   launchers. It finishes by running the backend's `--validate` inside the
   chroot, so a catalog that fails to parse stops the image build.
2. `configure-server.py --root …` (or run inside a chroot) records
   `/etc/aether/server-version`, sets `multi-user.target` as default, enables
   `aether-server-firstboot.service`, creates the directories the shipped role
   templates assume (`/srv/www`, `/srv/aether`, `/srv/restic`,
   `/var/log/remote`, `/etc/aether`, `/etc/aether-security`), and writes a
   default empty `firewall.json`.
3. `build-server-packages.py --list` reads the catalog and prints exactly what
   each role would be built from. `--build` is the bring-up path that compiles
   each backlogged recipe into the base, which is what flips a role's status
   from *unavailable* to *available*.
4. `build-server-iso.sh` builds the initrd, squashes the root (`-one-file-system`,
   excluding dev/proc/sys/run/build/sources/recipes), writes a console-first
   GRUB menu (install/try, live diagnostics, UEFI firmware settings) on serial +
   console, and emits `aether-server-0.1-x86_64.iso` via `grub-mkrescue`. It
   refuses to run while another server build holds the build lock.

## Tests

`test-server-roles.py` exercises the catalog, the backend helpers and the role
application path entirely off-line (`python3 test-server-roles.py`; 23 tests).
It validates the catalog, checks every role's templates exist, applies roles to
a throwaway root and asserts the configs/services/firewall/audit results, and
verifies the directory-join writers. Nothing here needs root, Linux, Qt, or a
real image.

## Status — say it plainly

- The **layout and the catalog→build mapping** are designed and tested as far
  as they can be off-line.
- **No server ISO, no built role software, no adcli, and no booted server.**
  `build-server-packages.py` is scaffolding: none of its recipes has been
  compiled and no source pins exist for the role packages yet. Bringing up the
  first package is a real bring-up task with per-package build logs, like the
  desktop's `--domain` chain was.
- The one thing that is already exercised is the mapping itself: `--list` reads
  the catalog and prints exactly what each role would be built from.