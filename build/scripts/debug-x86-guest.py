from pathlib import Path
r=Path('/opt/aether')
s=(r/'scripts/test-guest-x86.py').read_text()
s=s.replace("f'boot-guest-x86-{firmware}.log'", "f'boot-debug-x86-{firmware}.log'")
s=s.replace("b'/etc/init.d/S99aether selftest\\n'", "b'/usr/sbin/VBoxService --version; dmesg | tail -12; /etc/init.d/S99aether selftest\\n'")
(r/'scripts/test-debug-x86.py').write_text(s)
