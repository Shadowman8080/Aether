#!/usr/bin/env python3
"""Read-only artifact boot check using disposable QEMU snapshot writes."""
import hashlib,os,shutil,sys,time
from pathlib import Path
import pexpect
kind,firmware=sys.argv[1:3]
b=Path('/opt/aether/build/release-20261006'); run=b/('test-'+kind+'-'+firmware);run.mkdir(exist_ok=True)
image=b/('aether-0.3.1-dev-20261006-x86_64.'+('iso' if kind=='iso' else 'vmdk'))
args=['-machine','q35','-accel','tcg,thread=multi','-cpu','qemu64','-smp','4','-m','4096','-display','none','-vga','none','-device','virtio-vga','-monitor','none','-serial','stdio','-no-reboot','-nic','none']
if firmware=='uefi':
 shutil.copyfile('/usr/share/OVMF/OVMF_VARS_4M.fd',run/'vars.fd')
 args+=['-drive','if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd','-drive','if=pflash,format=raw,file='+str(run/'vars.fd')]
if kind=='iso':args+=['-drive','file='+str(image)+',media=cdrom,readonly=on','-boot','d']
else:args+=['-drive','file='+str(image)+',format=vmdk,if=virtio,snapshot=on']
log=(run/'console.log').open('w',buffering=1)
p=pexpect.spawn('qemu-system-x86_64',args,encoding='utf-8',codec_errors='replace',timeout=900);p.logfile_read=log
try:
 p.expect('aether login:');p.sendline('aether');p.expect('Password:');p.sendline('aether2026');p.expect(r'[$] ')
 command="test -f /usr/share/sounds/AetherGlass/manifest.json && grep -q CONFIG_MOUSE_PS2_VMMOUSE=y /boot/config-$(uname -r) && test -x /usr/bin/vector && test -x /usr/bin/nimbrel && test -x /usr/bin/apt-get && aether-sounds --status && systemctl is-active lightdm nimbrel-local; r=$?; printf '\\nAE_RESULT_%s_DONE\\n' \"$r\""
 p.sendline(command);p.expect(r'AE_RESULT_([0-9]+)_DONE\r*\n',180)
 if p.match.group(1)!='0':raise RuntimeError('Guest feature check failed')
 p.sendline("systemctl --failed --no-pager; printf '\\nAE_UNITS_DONE\\n'");p.expect(r'AE_UNITS_DONE\r+\n',60)
 (run/'PASS').write_text('Firmware boot, login, kernel, sound lookup, Vector/Nimbrel/apt presence and active desktop/AI service passed.\n')
 print('PASS',kind,firmware,flush=True)
except Exception as e:
 (run/'FAIL').write_text(repr(e));print('FAIL',kind,firmware,repr(e),flush=True);raise
finally:
 p.terminate(force=True);log.close()
