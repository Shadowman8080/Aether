from pathlib import Path
r = Path('/opt/aether')
p = r/'scripts/build-vbox.sh'
s = p.read_text().replace('VBOX_GCC_WERR =', 'DEFS.x86 += RT_WITH_OLD_CPU_SUPPORT\nVBOX_GCC_WERR =')
p.write_text(s)
s = (r/'scripts/refresh-guest-x64.sh').read_text()
s = s.replace('guest-x64', 'guest-x86').replace('build/prototype', 'build/prototype-x86')
s = s.replace('scripts/make-guest-iso.sh', 'scripts/make-guest-x86-iso.sh')
s = s.replace('test-guest-x86_64.py', 'test-guest-x86.py').replace('python3 scripts/test-guest-x86.py uefi\n', '')
s = s.replace('aether-0.1.1-x86_64.iso', 'aether-0.1.1-x86.iso')
(r/'scripts/refresh-guest-x86.sh').write_text(s)
