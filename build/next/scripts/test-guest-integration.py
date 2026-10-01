#!/usr/bin/env python3
from pathlib import Path
import json,re,secrets,shutil,socket,subprocess,sys,time
import pexpect
mode=sys.argv[1]
assert mode in ('uefi','bios')
base=Path('/opt/aether/build/aether-0.2.1-system.raw')
assert not subprocess.check_output(['losetup','-j',str(base)],text=True).strip()
work=Path('/opt/aether/build/guest-integration-test-'+mode)
work.mkdir(exist_ok=True)
disk=work/'disk.qcow2'
assert not disk.exists(), 'Use a fresh test overlay.'
subprocess.run(['qemu-img','create','-f','qcow2','-F','raw','-b',str(base),str(disk)],check=True)
password=re.search(r'^Temporary password: (.+)$',Path('/opt/aether/build/persistent-credentials.txt').read_text(),re.M)[1]
newpassword='Test7!'+secrets.token_hex(12)
firmware=[]
if mode=='uefi':
 shutil.copyfile('/usr/share/OVMF/OVMF_VARS_4M.fd',work/'OVMF_VARS.fd')
 firmware=['-drive','if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd','-drive','if=pflash,format=raw,file='+str(work/'OVMF_VARS.fd')]
qmp=work/'qmp.sock'
args=['-machine','q35','-accel','tcg,thread=multi','-cpu','qemu64','-smp','4','-m','3072','-display','none','-vga','none','-device','virtio-vga','-monitor','none','-serial','stdio','-no-reboot','-qmp','unix:'+str(qmp)+',server=on,wait=off','-drive','file='+str(disk)+',format=qcow2,if=virtio','-nic','user,model=vmxnet3']+firmware
log=open('/opt/aether/logs/next/guest-integration-'+mode+'.log','w',buffering=1)
p=None
def expect(pat,timeout=180): p.expect(pat,timeout=timeout)
def send(s): p.sendline(s)
def command(cmd,timeout=120):
 send(cmd+'; r=$?; printf "\\nAETHER_RC_%s_END\\n" "$r"')
 expect(r'AETHER_RC_([0-9]+)_END\r*\n',timeout)
 result=p.before
 status=p.match.group(1)
 expect('GUESTTEST> ')
 assert status=='0',result
 return result
def authenticate():
 command('sudo -k')
 send('sudo -v'); expect(r'\[sudo\] password for aether:'); send(newpassword); expect('GUESTTEST> ')
 command('sudo -n true')
def qmp_command(name,arguments=None):
 with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as s:
  s.connect(str(qmp)); f=s.makefile('rwb',buffering=0)
  json.loads(f.readline())
  def execute(name,arguments=None):
   f.write((json.dumps({'execute':name,'arguments':arguments or {}})+'\n').encode())
   while True:
    response=json.loads(f.readline())
    if 'error' in response: raise RuntimeError(response)
    if 'return' in response: return response['return']
  execute('qmp_capabilities'); return execute(name,arguments)

def screenshot(path):
 qmp_command('screendump',{'filename':str(path)})
try:
 for boot in (1,2):
  log.write('\n=== '+mode+' boot '+str(boot)+' ===\n')
  p=pexpect.spawn('qemu-system-x86_64',args,encoding='utf-8',codec_errors='replace',timeout=180)
  p.logfile_read=log
  expect('aether login:',240)
  if boot==1: screenshot(Path('/opt/aether/logs/next/guest-console-'+mode+'.ppm'))
  send('aether'); expect('Password:'); send(password if boot==1 else newpassword)
  if boot==1:
   expect(r'(?i)(current|old).*password:'); send(password)
   expect(r'(?i)new password:'); send(newpassword)
   expect(r'(?i)(retype|repeat|re-enter).*password:'); send(newpassword)
  expect(r'aether@aether:.*\$ ')
  send("bind 'set enable-bracketed-paste off'; export PS1='GUESTTEST> '")
  expect("GUESTTEST> '"); expect('GUESTTEST> ')
  authenticate()
  command('test "$(cat /proc/1/comm)" = systemd && test "$(id -u)" = 1000')
  command('systemctl is-active systemd-networkd systemd-resolved systemd-timesyncd')
  command('timeout 45 sh -c \'until ip -4 addr show | grep -q "10.0.2.15/"; do sleep 1; done\'')
  command('getent ahostsv4 example.com')
  command('test -z "$(systemctl --failed --no-legend --plain)"')
  command('VBoxService --version && VBoxControl --version && VBoxClient --version')
  command('test -f /usr/lib/open-vm-tools/plugins/vmusr/libdndcp.so && test -x /usr/bin/VBoxDRMClient && test -x /usr/bin/vmhgfs-fuse && test -x /usr/sbin/mount.vboxsf')
  command('! ldd /usr/bin/vmtoolsd /usr/bin/VBoxClient /usr/bin/aether-guest-panel /usr/lib/open-vm-tools/plugins/vmusr/libdndcp.so | grep "not found"')
  command('aether-efi-status')
  if mode=='uefi':
   command('test -d /sys/firmware/efi && test "$(cat /sys/firmware/efi/fw_platform_size)" = 64 && findmnt -rn --mountpoint /sys/firmware/efi/efivars -o FSTYPE | grep -x efivarfs')
   command('sudo -n efibootmgr -v')
   if boot==1:
    command("sudo -n efibootmgr -c -d /dev/vda -p 2 -L Aether-Test -l '\\EFI\\Aether\\grubx64.efi'")
   else:
    command('sudo -n efibootmgr | grep Aether-Test')
  else: command('test ! -d /sys/firmware/efi')
  if boot==1:
   command("printf '%s\\n' 'guest-persistence-ok' > ~/guest-persistence.txt")
   command('sudo -n systemctl mask --runtime --now getty@tty2.service && sudo -n chvt 2')
   command('sudo -n systemd-run --unit=aether-x-test --collect -p User=aether -p WorkingDirectory=/home/aether -p StandardInput=tty-force -p TTYPath=/dev/tty2 --setenv=HOME=/home/aether /bin/bash -c "exec startx -- :0 vt2 -keeptty > /home/aether/x-session.log 2>&1"')
   command('export DISPLAY=:0 XAUTHORITY=/home/aether/.Xauthority')
   command('timeout 90 sh -c \'until xdpyinfo >/dev/null 2>&1; do systemctl is-active --quiet aether-x-test || exit 1; sleep 1; done\'',120)
   command('xdpyinfo | head -12')
   command('timeout 60 sh -c \'until xprop -name "Aether - Guest integration" WM_CLASS >/dev/null 2>&1; do sleep 1; done\'')
   command('xrandr --current')
   command('xrandr -s 1024x768 && xrandr --current | grep "current 1024 x 768"')
   time.sleep(5)  # Allow the GTK frame and software scanout to finish after RandR.
   screenshot(Path('/opt/aether/logs/next/guest-integration-'+mode+'.ppm'))
   for key in ['tab','tab','tab','tab','ret']:
    qmp_command('send-key',{'keys':[{'type':'qcode','data':key}]})
    time.sleep(0.3)
   command('timeout 30 sh -c \'while test -S /tmp/.X11-unix/X0; do sleep 1; done\'')
   command('unset DISPLAY XAUTHORITY')
   send('sudo -n systemctl reboot')
  else:
   command('grep -x guest-persistence-ok ~/guest-persistence.txt')
   command('test -z "$(systemctl --failed --no-legend --plain)"')
   send('sudo -n systemctl poweroff')
  expect(pexpect.EOF,120); p.close(); assert p.exitstatus==0
 log.write('\nPASS: '+mode+' firmware, EFI variables where applicable, native tools/libraries, graphical session, RandR resize, DHCP/DNS, clean services, persistent settings across reboot. Native host clipboard/shared-folder transfers remain untested.\n')
 print('PASS guest integration '+mode)
except Exception:
 if p is not None and p.isalive():
  p.sendline('cat /home/aether/x-session.log; ps -eo user,pid,ppid,stat,args; sudo -n tail -n 65 /var/log/Xorg.0.log; sudo -n journalctl -b --no-pager -n 30')
  try: p.expect('GUESTTEST> ',timeout=10)
  except Exception: pass
 raise
finally:
 if p is not None and p.isalive(): p.terminate(force=True)
 log.close()
