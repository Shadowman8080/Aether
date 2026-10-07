#!/usr/bin/env python3
"""Boot an immutable candidate with temporary VM writes; no personal disk access."""
import json,shutil,sys,time
from pathlib import Path
import pexpect
import argparse,hashlib,shlex
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--image',type=Path,required=True)
parser.add_argument('--firmware',choices=['bios','uefi'],required=True)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--candidate-security',action='store_true',help='Require the next candidate security integrations')
options=parser.parse_args();image=options.image.resolve(strict=True);firmware=options.firmware
if image.suffix not in ('.iso','.vmdk') or ',' in str(image):raise ValueError('Use an ISO or VMDK path without commas')
kind='iso' if image.suffix=='.iso' else 'disk';run=options.output.resolve();run.mkdir(parents=True,exist_ok=False)
with image.open('rb') as stream:image_hash=hashlib.file_digest(stream,'sha256').hexdigest()
(run/'image.json').write_text(json.dumps({'name':image.name,'sha256':image_hash,'firmware':firmware},indent=2))
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
 check('desktop and demand socket','for i in $(seq 1 60); do systemctl is-active --quiet lightdm && systemctl is-active --quiet nimbrel-local.socket && break; sleep 2; done; systemctl is-active lightdm && systemctl is-active nimbrel-local.socket',180)
 check('AI remains idle before use','! systemctl is-active nimbrel-engine')
 check('unconfigured trust is explicit',"aether-update status | grep -q 'not configured'")
 check('automatic check timer', 'systemctl is-active --quiet aether-update-check.timer')
 check('Flatpak sandbox','bwrap --ro-bind / / --unshare-user --unshare-pid --proc /proc /usr/bin/true')
 check('native tools','flatpak --version && rsync --version && test -x /usr/bin/kdeconnect-app && test -x /usr/bin/fwupdmgr && test -x /usr/bin/orca && test -x /usr/bin/aether-settings')
 if options.candidate_security:
  check('systemd security integrations',"/usr/lib/systemd/systemd --version > /tmp/systemd-features && (failed=0; for feature in APPARMOR SECCOMP FIDO2 TPM2 LIBCRYPTSETUP LIBCRYPTSETUP_PLUGINS; do grep -q \"+$feature\" /tmp/systemd-features || failed=1; done; test $failed = 0)")
  check('diagnostic export',"aether-diagnostics --output /tmp/aether-diagnostics-ci.json && test \"$(stat -c %a /tmp/aether-diagnostics-ci.json)\" = 600 && python3 -c 'import json; d=json.load(open(\"/tmp/aether-diagnostics-ci.json\")); assert d[\"schema\"]==1 and \"services\" in d'")
  check('firewall and dispatcher','systemctl is-active --quiet aether-firewall && test -x /etc/NetworkManager/dispatcher.d/90-aether-network-profile && test -L /etc/NetworkManager/dispatcher.d/pre-up.d/90-aether-network-profile && test -L /etc/NetworkManager/dispatcher.d/pre-down.d/90-aether-network-profile')
 check('local AI socket activation',"printf '%s' '{\"action\":\"status\"}' | nimbrel-client && systemctl is-active --quiet nimbrel-local && for i in $(seq 1 30); do systemctl is-active --quiet nimbrel-engine && break; sleep 2; done; systemctl is-active --quiet nimbrel-engine",240)
 if options.candidate_security and firmware=='uefi':
  inference='''import json,subprocess,time
def call(value):
 p=subprocess.run(['nimbrel-client'],input=json.dumps(value),text=True,capture_output=True,check=True,timeout=330)
 result=json.loads(p.stdout);assert result.get('ok'),result
 return result
for _ in range(90):
 if call({'action':'status'}).get('ready'):break
 time.sleep(2)
else:raise RuntimeError('Model did not become ready')
answer=call({'action':'ask','task':'chat','prompt':'Say hello in one short sentence.','history':[]})
assert answer.get('answer','').strip()
print('Local inference returned a nonempty answer')
'''
  check('local inference under rebuilt systemd','python3 -c '+shlex.quote(inference),600)
 check('no failed units',"test \"$(systemctl --failed --no-legend --plain | wc -l)\" = 0")
 (run/'PASS').write_text('Boot/login and listed integration checks passed. Physical phone/firmware not tested.\n')
 print('PASS',kind,firmware,flush=True)
except Exception as e:
 try:
  p.sendline("printf '%s\\n' aether2026 | sudo -S journalctl -b -n 100 --no-pager; systemctl --failed --no-pager; systemctl status lightdm nimbrel-local.socket nimbrel-engine --no-pager; printf 'AETHER_FAILURE_%s\\n' EVIDENCE_DONE")
  p.expect('AETHER_FAILURE_EVIDENCE_DONE\\r*\\n',30)
 except (pexpect.TIMEOUT,pexpect.EOF):pass
 (run/'FAIL').write_text(str(e));print('FAIL',kind,firmware,str(e),flush=True);raise
finally:
 (run/'checks.json').write_text(json.dumps(results,indent=2));p.terminate(force=True);log.close()
