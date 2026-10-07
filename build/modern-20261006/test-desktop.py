#!/usr/bin/env python3
"""Disposable live-VM checks for first run, local AI and session notifications."""
import json,shlex,socket,time,sys
from pathlib import Path
import pexpect
b=Path('/opt/aether/build/modern-20261006');run=b/('desktop-test-'+time.strftime('%Y%m%dT%H%M%S'));run.mkdir();monitor=run/'qmp.sock'
args=['-machine','q35','-accel','tcg,thread=multi','-cpu','qemu64','-smp','4','-m','4096','-display','none','-vga','none','-device','virtio-vga','-monitor','none','-qmp','unix:'+str(monitor)+',server=on,wait=off','-serial','stdio','-no-reboot','-nic','none']
if '--disk' in sys.argv:args+=['-drive','file='+str(b/'aether-0.3.2-dev-20261006-x86_64.vmdk')+',format=vmdk,if=virtio,snapshot=on']
else:args+=['-drive','file='+str(b/'aether-0.3.2-dev-20261006-x86_64.iso')+',media=cdrom,readonly=on','-boot','d']
log=(run/'console.log').open('w',buffering=1);p=pexpect.spawn('qemu-system-x86_64',args,encoding='utf-8',codec_errors='replace',timeout=900);p.logfile_read=log;results=[]
def check(name,code,timeout=180):
 command='python3 -c '+shlex.quote('exec(bytes.fromhex('+repr(code.encode().hex())+'))')
 p.sendline(command+"; r=$?; printf '\\nDESKTOP_RESULT_%s_END\\n' \"$r\"")
 p.expect(r'DESKTOP_RESULT_([0-9]+)_END\r*\n',timeout);rc=int(p.match.group(1));results.append({'check':name,'exit_code':rc});(run/'checks.json').write_text(json.dumps(results,indent=2))
 if rc:raise RuntimeError(name+' failed')
 p.expect('AE# ',30);print('PASS',name,flush=True)
try:
 p.expect('aether login:');p.sendline('aether');p.expect('Password:');p.sendline('aether2026');p.expect(r'[$] ')
 p.sendline('sudo -i');i=p.expect([r'\[sudo\] password for aether:',r'# '],90)
 if i==0:p.sendline('aether2026');p.expect(r'# ',90)
 p.sendline("export PS1='AE# '");p.expect('AE# ')
 check('local AI answers', '''import json,subprocess,time
def call(value):
 p=subprocess.run(['sudo','-H','-u','aether','--','nimbrel-client'],input=json.dumps(value),text=True,capture_output=True,timeout=300)
 assert p.returncode==0,p.stderr+p.stdout
 return json.loads(p.stdout)
for attempt in range(60):
 status=call({'action':'status'})
 if status.get('ready'):break
 time.sleep(3)
else:
 subprocess.run(['systemctl','status','nimbrel-engine','nimbrel-local','--no-pager','-l'])
 subprocess.run(['journalctl','-u','nimbrel-engine','-n','50','--no-pager'])
 raise RuntimeError('Local model did not become ready')
answer=call({'action':'ask','task':'chat','prompt':'Say hello in one short sentence.','history':[]})
assert answer.get('ok') and isinstance(answer.get('answer'),str) and answer['answer'].strip(),answer
assert subprocess.check_output(['systemctl','show','nimbrel-engine','-p','NRestarts','--value'],text=True).strip()=='0','Engine restarted unexpectedly'
print('Local inference returned a nonempty answer; no external server used.')
''',600)
 check('idle unload and socket remains available', '''from pathlib import Path
import subprocess,time,json
subprocess.run(['systemctl','stop','nimbrel-local.service'],check=True)
p=Path('/opt/nimbrel/local_server.py');text=p.read_text();assert '>600' in text
p.write_text(text.replace('>600','>15').replace('time.sleep(30)','time.sleep(1)'))
subprocess.run(['nimbrel-client'],input='{"action":"status"}',text=True,check=True)
time.sleep(25)
for unit in ('nimbrel-local.service','nimbrel-engine.service'):
 assert subprocess.run(['systemctl','is-active','--quiet',unit]).returncode!=0,unit
assert subprocess.run(['systemctl','is-active','--quiet','nimbrel-local.socket']).returncode==0
p.write_text(text)
print('Idle path tested with a shortened timer in the disposable VM; production default is 600 seconds.')
''',120)
 check('first-run session and update notification', '''from pathlib import Path
import configparser,json,subprocess,time
# Autologin exists only in this throwaway live overlay, never in the image.
p=Path('/etc/lightdm/lightdm.conf');c=configparser.ConfigParser(interpolation=None,strict=False);c.read(p)
if not c.has_section('Seat:*'):c.add_section('Seat:*')
c['Seat:*']['autologin-user']='aether';c['Seat:*']['autologin-user-timeout']='0'
with p.open('w') as f:c.write(f)
Path('/etc/pam.d/lightdm-autologin').write_text('auth required pam_permit.so\\naccount required pam_unix.so\\nsession required pam_unix.so\\nsession optional pam_systemd.so\\n')
Path('/var/lib/aether-updates-status.json').write_text(json.dumps({'state':'updates-available','packages':[],'test_fixture':True}))
subprocess.run(['systemctl','restart','lightdm'],check=True)
for attempt in range(90):
 if subprocess.run(['pgrep','-u','1000','-x','aether-settings'],capture_output=True).returncode==0 and Path('/home/aether/.cache/aether-update-notification').exists():break
 time.sleep(2)
else:raise RuntimeError('First-run window or session notification did not start')
time.sleep(15)
''',300)
 with socket.socket(socket.AF_UNIX) as s:
  s.connect(str(monitor));f=s.makefile('rwb',buffering=0);json.loads(f.readline())
  for request in [{'execute':'qmp_capabilities'},{'execute':'screendump','arguments':{'filename':str(run/'desktop.png'),'format':'png'}}]:
   f.write((json.dumps(request)+'\n').encode())
   while True:
    response=json.loads(f.readline())
    if 'error' in response:raise RuntimeError(response)
    if 'return' in response:break
 (run/'PASS').write_text('First-run UI, session notification, local inference and shortened idle timer passed.\n');print('DESKTOP_PASS',run,flush=True)
except Exception as e:(run/'FAIL').write_text(str(e));raise
finally:p.terminate(force=True);log.close()
