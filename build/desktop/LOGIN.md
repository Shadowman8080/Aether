# Aether login options

Aether exposes two login options. Both are opt-in and both start disabled.

| Option | What it does | Where it lives |
| --- | --- | --- |
| Automatic login | Signs one local account in at boot with no password prompt | LightDM seat setting + greeter support |
| Active Directory | Signs a domain user in through sssd | sssd + Kerberos + NSS/PAM |

Everything is driven by one command:

```sh
aether-login                     # report both options
aether-login check               # exit non-zero if the state is unusable
sudo aether-login autologin on  # or: on <user>
sudo aether-login autologin off
sudo aether-login ad join EXAMPLE.COM --user 'DOMAIN\join-account'
sudo aether-login ad leave
aether-login ad status
```

State is recorded in `/etc/aether/login.conf` (root-owned). The automatic login
drop-in is `/etc/lightdm/lightdm.conf.d/70-aether-autologin.conf`.

## Automatic login

`autologin on` writes a LightDM drop-in with `autologin-user`,
`autologin-user-timeout=0` and `autologin-session` taken from the seat's
configured `user-session`, so an automatic sign-in lands in the same session a
manual sign-in would have chosen. `autologin off` removes the file.

Two details matter:

- **The greeter deliberately does nothing.** LightDM performs automatic login
  itself. Aether's greeter normally starts a PAM transaction as soon as it
  connects; doing that during automatic login would cancel the daemon's
  transaction and strand the seat at an empty password prompt. The greeter
  therefore reads the LightDM configuration itself and, when the configured
  automatic account is the account it would have selected, it shows
  "Signing in automatically" and waits instead of authenticating.
- **Only one local account is affected**, and it must already exist. The tool
  refuses a name that is not a real account. `aether-login check` fails if the
  configuration points at a user that has since been removed, so a stale
  drop-in cannot silently lock anyone out of a seat.

This is a security downgrade by design: the seat is unlocked without a
password. It is a deliberate local choice, which is why it is per-seat and
reversible rather than a build default.

## Active Directory

Domain sign-in needs sssd. Aether had no AD client at all before this work; the
PAM stack was `pam_unix` only.

### Build stage

`build/desktop/scripts/build-desktop-domain.py` builds the chain:

| Package | Version | Why |
| --- | --- | --- |
| libunistring | 1.3 | required by sssd |
| talloc | 2.5.0 | required by sssd |
| libevent | 2.1.12-stable | also ships tevent, required by sssd |
| ldb | 2.6.2 | required by sssd |
| c-ares | 1.34.8 | CLDAP resolver behind the AD provider |
| krb5 | 1.22.2 | Kerberos for AD |
| sssd | 2.13.1 | the AD client itself |

Run it with the normal stage runner:

```sh
scripts/run-desktop-build.sh build-desktop-domain.py
```

It is optional. Without it the desktop still builds and boots, and
`aether-login` reports that domain sign-in is unavailable. Missing the stage
never breaks a build.

### How it is wired

`build/desktop/scripts/configure-login-options.py` runs in the offline root
after the desktop is configured, and only when sssd is actually present:

- creates the `sssd` system account and `/var/lib/sss`
- enables `sssd.service`
- writes `/etc/aether/domain-login`, whose presence is what makes the greeter
  offer a domain field
- rewrites `/etc/pam.d/sddm`

The PAM stack keeps local accounts and Aether's sign-in delay intact while
letting domain accounts through:

```
auth       optional      pam_faildelay.so delay=3000000
auth       requisite     pam_nologin.so
auth       required      pam_faillock.so preauth silent
auth       sufficient    pam_unix.so try_first_pass
auth       sufficient    pam_sss.so ignore_unknown_user
auth       required      pam_deny.so
```

Both `pam_unix` and `pam_sss` are `sufficient`, so whichever succeeds ends the
stack successfully and the final `pam_deny` only fires when neither matched.
`ignore_unknown_user` means a local sign-in does not wait on the domain.

`ad join` writes `/etc/krb5.conf` and `/etc/sssd.conf` (mode 0600), adds `sss`
to `passwd`, `group`, `shadow` and `hosts` in `/etc/nsswitch.conf` after
`files`, and calls adcli. `ad leave` reverses all of it and leaves local
accounts untouched.

### Signing in

The greeter adds a user-name field when `/etc/aether/domain-login` exists. Type
either form and it is passed to LightDM unchanged for sssd to resolve:

```
jane
jane@example.com
EXAMPLE\jane
```

Local names stay restricted to `^[a-z][a-z0-9_-]{0,30}$`. Domain-qualified
names are only accepted where sssd was built.

## Verification status

Read this before claiming any of it works.

### aether-login

`scripts/test-aether-login.sh` runs the tool against a throwaway root
(`AETHER_LOGIN_ROOT`), so it exercises the real file handling without touching
the system: the automatic login drop-in and its contents, `seat_session`
reading `user-session`, the missing-user failure in `check`, the full
`ad join` and `ad leave` round trip against a stub sssd and a stub adcli,
`sssd.conf` and `krb5.conf` contents, `nsswitch.conf` insertion and reversal,
the join tool being reported present and absent, and rejection of bad input.

```
sh build/desktop/scripts/test-aether-login.sh
PASS=62 FAIL=0 SKIP=1
```

The skip is `sssd.conf`'s 0600 mode: the filesystem used for that run ignores
`chmod`, so the mode could not be checked and is not claimed. Re-run the suite
on Linux to cover it.

Real system effects are **not** covered: service control is skipped against a
test root, and no join ever contacted a domain controller.

### Automatic login

The greeter change is **not** compiled and **not** booted. It needs a real boot
test: enable it, reboot, confirm the desktop comes up unattended, then confirm
the greeter asks for a password again after `autologin off`.

### Active Directory

**Not built and not tested.** The chain in `build-desktop-domain.py` has never
been compiled, so its configure options are unvalidated; treat the first run as
a bring-up and read `/build/logs/<package>.log`. End-to-end sign-in
additionally needs a real domain controller, which Aether has never been
pointed at.

Joining a domain also needs **adcli**, which performs the machine account join.
adcli is *not* in `configs/direct-sources.json`, because its upstream could not be
obtained and no digest was invented in its place. Until it is added,
`aether-login ad join` fails with a clear message, `ad status` reports the join
tool as missing and says why, and `ad leave` still works. A machine joined by
other means still signs in through sssd.

Routes ruled out while looking for it, so they need not be tried again:

| Source | Result |
| --- | --- |
| `freedesktop.org/software/adcli/releases/` (http and https) | HTTP 418 anti-bot challenge |
| `gitlab.freedesktop.org/.../-/archive/...tar.gz` | HTTP 200 but a 7 KB `<!do...` HTML challenge, not a tarball |
| `git ls-remote gitlab.freedesktop.org/polkit-gnome/adcli` | `HTTP Basic: Access denied`; anonymous git now needs a token |
| Nixpkgs `fetchFromGitLab` hash for `realmd/adcli` `0.9.3a` | resolves, but it is a NAR hash of the *unpacked* tree, not the tarball sha256, so it is not usable as `sha256_expected` |
| Fedora `src.fedoraproject.org` dist-git and lookaside | HTML login interstitial instead of the tarball |
| `sources.debian.org` | proof-of-work challenge; `snapshot.debian.org` has no adcli at all |
| Launchpad, Buildroot, Gentoo distfiles, Termux, Void | no adcli package |

Adding it needs a real tarball plus its digest, from either upstream on a host
that is not being challenged or a mirror that serves the identical upstream
bytes. It also pulls in two more dependencies Aether does not yet build:
openldap and cyrus-sasl.

Source digests are pinned in `configs/direct-sources.json` and enforced at
fetch time. sssd's digest was verified against the `sha256sum` file published
with the upstream release; the other six were computed from the upstream HTTPS
tarballs.