#!/usr/bin/env python3
"""Install native PAM policies after Linux-PAM, shadow and systemd are rebuilt."""
from pathlib import Path
import subprocess
root=Path('/etc/pam.d'); root.mkdir(parents=True,exist_ok=True)
policies={
 'system-auth':'auth required pam_unix.so try_first_pass\n',
 'system-account':'account required pam_unix.so\n',
 'system-password':'password required pam_unix.so yescrypt shadow try_first_pass\n',
 'system-session':'session required pam_unix.so\nsession optional pam_systemd.so\n',
 'other':'auth required pam_deny.so\naccount required pam_deny.so\npassword required pam_deny.so\nsession required pam_deny.so\n',
 'login':'auth optional pam_faildelay.so delay=3000000\nauth requisite pam_nologin.so\nauth include system-auth\naccount required pam_access.so\naccount include system-account\npassword include system-password\nsession required pam_env.so\nsession required pam_limits.so\nsession include system-session\n',
 'su':'auth sufficient pam_rootok.so\nauth include system-auth\naccount include system-account\npassword include system-password\nsession required pam_env.so\nsession include system-session\n',
 'passwd':'password include system-password\n',
 'chpasswd':'password include system-password\n',
 'sddm':'auth requisite pam_nologin.so\nauth include system-auth\naccount include system-account\npassword include system-password\nsession required pam_env.so\nsession required pam_limits.so\nsession include system-session\n',
 'sddm-greeter':'auth required pam_permit.so\naccount required pam_permit.so\npassword required pam_deny.so\nsession required pam_unix.so\nsession optional pam_systemd.so\n',
 'kde':'auth include system-auth\naccount include system-account\npassword include system-password\nsession include system-session\n',
 'polkit-1':'auth include system-auth\naccount include system-account\npassword include system-password\nsession include system-session\n',
 'systemd-user':'account include system-account\nsession required pam_unix.so\nsession required pam_loginuid.so\nsession optional pam_keyinit.so force revoke\nsession optional pam_systemd.so\n'
}
for name,content in policies.items():
 (root/name).write_text('# Aether Linux native desktop authentication\n'+content)
 (root/name).chmod(0o644)
# The greeter's PAM service only starts its dedicated unprivileged account;
# real user authentication always goes through the sddm service above.
subprocess.run(['groupadd','-f','wheel'],check=True)
subprocess.run(['usermod','-a','-G','wheel','aether'],check=True)
print('Native PAM policies installed; runtime login and lock tests are required.')

# Preserve installed Aether security defaults on subsequent desktop rebuilds.
if Path("/usr/libexec/aether-configure-security").is_file():
    subprocess.run(["python3", "/usr/libexec/aether-configure-security"], check=True)
