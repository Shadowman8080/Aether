from pathlib import Path
import json,os,re,secrets,string,subprocess,shutil,socket,time
import pexpect
from PIL import Image
base=Path('/opt/aether/build')
work=base/('encrypted-install-test-'+time.strftime('%Y%m%d-%H%M%S'));work.mkdir(mode=0o700)
Path('/opt/aether/logs/security/current-encrypted-test').write_text(str(work)+'\n')
def secret():return ''.join(secrets.choice(string.ascii_letters+string.digits) for _ in range(28))
login,storage,recovery=secret(),secret(),secret()
credentials=work/'test-credentials.json';credentials.write_text(json.dumps(dict(login=login,storage=storage,recovery=recovery)));credentials.chmod(0o600)
disk=work/'installed.qcow2';subprocess.run(['qemu-img','create','-f','qcow2',str(disk),'20G'],check=True)
shutil.copyfile('/usr/share/OVMF/OVMF_VARS_4M.fd',work/'OVMF_VARS.fd')
p=None;log=None;qmp=work/'qmp.sock'
def phase(s):print(s,flush=True);(work/'status').write_text(s+'\n')
def launch(live,label):
 global p,log
 args=['-machine','q35','-accel','tcg,thread=multi','-cpu','max','-smp','6','-m','4096','-display','none','-vga','none','-device','virtio-vga','-monitor','none','-serial','stdio','-no-reboot','-qmp','unix:'+str(qmp)+',server=on,wait=off','-nic','user,model=vmxnet3','-drive','if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd','-drive','if=pflash,format=raw,file='+str(work/'OVMF_VARS.fd'),'-drive','file='+str(disk)+',format=qcow2,if=virtio']
 if live:args+=['-drive','file=/opt/aether/images/aether-0.3-x86_64-security.iso,media=cdrom,readonly=on','-boot','d']
 log=(work/(label+'.log')).open('w',buffering=1)
 p=pexpect.spawn('qemu-system-x86_64',args,encoding='utf-8',codec_errors='replace',timeout=300);p.logfile_read=log

def expect(s,t=300):p.expect(s,timeout=t)
def command(s,t=300):
 p.sendline(s+'; r=$?; printf "\\nENC_RC_%s_END\\n" "$r"')
 expect(r'ENC_RC_([0-9]+)_END\r*\n',t)
 assert p.match.group(1)=='0',p.before
 expect('ENCTEST> ')
def console_login(password):
 expect('aether login:',600);p.sendline('aether');expect('Password:');p.sendline(password);expect(r'aether@aether:.*\$ ')
 p.sendline("bind 'set enable-bracketed-paste off'; export PS1='ENCTEST> '")
 expect("ENCTEST> '");expect('ENCTEST> ')
 p.sendline('sudo -k; sudo -v');expect(r'\[sudo\] password for aether:');p.sendline(password);expect('ENCTEST> ')
 command('sudo -n true')
def qmp_call(method,args=None):
 with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as sock:
  sock.connect(str(qmp));f=sock.makefile('rwb',buffering=0);json.loads(f.readline())
  def call(m,a=None):
   f.write((json.dumps(dict(execute=m,arguments=a or {}))+'\n').encode())
   while True:
    v=json.loads(f.readline())
    if 'error' in v:raise RuntimeError(v)
    if 'return' in v:return v['return']
  call('qmp_capabilities');return call(method,args)
def keys(*codes):
 for value in codes:
  qmp_call('input-send-event',{'events':[{'type':'key','data':{'down':True,'key':{'type':'qcode','data':value}}}]});time.sleep(.15)
 for value in reversed(codes):
  qmp_call('input-send-event',{'events':[{'type':'key','data':{'down':False,'key':{'type':'qcode','data':value}}}]});time.sleep(.15)
def unlock(value,label):
 phase('BOOT encrypted installation using '+label)
 launch(False,label)
 time.sleep(60)
 qmp_call('screendump',{'filename':str(work/(label+'-unlock.ppm'))})
 Image.open(work/(label+'-unlock.ppm')).save(work/(label+'-unlock.png'))
 phase('INSPECT_UNLOCK '+str(work/(label+'-unlock.png'))+' ; create '+str(work/('continue-'+label)))
 deadline=time.monotonic()+600
 while not (work/('continue-'+label)).exists():
  if time.monotonic()>deadline:raise RuntimeError('Unlock screen verification timed out')
  time.sleep(1)
 for ch in value:
  keys('shift',ch.lower()) if ch.isupper() else keys(ch)
 keys('ret')
 console_login(login)
 command('test "$(findmnt -n -o SOURCE /)" = /dev/mapper/aether-root')
 command('sudo -n cryptsetup status aether-root')
 command('systemctl is-active lightdm')
 command('sudo -n passwd -S root')
 command('test ! -e /etc/aether-security/backup.key')
 command('sudo -n grep -Fx /mnt/aether-shares/AetherEncryptedBackups /etc/aether-security/backup-destination')
 p.sendline('sudo -n poweroff');expect(pexpect.EOF,180);p.close();log.close();assert p.exitstatus==0
 phase('PASS encrypted boot with '+label)
try:
 phase('BOOT live installer')
 launch(True,'installer')
 console_login('aether2026')
 command('test -s /usr/share/cracklib/pw_dict.pwd')
 command('grep -q aesni /proc/crypto')
 p.sendline('sudo -n aether-install')
 expect('Target disk, such as /dev/sdb.*:');p.sendline('/dev/vda')
 expect(r'Encrypt system storage with LUKS2\? \[Y/n\]:');p.sendline('y')
 expect(r'Personal account name \[aether\]:');p.sendline('aether')
 expect('Backup destination to set up after installation.*:');p.sendline('/mnt/aether-shares/AetherEncryptedBackups')
 expect('To erase this disk, type ERASE /dev/vda:');p.sendline('ERASE /dev/vda')
 expect(r"Type 'yes' in capital letters.*:");p.sendline('YES')
 expect('Enter passphrase for /dev/vda4:');p.sendline(storage)
 expect('Verify passphrase:');p.sendline(storage)
 expect('Enter passphrase for /dev/vda4:',600);p.sendline(storage)
 expect('Enter any existing passphrase.*:',600);p.sendline(storage)
 expect('Enter new passphrase.*:',600);p.sendline(recovery)
 expect('Verify passphrase:');p.sendline(recovery)
 phase('COPY encrypted system and create personal account')
 expect(r'New password:',2400);p.sendline(login)
 outcome=p.expect([r'Retype new password:',r'BAD PASSWORD:'],timeout=90)
 assert outcome==0,'Generated strong password rejected; inspect redacted test log'
 p.sendline(login)
 expect('Installation complete.',900)
 expect('ENCTEST> ')
 p.sendline('sudo -k; sudo -v');expect(r'\[sudo\] password for aether:');p.sendline('aether2026');expect('ENCTEST> ')
 p.sendline('sudo -n poweroff');expect(pexpect.EOF,180);p.close();log.close();assert p.exitstatus==0
 unlock(storage,'primary-passphrase')
 unlock(recovery,'recovery-passphrase')
 phase('PASS: live LUKS2 installation, independent recovery passphrase, two UEFI encrypted boots, account login, backup destination selection and clean shutdown')
finally:
 if p is not None and p.isalive():
  try:qmp_call('quit')
  finally:p.close()
 if log is not None and not log.closed:log.close()
