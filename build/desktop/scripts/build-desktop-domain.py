#!/usr/bin/env python3
"""Active Directory prerequisites: MIT Kerberos and sssd; no host packages.

This is an optional stage. Without it the desktop still builds and boots, and
aether-login reports that domain sign-in is unavailable.

NOT YET BUILT. This chain has never been compiled on the build host, so the
configure options below are unvalidated. Treat the first run as a bring-up:
watch /build/logs/<package>.log for each package and fix options as needed
before shipping an image that claims domain sign-in.
"""
from pathlib import Path
import runpy
import subprocess

ns = runpy.run_path('/recipes/scripts/build-desktop-foundation.py')
build = ns['build']

# sssd's configure.ac requires these five, plus dbus-1 and Linux-PAM, which the
# desktop already provides. libunistring is required but not obvious from the
# sssd documentation.
build('libunistring', 'autoconf')
# talloc pulls no Python: sssd only needs the shared library.
build('talloc', 'autoconf', ['--without-python'])
# libevent also ships tevent, which sssd requires. Samples, benchmarks and the
# regression suite are not needed and only slow the build down.
build('libevent', 'autoconf', ['--disable-samples', '--disable-libevent-regress',
                               '--without-openssl', '--without-bpf'])
# ldb ships command line tools that sssd does not use.
build('ldb', 'autoconf', ['--without-tools'])
# c-ares is the CLDAP resolver behind the sssd AD provider.
build('c-ares', 'cmake', ['-DCARES_STATIC=OFF', '-DCARES_SHARED=ON',
                          '-DCARES_BUILD_TESTS=OFF', '-DCARES_BUILD_TOOLS=OFF'])
# MIT Kerberos. libedit and GNU Readline are deliberately omitted: krb5 only
# wants them for interactive line editing in kadmin, GNU removed libedit from
# its FTP tree, and pulling in Readline would add a GPL dependency for nothing.
build('krb5', 'autoconf', ['--without-libedit', '--without-readline'])
# sssd. Modern sssd enables its AD provider as soon as c-ares, krb5, ldb,
# talloc and tevent are present, so there is no provider switch to pass. The
# directory options decide where the NSS and PAM modules land, which is what
# Aether's own PAM configuration refers to.
build('sssd', 'autoconf', [
    '--enable-nsslibdir=/usr/lib',
    '--enable-pammoddir=/usr/lib/security',
    '--without-python3-bindings',
    '--with-adcli-path=/usr/bin',
    '--with-sssd-user=sssd',
])

for name in ('/usr/lib/security/pam_sss.so', '/usr/lib/libnss_sss.so', '/usr/sbin/sssd'):
    if not Path(name).exists():
        raise SystemExit('Active Directory stage did not produce ' + name)

print('Active Directory prerequisites built. Run configure-login-options.py next;')
print('joining a domain additionally needs adcli, which is not in the source manifest.')