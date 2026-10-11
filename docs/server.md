# Aether Server edition

The server edition is Aether's console-first image in the spirit of Ubuntu
Server: no desktop session, boot to `multi-user.target`, administer over SSH,
and install everything else from a data-driven role catalog. The graphical
installer — same Qt stack as the desktop installer, running on the lightest
available platform — is the entry point, with an identical console fallback.

## Role catalog

`src/server/roles/catalog.json` is the single source of truth. The installer UI
and the install backend read the same file (installed to
`/usr/share/aether/server/roles.json`, overridable with `AETHER_SERVER_CATALOG`).
The schema is validated on every load; see
[`src/server/README.md`](../src/server/README.md) for the field-by-field
contract.

27 roles across 7 categories. All of the originally requested roles are present
(DHCP, NTP, RADIUS/TACACS+, syslog, file, database, FTP, web, application, mail,
proxy, hypervisor, print), plus the additions below.

### Network infrastructure

| Role | Software | Opens |
|---|---|---|
| DHCP server | Kea (`kea-dhcp4`) | `udp/67` `udp/68` |
| DNS server | BIND 9 | `tcp/53` `udp/53` |
| NTP server | chrony | `udp/123` |
| AAA server (RADIUS / TACACS+) | FreeRADIUS + `tac_plus` | `udp/1812` `udp/1813` `tcp/49` |
| Reverse proxy / load balancer | HAProxy | `tcp/80` `tcp/443` |

### Identity, access and security

| Role | Software | Opens |
|---|---|---|
| OpenSSH server *(default, recommended)* | OpenSSH | `tcp/22` |
| VPN server (WireGuard) | wireguard-tools | `udp/51820` |
| Directory server (OpenLDAP) | slapd | `tcp/389` `tcp/636` |
| Certificate authority | step-ca | `tcp/8443` |
| AD-compatible domain controller | Samba AD DC | `tcp/53` `udp/53` `tcp/88` `tcp/389` `tcp/445` `tcp/464` `udp/464` `tcp/636` `tcp/3268` |

### Logging and monitoring

| Role | Software | Opens |
|---|---|---|
| Central syslog server | rsyslog | `tcp/514` `udp/514` |
| Monitoring and dashboards | Prometheus, Grafana, node_exporter | `tcp/9090` `tcp/3000` |

### Storage and data

| Role | Software | Opens |
|---|---|---|
| File server (Samba) | Samba | `tcp/445` `tcp/139` `udp/137` `udp/138` |
| Database server (PostgreSQL) | PostgreSQL | `tcp/5432` |
| FTP server (vsftpd) | vsftpd | `tcp/21` |
| Backup server (restic REST) | rest-server | `tcp/8000` |

### Web and internet services

| Role | Software | Opens |
|---|---|---|
| Web server (Nginx) *(recommended)* | Nginx | `tcp/80` `tcp/443` |
| Application server (PHP-FPM) | PHP-FPM | *(unix socket only)* |
| Mail server (Postfix + Dovecot) | Postfix, Dovecot | `tcp/25` `tcp/465` `tcp/587` `tcp/143` `tcp/993` |
| Proxy server (Squid) | Squid | `tcp/3128` |
| Git server (Gitea) | Gitea | `tcp/3000` `tcp/22` |

### Compute and virtualization

| Role | Software | Opens |
|---|---|---|
| Virtualization host (libvirt / KVM) | libvirt, QEMU | *(network-specific)* |
| Container host (Podman) | Podman | *(per-container)* |

### Business and collaboration

| Role | Software | Opens |
|---|---|---|
| Print server (CUPS) | CUPS | `tcp/631` `udp/631` |
| VoIP / PBX server (Asterisk) | Asterisk | `udp/5060` `tcp/5060` |
| Media streaming server (Jellyfin) | Jellyfin | `tcp/8096` |
| CI/CD runner (GitLab Runner) | gitlab-runner | *(outbound only)* |

Roles defined as *"network-specific"* or *"per-container"* do not open global
ports — the firewall stays closed and the software publishes its own endpoints
deliberately. The shipped templates are deliberately conservative (SSH forbids
root login, PostgreSQL listens on loopback, Squid and DNS recursion are
loopback/subnet-only, the CA keeps its key local).

## The install path

The flow, shared by the graphical wizard and the console installer:

```
Qt wizard (pkexec)               console (sudo aether-server-install)
        │  JSON on stdin                     │  prompts
        ▼                                    ▼
        └─────────────► aether-server-install-backend
                        1  GPT disk layout (EFI + /boot + root)
                        2  LUKS2 (argon2id) + recovery passphrase
                        3  filesystems (fat32 / ext4)
                        4  copy live image, regenerate nothing yet
                        5  administrator account + sudoers wheel rule
                           timezone, keymap
                        6  hostname, NetworkManager profile (DHCP or static)
                           multi-user.target → apply roles:
                           configs → services → firewall merge → audit report
                        7  directory join (see below)
                        8  initramfs, GRUB (BIOS + UEFI), grub.cfg
                        9  report unavailable / partial roles honestly
```

The wizard renders `AETHER_PROGRESS {"step":N,"message":…}` lines emitted by
the backend. Capabilities and limits are enforced at request time, before the
disk is touched: minimum 12-character passwords with `libpwquality`, valid
hostname/domain/IP, roles that exist in the catalog, a ≥ 16 GiB unmounted
writable whole disk, and the exact `ERASE /dev/…` confirmation.

## Firewall integration

Role firewall entries are merged into the target's
`/etc/aether-security/firewall.json` — the same file `aether-firewall` reads.
The merge is a union across the selected roles, so the default-deny posture of
the base is preserved and only the chosen roles' ports open. The image ships
with an empty firewall state; nothing is open unless a role asked for it.

## Active Directory join

Joining a domain is an option at install time and a first-class tool after it:

- **Configuration is written during installation** — `krb5.conf`, `sssd.conf`,
  the PAM/sshd stacks and `nsswitch.conf` sss entries — adapted from the
  desktop's sssd work in `build/desktop/scripts/build-desktop-domain.py`. The
  `sss` source is inserted directly after the first `nsswitch` source so local
  accounts keep resolving first.
- **The machine account is created during installation only if `adcli` exists
  in the image.** It does not today. The installer says so, records
  `AD_JOINED=0` in `/etc/aether/directory.conf`, and the firstboot service
  prints a motd warning pointing at the exact command:
  `sudo aether-directory join EXAMPLE.LAN --user <join-account>`.
- **`aether-directory`** (`join` / `leave` / `status`) is the post-install
  tool. Only `join` contacts the network; local accounts are never touched.
  `AETHER_DIRECTORY_ROOT` lets its file handling run against a scratch root.

This is the honest path: the configuration is real, the join is not claimed to
have run. Nothing boots with a silently half-configured domain setup.

## First boot

`aether-server-firstboot.service` runs once and regenerates the SSH host keys
(live images otherwise share keys), seeds a fresh `machine-id`, and installs the
pending-join notice. The system boots to `multi-user.target` on a
serial-enabled console with GRUB entries for normal boot and a verbose
recovery console.

## Verification status

- **Unit-tested off-line:** catalog schema, role application, firewall merge,
  audit report, and the directory-join writers (23 tests in
  `build/server/scripts/test-server-roles.py`). Everything runs without Linux,
  Qt, root, or an image.
- **Not built:** no server ISO, no compiled Qt installer, no built role
  software, no adcli, no domain join exercised against a real domain
  controller, no booted server. The build pipeline
  (`build-server-iso.sh`, `build-server-packages.py`) is validated as far as
  static checks and the catalog→recipe mapping allow.
- **Not hardware tested:** no physical server, no VM, x86_64 only for now.

Releasing this edition requires the same gates as the desktop: a real built
image, a booted install, and each claimed role verified by running its service.

## Building

See [`build/server/README.md`](../build/server/README.md) and
[`src/server/README.md`](../src/server/README.md). The short version:

```sh
# install assets into an offline Aether root, then finish the image
scripts/install-server-assets.sh /opt/aether/server-root
python3 scripts/configure-server.py --root /opt/aether/server-root
scripts/build-server-iso.sh          # → aether-server-0.1-x86_64.iso
```

Each role package must be source-built into the base before its role reports as
*available* (`scripts/build-server-packages.py --list` shows the plan).