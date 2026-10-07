#!/usr/bin/env python3
"""Boot an immutable candidate with temporary VM writes; no personal disk access."""
import json,shutil,sys,time
from pathlib import Path
import pexpect
kind,firmware=sys.argv[1:3]
b=Path('/opt/aether/build/modern-20261006');run=b/('test-'+kind+'-'+firmware);run.mkdir(exist_ok=True)
image=b/('aether-0.3.2-dev-20261006-x86_64.'+('iso' if kind=='iso' else 'vmdk'))
args=['-machine','q35','-accel','tcg,thread=multi','-cpu','qemu64','-smp','4','-m','4096','-display','none','-vga','none','-device','virtio-vga','-monitor','none','-serial','stdio','-no-reboot','-nic','none']
if firmware=='uefi':
 shutil.copyfile('/usr/share/OVMF/OVMF_VARS_4M.fd',run/'vars.fd')
 args+=['-drive','if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd','-drive','if=pflash,format=raw,file='+str(run/'vars.fd')]
args+=['-drive',('file='+str(image)+',media=cdrom,readonly=on') if kind=='iso' else ('file='+str(image)+',format=vmdk,if=virtio,snapshot=on')]
if kind=='iso':args+=['-boot','d']
log=(run/'console.log').open('w',buffering=1);results=[]
p=pexpect.spawn('qemu-system-x86_64',args,encoding='utf-8',codec_errors='replace',timeout=900);p.logfile_read=log
def check(name,cmd,timeout=180):
 p.sendline(cmd+"; r=$?; printf '\\nMODERN_RESULT_%s_END\\n' \"$r\"")
 p.expect(r'MODERN_RESULT_([0-9]+)_END\r*\n',timeout)
 code=int(p.match.group(1));results.append({'check':name,'exit_code':code})
 if code:raise RuntimeError(name+' failed: '+str(code))
 p.expect(r'[$] ',30)
try:
 p.expect('aether login:');p.sendline('aether');p.expect('Password:');p.sendline('aether2026');p.expect(r'[$] ')
 check('desktop and demand socket','systemctl is-active --quiet lightdm && systemctl is-active --quiet nimbrel-local.socket && ! systemctl is-active --quiet nimbrel-engine')
 check('unconfigured trust is explicit',"aether-update status | grep -q 'not configured'")
 check('automatic check timer', 'systemctl is-active --quiet aether-update-check.timer')
 check('Flatpak sandbox','bwrap --ro-bind / / --unshare-user --unshare-pid --proc /proc /usr/bin/true')
 check('native tools','flatpak --version && rsync --version && test -x /usr/bin/kdeconnect-app && test -x /usr/bin/fwupdmgr && test -x /usr/bin/orca && test -x /usr/bin/aether-settings')
 check('local AI socket activation',"printf '%s' '{\"action\":\"status\"}' | nimbrel-client && systemctl is-active --quiet nimbrel-local && for i in $(seq 1 30); do systemctl is-active --quiet nimbrel-engine && break; sleep 2; done; systemctl is-active --quiet nimbrel-engine",240)
 check('no failed units',"test \"$(systemctl --failed --no-legend --plain | wc -l)\" = 0")
 (run/'PASS').write_text('Boot/login and listed integration checks passed. Physical phone/firmware not tested.\n')
 print('PASS',kind,firmware,flush=True)
except Exception as e:
 (run/'FAIL').write_text(str(e));print('FAIL',kind,firmware,str(e),flush=True);raise
finally:
 (run/'checks.json').write_text(json.dumps(results,indent=2));p.terminate(force=True);log.close()
