#!/usr/bin/env python3
"""Install Aether's login options: automatic login and Active Directory.

Automatic login is a LightDM seat setting and is off by default. Active
Directory needs the sssd dependency chain; when sssd is absent the domain
pieces are skipped so the desktop still builds and boots.
"""
from pathlib import Path
import os
import shlex
import subprocess

release = Path('/etc/os-release').read_text()
if not any(line in ('ID=aether', 'ID="aether"') for line in release.splitlines()):
    raise SystemExit('Refusing to configure a non-Aether system')

def write(name, contents, mode=0o644):
    p = Path(name)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(contents)
    p.chmod(mode)

# Both options start disabled. The state file is the single record of intent;
# aether-login rewrites it whenever an option changes.
write('/etc/aether/login.conf', '''# Aether login options. Managed by aether-login; edit that instead.
AUTOLOGIN_USER=
AD_ENABLED=0
AD_DOMAIN=
AD_REALM=
''')

# Automatic login is off until a user opts in, so a stale drop-in from an
# earlier install cannot silently start skipping the greeter.
autologin = Path('/etc/lightdm/lightdm.conf.d/70-aether-autologin.conf')
if autologin.exists():
    autologin.unlink()

# pam_sss is the marker for whether the AD stack was built.
pam_sss = [p for p in (Path('/usr/lib/security/pam_sss.so'), Path('/lib/security/pam_sss.so'))
           if p.exists()]
sssd = [p for p in (Path('/usr/sbin/sssd'), Path('/usr/bin/sssd')) if p.exists()]

if sssd and pam_sss:
    # Presence of this file is what tells the greeter that a domain name may be
    # typed at sign-in. It exists only where sssd was actually built.
    write('/etc/aether/domain-login', '# Presence marks an Active Directory capable system.\n')
    # Both modules are sufficient, so a local account never waits on the domain
    # and a domain account is not rejected by the final deny. faillock's
    # preauth check and Aether's sign-in delay are preserved.
    write('/etc/pam.d/sddm', '''# Aether greeter: local accounts first, Active Directory when joined.
auth       optional      pam_faildelay.so delay=3000000
auth       requisite     pam_nologin.so
auth       required      pam_faillock.so preauth silent
auth       sufficient    pam_unix.so try_first_pass
auth       sufficient    pam_sss.so ignore_unknown_user
auth       required      pam_deny.so
account    required      pam_access.so
account    sufficient    pam_unix.so
account    sufficient    pam_sss.so ignore_unknown_user
account    required      pam_deny.so
password   include       system-password
session    required      pam_env.so
session    required      pam_limits.so
session    include       system-session
''')
    if subprocess.run(['getent', 'group', 'sssd'], capture_output=True).returncode != 0:
        subprocess.run(['groupadd', '--system', 'sssd'], check=True)
    if subprocess.run(['getent', 'passwd', 'sssd'], capture_output=True).returncode != 0:
        subprocess.run(['useradd', '--system', '--gid', 'sssd', '--home-dir', '/var/lib/sss',
                        '--shell', '/usr/bin/false', 'sssd'], check=True)
    Path('/var/lib/sss').mkdir(parents=True, exist_ok=True)
    subprocess.run(['chown', 'sssd:sssd', '/var/lib/sss'], check=True)
    if Path('/etc/sssd').exists():
        Path('/etc/sssd').chmod(0o700)
    if subprocess.run(['systemctl', '--root=/', 'cat', 'sssd.service'],
                      capture_output=True).returncode == 0:
        subprocess.run(['systemctl', '--root=/', 'enable', 'sssd.service'], check=True)
    print('Automatic login available; Active Directory wired up through sssd.')
    print('Join a domain with: sudo aether-login ad join DOMAIN')
    # sssd signs a joined machine in, but the join itself is done by adcli, which
    # Aether does not build. Say so at build time rather than letting the join
    # fail later on a machine that looks domain-ready.
    if not Path('/usr/bin/adcli').exists():
        print('WARNING: adcli is absent, so "aether-login ad join" cannot run.')
        print('         Sign-in works on a machine joined by other means;')
        print('         add adcli to the build to join one from here.')
else:
    missing = []
    if not sssd:
        missing.append('sssd')
    if not pam_sss:
        missing.append('pam_sss.so')
    print('Automatic login available; Active Directory unavailable (missing '
          + ', '.join(missing) + ').')
    print('Build the sssd dependency chain to enable domain sign-in.')

subprocess.run(['sh', '-n', '/usr/bin/aether-login'], check=True)
result = subprocess.run(['/usr/bin/aether-login', 'check'], capture_output=True, text=True)
print(result.stdout.strip())
if result.returncode != 0:
    raise SystemExit('aether-login check failed: ' + (result.stderr.strip() or 'unknown'))
print('Login options configured; both start disabled and need a boot test.')
