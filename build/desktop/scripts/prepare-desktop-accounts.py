#!/usr/bin/env python3
"""Prepare unprivileged service accounts in the native build root."""
import grp
import pwd
import subprocess
from pathlib import Path

for name, home in [('polkitd', '/var/lib/polkit-1'), ('sddm', '/var/lib/sddm'),
                   ('avahi', '/run/avahi-daemon')]:
    try:
        grp.getgrnam(name)
    except KeyError:
        subprocess.run(['groupadd', '--system', name], check=True)
    try:
        pwd.getpwnam(name)
    except KeyError:
        subprocess.run(['useradd', '--system', '--gid', name, '--home-dir', home,
                        '--shell', '/usr/bin/false', name], check=True)
    if home.startswith('/var/'):
        path = Path(home)
        path.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.chown(path, name, name)
