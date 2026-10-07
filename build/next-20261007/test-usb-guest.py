#!/usr/bin/env python3
"""Exercise USB policy trials against QEMU devices, never host USB hardware."""
import json,shlex,socket,subprocess,time,argparse
from pathlib import Path
import pexpect
parser=argparse.ArgumentParser();parser.add_argument('--output',default='test-usb-guest');options=parser.parse_args()
if not options.output.startswith('test-usb-guest') or '/' in options.output:parser.error('Invalid output directory')
b=Path('/opt/aether/build/next-20261007');out=b/options.output;out.mkdir(exist_ok=False)
subprocess.run(['xorriso','-as','mkisofs','-quiet','-R','-J','-o',str(b/'usb-payload.iso'),str(b/'usb-payload')],check=True)
args=['-machine','q35','-accel','tcg,thread=multi','-cpu','qemu64','-smp','4','-m','4096','-display','none','-vga','none','-device','virtio-vga','-monitor','none','-serial','stdio','-no-reboot','-nic','none','-qmp','unix:'+str(out/'qmp.sock')+',server=on,wait=off','-device','qemu-xhci,id=usbtest','-device','usb-kbd,bus=usbtest.0,id=trustedkbd,serial=AetherTrustedKeyboard','-drive','file='+str(b/'aether-next-20261007-test.iso')+',media=cdrom,readonly=on,index=2','-drive','file='+str(b/'usb-payload.iso')+',media=cdrom,readonly=on,index=3','-boot','d']
log=(out/'console.log').open('w',buffering=1);results=[]
p=pexpect.spawn('qemu-system-x86_64',args,encoding='utf-8',codec_errors='replace',timeout=600);p.logfile_read=log
def check(name,command,timeout=90):
 p.sendline(command+"; r=$?; printf '\\nUSB_RESULT_%s_DONE\\n' \"$r\"")
 p.expect(r'USB_RESULT_([0-9]+)_DONE\r*\n',timeout)
 code=int(p.match.group(1));results.append({'check':name,'exit_code':code})
 if code:raise RuntimeError(name+' failed')
 p.expect('USBTEST# ',30)
def monitor(command,arguments):
 with socket.socket(socket.AF_UNIX) as client:
  client.settimeout(10);client.connect(str(out/'qmp.sock'));stream=client.makefile('rwb');json.loads(stream.readline())
  for request in ({'execute':'qmp_capabilities'},{'execute':command,'arguments':arguments}):
   stream.write((json.dumps(request)+'\n').encode());stream.flush()
   while True:
    result=json.loads(stream.readline())
    if 'error' in result:raise RuntimeError(result)
    if 'return' in result:break
try:
 p.expect('aether login:');p.sendline('aether');p.expect('Password:');p.sendline('aether2026');p.expect(r'[$] ')
 p.sendline('sudo -s');p.expect('password for aether:');p.sendline('aether2026');p.expect(r'[#] ')
 p.sendline("stty -echo; PS1=$(printf 'USB%s# ' TEST)");p.expect('USBTEST# ')
 check('mount test packages','mkdir -p /media/usbtest && mount -o ro /dev/sr1 /media/usbtest')
 install='''import hashlib,json,subprocess
from pathlib import Path
root=Path('/media/usbtest');records=json.loads((root/'packages.json').read_text());archives=[]
for item in records:
 path=root/item['archive'];assert path.name==item['archive'];assert hashlib.file_digest(path.open('rb'),'sha256').hexdigest()==item['sha256'];archives.append(str(path))
subprocess.run(['dpkg','--install',*archives],check=True)
subprocess.run(['ldconfig'],check=True)
subprocess.run(['systemctl','daemon-reload'],check=True)
'''
 check('install verified native packages','python3 -c '+shlex.quote(install),180)
 check('protection initially off','! systemctl is-enabled --quiet usbguard.service && ! systemctl is-active --quiet usbguard.service')
 p.sendline('aether-usbguard setup');p.expect('Type TRIAL');p.sendline('TRIAL');p.expect('Type KEEP within 60 seconds',40)
 time.sleep(70)
 p.sendline('KEEP');p.expect('trial expired and was reverted',30);p.expect('USBTEST# ')
 check('automatic rollback','! systemctl is-active --quiet usbguard.service && ! systemctl is-enabled --quiet usbguard.service && test ! -e /var/lib/aether-usbguard/trial.json')
 p.sendline('aether-usbguard setup');p.expect('Type TRIAL');p.sendline('TRIAL');p.expect('Type KEEP within 60 seconds',40);p.sendline('KEEP');p.expect('USB protection enabled',30);p.expect('USBTEST# ')
 check('trusted keyboard allowed',"usbguard list-devices | grep 'allow .*serial \"AetherTrustedKeyboard\"'")
 monitor('device_add',{'driver':'usb-mouse','bus':'usbtest.0','id':'unknownmouse','serial':'AetherUnknownMouse'})
 check('unknown mouse blocked',"for i in $(seq 1 20); do usbguard list-devices | grep 'block .*serial \"AetherUnknownMouse\"' && break; sleep 1; done; usbguard list-devices | grep 'block .*serial \"AetherUnknownMouse\"'")
 check('explicit device approval',"identity=$(usbguard list-devices | awk '/AetherUnknownMouse/{gsub(\":\",\"\",$1);print $1}'); test -n \"$identity\" && usbguard allow-device \"$identity\" && usbguard list-devices | grep 'allow .*serial \"AetherUnknownMouse\"'")
 p.sendline('aether-usbguard disable');p.expect('Type DISABLE');p.sendline('DISABLE');p.expect('No automatic restart occurs');p.expect('USBTEST# ')
 check('disable waits for manual reboot','! systemctl is-enabled --quiet usbguard.service && systemctl is-active --quiet usbguard.service')
 (out/'PASS').write_text('Virtual USB policy trial, automatic rollback and explicit approval passed. Physical input devices not certified.\n');print('USB_GUEST_PASS',flush=True)
except Exception as error:
 try:
  p.sendline("journalctl -b -u usbguard -u aether-usbguard-recover --no-pager; printf 'USB_EVIDENCE_%s\\n' DONE");p.expect(r'USB_EVIDENCE_DONE\r*\n',30)
 except (pexpect.EOF,pexpect.TIMEOUT):pass
 (out/'FAIL').write_text(str(error));raise
finally:
 (out/'checks.json').write_text(json.dumps(results,indent=2)+'\n');p.terminate(force=True);log.close()
