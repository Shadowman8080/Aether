from pathlib import Path
r = Path('/opt/aether')
s = (r/'scripts/build-vbox-x64.sh').read_text()
s = s.replace('status=$base/logs/vbox-x64.status', '''case "${1:-x86_64}" in
  x86_64) output=prototype; triple=x86_64-aether-linux-gnu; arch=amd64; suffix=x64 ;;
  x86) output=prototype-x86; triple=i686-aether-linux-gnu; arch=x86; suffix=x86 ;;
  arm64) output=prototype-arm64; triple=aarch64-aether-linux-gnu; arch=arm64; suffix=arm64 ;;
  *) exit 2 ;;
esac
exec 9>"$base/build/vbox-source.lock"
flock 9
status=$base/logs/vbox-$suffix.status''')
s = s.replace('tc=$base/build/prototype/host/bin/x86_64-aether-linux-gnu', 'tc=$base/build/$output/host/bin/$triple')
s = s.replace('vbox-x64', 'vbox-$suffix').replace('--target-arch=amd64', '--target-arch="$arch"')
(r/'scripts/build-vbox.sh').write_text(s)
iso = (r/'scripts/build-x86.sh').read_text()
iso = '#!/bin/bash\nset -euo pipefail\ncd /opt/aether\n' + iso[iso.index('stage='):iso.index('python3 scripts/test-boot-x86.py')]
iso = iso.replace('iso-stage-x86','iso-stage-guest-x86').replace('aether-0.1-x86.iso', 'aether-0.1.1-x86.iso')
iso = iso.replace('AETHER_01_X86','AETHER_011_X86').replace('0.1 - x86', '0.1.1 - x86')
iso = iso.replace('rdinit=/init\n', 'rdinit=/init quiet loglevel=3\n')
(r/'scripts/make-guest-x86-iso.sh').write_text(iso)
finish = (r/'scripts/finish-guest-x64.sh').read_text()
finish = finish.replace('guest-x64','guest-x86').replace('for component in vmtools-x64 vbox-x64;', 'for component in vmtools-x86;')
finish = finish.replace('bash scripts/install-vbox.sh x86_64', 'bash scripts/build-vbox.sh x86\nbash scripts/install-vbox.sh x86')
finish = finish.replace('build/prototype', 'build/prototype-x86')
finish = finish.replace('scripts/make-guest-iso.sh', 'scripts/make-guest-x86-iso.sh')
finish = finish.replace('test-guest-x86_64.py', 'test-guest-x86.py')
finish = finish.replace('python3 scripts/test-guest-x86.py uefi\n', '')
finish = finish.replace('aether-0.1.1-x86_64.iso','aether-0.1.1-x86.iso')
(r/'scripts/finish-guest-x86.sh').write_text(finish)
