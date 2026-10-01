from pathlib import Path
r = Path('/opt/aether')
# Retain the original 0.1 packaging recipe and ISO as a known-good baseline.
s = (r/'scripts/make-iso.sh').read_text()
s = s.replace('build/iso-stage', 'build/iso-stage-guest')
s = s.replace('aether-0.1-x86_64.iso', 'aether-0.1.1-x86_64.iso')
s = s.replace('AETHER_01', 'AETHER_011').replace('0.1-dev', '0.1.1-dev')
s = s.replace('0.1 - First Light', '0.1.1 - VM guest console')
s = s.replace('rdinit=/init\n', 'rdinit=/init quiet loglevel=3\n')
# Do not overwrite legacy standalone kernel/initramfs/checksum artifacts.
s = s[:s.index('cp "$src/bzImage"')]
(r/'scripts/make-guest-iso.sh').write_text(s)
for arch, original in [('x86_64', 'test-boot.py'), ('x86', 'test-boot-x86.py')]:
    t = (r/'scripts'/original).read_text()
    t = t.replace(f'aether-0.1-{arch}.iso', f'aether-0.1.1-{arch}.iso')
    t = t.replace("f'boot-", "f'boot-guest-")
    (r/'scripts'/f'test-guest-{arch}.py').write_text(t)
for name in ['overlay', 'overlay-x86', 'overlay-arm64']:
    overlay = r/name
    (overlay/'usr/bin').mkdir(parents=True, exist_ok=True)
    for source, dest in [('S51vboxservice','etc/init.d/S51vboxservice'),
                         ('aether-guest-status','usr/bin/aether-guest-status')]:
        path = overlay/dest
        path.write_text((r/'scripts'/source).read_text())
        path.chmod(0o755)
    p = overlay/'etc/init.d/S99aether'
    t = p.read_text()
    if 'aether-guest-status' not in t:
        t = t.replace('    uname -a', '''    if [ -x /usr/sbin/VBoxService ] && [ -x /usr/bin/vmtoolsd ]; then
        check /usr/bin/aether-guest-status
        if /usr/bin/vmware-checkvm >/dev/null 2>&1; then
            check pidof vmtoolsd
        fi
        if [ -c /dev/vboxguest ]; then check pidof VBoxService; fi
    fi
    uname -a''')
        p.write_text(t)
