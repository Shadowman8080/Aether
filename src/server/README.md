# Aether Server 0.1 — the server edition

Aether Server is the console-first server edition of Aether, in the spirit of
Ubuntu Server: no Plasma desktop, a `multi-user.target` boot, and an
interactive **graphical** installer that also runs from the plain console. It
installs an administrator account with sudo, configures the network, applies a
data-driven set of server roles, and can join an Active Directory domain during
installation.

Like everything else in Aether, the edition is honest about state: a role whose
software is not built into the image is **reported as unavailable**, not
silently skipped, and not allowed to fail the whole install.

```
src/server/
├── backend/
│   ├── server_roles.py        role catalog loading, validation, applying,
│   │                          firewall merge, audit report, AD config writers
│   └── aether-server-install  privileged installer backend (pxexec entrypoint)
├── installer/
│   ├── main.cpp               Qt6 graphical installer wizard
│   ├── CMakeLists.txt         builds the aether-server-installer binary
│   ├── aether-server-setup    launcher: picks Wayland/xcb/linuxfb/eglfs, or TTY
│   └── aether-directory       post-install AD join / leave / status tool
├── roles/
│   ├── catalog.json           the data-driven role catalog (the single source
│   │                          of truth for the UI and the backend)
│   └── configs/<role>/…       per-role configuration templates
└── assets/
    └── usr/                   polkit action, .desktop entry, /etc/issue,
                               /etc/motd, default firewall.json,
                               aether-server-firstboot.service + script
```

## The role catalog is data, not code

`roles/catalog.json` defines every role. The Qt installer and the Python
backend read the **same** file (the installed copy at
`/usr/share/aether/server/roles.json`, overridable with
`AETHER_SERVER_CATALOG`). Adding a role means adding a catalog entry plus a
config template under `roles/configs/` — no UI or backend change.

The catalog is schema-1 with a mandatory `schema`, `config_root`, `categories`
and `roles` array. Every role declares:

| Field | Meaning |
|---|---|
| `id` | stable identifier used in the request JSON and CLI |
| `name` / `summary` | what the UI shows |
| `category` | one of the catalog's category ids |
| `packages` | source-built packages a role needs |
| `binaries` | absolute paths checked to decide *available* vs *unavailable* |
| `services` | unit names to enable when the role applies |
| `configs` | `source` (relative, under `config_root`) → `destination` (absolute), plus `mode` |
| `firewall` | `tcp/N` / `udp/N` entries merged into `/etc/aether-security/firewall.json` |
| `default` / `recommended` | default selection and UI hints |
| `notes` | honest operational warning shown in the role detail pane |

`validate_catalog()` runs on every load, so a malformed catalog fails loudly at
install start instead of halfway through writing configuration. Firewall
entries, config destinations, binary paths and category references are all
checked. See `backend/server_roles.py` for the exact rules and
`build/server/scripts/test-server-roles.py` for the suite that enforces them.

### Availability

At apply time each role's `binaries` are checked inside the installed root. If
none are present the role is reported as **unavailable** (nothing written). If
config templates or some binaries are missing it is reported as **partial**. An
available role copies its templates, writes the service enablement (or reports
which units are missing), and merges its firewall ports. Every decision is
recorded in an audit report written during installation.

## The installer

`installer/main.cpp` is a Qt6 (Widgets + Svg) `QWizard`. Pages cover:

1. Welcome — whole-disk warning, exactly as the desktop installer
2. Region — keyboard, timezone
3. Network — hostname, DHCP or static IPv4 (address/gateway/DNS/interface)
4. Storage — disk selection (≥ 16 GiB, unmounted, writable), optional LUKS2
   with separate storage and recovery passphrases
5. **Roles** — the catalog rendered as a checkbox tree grouped by category,
   with per-role software/services/ports/notes in a detail pane, plus
   *Select recommended / Select all / Clear all*
6. **Directory** — optional Active Directory join (domain, join account,
   computer name, password), plus a first-run password note if enabled
7. Account — administrator name and password (≥ 12 chars, confirmed)
8. Review — a summary of everything selected and the exact
   `ERASE /dev/…` confirmation
9. Install — progress rendered from the backend's `AETHER_PROGRESS` lines

The wizard talks to the privileged backend through `pkexec` under the
`org.aether.serverinstall` policy action (polkit `auth_admin`). The request is
a single JSON object on stdin; passwords never appear on the command line and
are never echoed back.

`aether-server-setup` launches the wizard with the lightest Qt platform that
exists: an active Wayland/X11 session, then `linuxfb` (no compositor at all),
then `eglfs`. `AETHER_SERVER_QT_PLATFORM` overrides the choice and
`AETHER_SERVER_TTY=1` runs the text installer instead — both paths reach the
identical backend, so the console flow is exactly the graphical flow minus the
window.

## The backend

`backend/aether-server-install` is the privileged half. It validates the
request (hostname, timezone, keyboard, `libpwquality` password policy, network,
roles against the catalog, directory settings), refuses anything that is not a
real, unmounted, writable whole disk ≥ 16 GiB, and only then performs the
installation in nine progress steps.

```
 1  Prepare the GPT disk (EFI, 512M /boot, 1G boot partition, root)
 2  Create LUKS2 storage when requested (argon2id, recovery passphrase)
 3  Create filesystems
 4  Copy Aether Server from the live image
 5  Set up the administrator account, sudoers wheel rule, timezone/keymap
 6  Network (hostname, hosts, NetworkManager profile), multi-user target,
    apply the selected roles (configs + services + firewall merge + audit)
 7  Join the Active Directory domain when requested
 8  Install the boot environment (initramfs, GRUB BIOS + UEFI, grub.cfg)
 9  Finish — report unavailable/partial roles honestly
```

The backend doubles as the interactive console tool: run
`sudo aether-server-install` without arguments on the live ISO and it prompts
for the same information, then follows the identical code path.

`backend/server_roles.py` is deliberately free of CLI handling so the tests can
import it and apply any catalog against a throwaway root directory.

## Active Directory join

The Directory page (and the console prompt) can join an AD domain during
installation. The backend writes `krb5.conf`, `sssd.conf`, the PAM/sshd stacks
and the `nsswitch.conf` sss entries directly, adapted from the desktop's sssd
work in `build/desktop/scripts/build-desktop-domain.py`.

The machine-account join itself is attempted **only if `adcli` is present in
the image**. Today it is not built, so the installer says so, marks the join
pending (`AD_JOINED=0` in `/etc/aether/directory.conf`), and the
`aether-server-firstboot` service prints a motd warning with the exact command:

```
sudo aether-directory join EXAMPLE.LAN --user <join-account>
```

`installer/aether-directory` performs the real join / leave / status after
boot, and is the tool the firstboot notice points at. Local accounts are never
touched and, except for `join`, nothing contacts the domain. Setting
`AETHER_DIRECTORY_ROOT` lets the file handling run against a scratch root for
tests.

## First boot

`aether-server-firstboot.service` runs once per installed system
(`ConditionPathExists=!/var/lib/aether/firstboot.done`) and:

- regenerates SSH host keys (the installed system is a copy of the live image,
  so a shared key set would let one install impersonate another),
- seeds a fresh machine-id,
- writes the pending-join motd notice when sssd config exists but the join is
  still pending.

The installed system boots to `multi-user.target` on a serial-enabled console,
with GRUB entries for Aether Server and a verbose recovery console.

## Honest status

- The **role catalog, backend logic, installer UI and build scripts** exist and
  the catalog/backend path is exercised by 23 unit tests
  (`build/server/scripts/test-server-roles.py`, all green).
- The **Qt installer has not been compiled** and **nothing has been booted.**
  This is unvalidated work-in-progress, exactly like the desktop's own
  bring-up. There is no server ISO, no built role software, no adcli, and no
  domain join that has ever run against a real domain controller.
- `build/server/scripts/build-server-packages.py` is the *plan* for turning the
  catalog into source builds; none of its recipes is compiled yet.