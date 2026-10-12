# Architecture

Aether is assembled from source into a coherent stack. This document describes
the layers, how they talk to each other, and — just as importantly — where the
seams are still unfinished.

## Layer stack

```
┌──────────────────────────────────────────────────────────────┐
│  Session            LightDM  →  Aether greeter              │
│                     systemd user session, Wayland or X11     │
├──────────────────────────────────────────────────────────────┤
│  Shell              KDE Plasma 6 + Aether look-and-feel      │
│                     Plasma shell layout, power menu plasmoid │
├──────────────────────────────────────────────────────────────┤
│  First-party apps   AuraSearch   launcher / search / calc    │
│                     Nimbrel      on-device AI assistant      │
│                     Vector       applications & files       │
│                     Aether Devices  plug-and-play manager   │
│                     Aether Security Center, installer        │
├──────────────────────────────────────────────────────────────┤
│  Integration        NetworkManager (DHCP/DNS)               │
│                     PipeWire + WirePlumber (audio)           │
│                     xdg-desktop-portal, CUPS printing portal  │
├──────────────────────────────────────────────────────────────┤
│  Security           nftables 1.1.7 default-deny              │
│                     AppArmor 4.1.8, Yama, Landlock           │
│                     PAM (yescrypt), logind seat access       │
│                     cryptsetup/LUKS2, restic 0.19.1 backups   │
├──────────────────────────────────────────────────────────────┤
│  Init               systemd                                   │
├──────────────────────────────────────────────────────────────┤
│  Kernel             Linux 6.18.54-aether4 (in-tree build)   │
└──────────────────────────────────────────────────────────────┘
```

Everything below the shell is upstream KDE/Qt/systemd built from pinned sources.
Everything in the "First-party apps" row is Aether's own code and lives in
[`../src/`](../src).

## Nimbrel's request path

The AI subsystem is deliberately the narrowest part of the system. See
[`../src/nimbrel/README.md`](../src/nimbrel/README.md) for the full note.

```
Qt client  ──AF_UNIX──▶  /run/nimbrel/api.sock        (0666)
                            │  SO_PEERCRED → uid check
                            ▼
                         /run/nimbrel-engine/engine.sock  (0700)
                            │
                            ▼
                    llama-server, Qwen3.5 0.8B Q4_0, CPU only
```

`RestrictAddressFamilies=AF_UNIX` on `nimbrel-engine.service` means the engine
cannot create an IP socket. This is enforced by the kernel, not by the
application.

## Network posture

`nftables` runs a stateful IPv4/IPv6 **incoming and forwarding default-deny**
policy. DNS, DHCP, IPv6 discovery and normal outgoing client traffic continue to
work. A firewall reload owns only its own table, so other software's nftables
tables are preserved.

Deliberate exceptions must be opened on purpose:

```sh
sudo aether-firewall allow-tcp 8080
sudo aether-firewall status
```

Known rough edges: VPN and container routing need an explicit reviewed policy
because forwarding is denied by default, and there are no interface trust
profiles or outbound allowlists yet.

## Server edition

The server image (`src/server/`) is the desktop stack minus the session, booted
to `multi-user.target` and administered over SSH. Its install-time layering is
a second, deeper half of the security story: the server installer applies a
data-driven role catalog and merges each chosen role's ports into the
`/etc/aether-security/firewall.json` the base firewall reads, so the
default-deny posture is preserved and only announced roles open ports.

```
src/server/roles/catalog.json   the single source of truth (schema-1, validated
                                on every load)
  ├─ installer/main.cpp         Qt wizard — checkbox role tree, AD join page
  ├─ backend/aether-server-install   privileged (pkexec), steps 1–9
  └─ backend/server_roles.py    apply roles / firewall merge / audit / AD writers
```

The directory-join path writes the same krb5/sssd/PAM/nsswitch configuration
the desktop greeter work uses, then creates the machine account during install
only when `adcli` is present. It is not, so joins happen after boot through
`aether-directory`. See [`server.md`](server.md) for the full design.

## Update path

The 0.3.2 build installs an automatic check timer and an updater that verifies
TUF metadata and package signatures. Installation requires approval, prepares a
separate ext4 system copy with shared home directories, and uses a trial boot
with fallback and health confirmation. It never restarts automatically.

**Public release trust remains unconfigured.** No production signing keys are
shipped. Older base package ownership records also need reconciliation before
core OS updates. Flatpak application sources are configured separately.

See [update implementation](../src/updates/README.md),
[operator key setup](../src/updates/LOCAL-KEY-SETUP.md) and the
[current verification record](modern-desktop-20261006.md).

## Build organisation

The build is driven by Python "recipe" scripts that append to an Arch-style
package set. Groups follow the feature areas in
[`../build/desktop/README.md`](../build/desktop/README.md):

| Group | Covers |
|---|---|
| `desktop` | Qt, KDE Frameworks, Plasma, desktop applications, portals |
| `server` | role catalog, server installer, install backend, server image |
| `nimbrel` | native bindings, llama.cpp, engine packaging |
| `security` | PAM helper, firewall tooling, cryptsetup, backups |
| `updates` | python-tuf, GnuPG verification, release tooling |
| `assets` | wallpapers, colour schemes, screensavers, Plymouth, layouts |

All build CPUs are used; the 0.3 desktop build ran on 16.

## Where the seams are

These are architectural gaps, not just missing features:

- **No verified boot chain.** Secure Boot is disabled and module signatures are
  not enforced, so the kernel's integrity story stops at the bootloader.
- **`/boot` is unencrypted.** LUKS2 covers the root filesystem only.
- **No deployed repository.** The installed update and recovery tooling is tested,
  but production trust and repository infrastructure remain unconfigured.
- **Device hardware is source-built, not hardware-tested.** The plug-and-play
  layer (udev policy, the Aether Devices manager, hotplug notifications and the
  extra kernel driver classes) is implemented but has not been compiled into an
  image or booted on physical devices; there is still no hardware support
  policy.
- **Thin AppArmor coverage.** Most desktop applications run unconfined.
- **Session isolation is weaker on VMware.** Clipboard support causes X11 to be
  selected, which increases isolation risk between applications sharing a
  session.
- **Single architecture.** Only x86_64 is built; there is no 32-bit or ARM64
  desktop image and no multi-arch test coverage.
- **The server edition is design-tested, not built.** Its catalog and backend
  are unit-tested off-line, but no server ISO, Qt installer build, role
  software, adcli, or booted install exists yet. Every screenful of the server
  story after that point is unvalidated.