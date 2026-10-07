#!/usr/bin/env python3
"""Exercise trial/fallback/health commit in a disposable QCOW2, never a user VM."""
import json,re,subprocess,time,sys
from pathlib import Path
import pexpect
b=Path('/opt/aether/build/modern-20261006')
prepared='--prepared' in sys.argv
run=Path((b/'native-recovery-latest').read_text().strip()) if prepared else b/('recovery-test-'+time.strftime('%Y%m%dT%H%M%S'))
assert run.parent==b
run.mkdir(exist_ok=prepared)
disk=run/'test.qcow2';base=b/'aether-0.3.2-dev-20261006-x86_64.vmdk'
if not prepared:subprocess.run(['qemu-img','create','-f','qcow2','-F','vmdk','-b',str(base),str(disk)],check=True)
results=[];p=None;log=None;boot_number=0
def boot():
 global p,log,boot_number
 boot_number+=1;print('RECOVERY_BOOT',boot_number,flush=True)
 log=(run/f'boot-{boot_number}.log').open('w',buffering=1)
 args=['-machine','q35','-accel','tcg,thread=multi','-cpu','qemu64','-smp','4','-m','4096','-display','none','-vga','none','-device','virtio-vga','-monitor','none','-serial','stdio','-no-reboot','-nic','none','-drive','file='+str(disk)+',format=qcow2,if=virtio,discard=unmap']
 p=pexpect.spawn('qemu-system-x86_64',args,encoding='utf-8',codec_errors='replace',timeout=900);p.logfile_read=log
 p.expect('aether login:');p.sendline('aether');p.expect('Password:');p.sendline('aether2026');p.expect(r'[$] ')
 p.sendline('sudo -i');match=p.expect([r'\[sudo\] password for aether:',r'# '],90)
 if match==0:p.sendline('aether2026');p.expect(r'# ',90)
 p.sendline("export PS1='AE# '");p.expect('AE# ')
def check(name,command,timeout=180):
 p.sendline(command+"; r=$?; printf '\\nREC_RESULT_%s_END\\n' \"$r\"")
 p.expect(r'REC_RESULT_([0-9]+)_END\r*\n',timeout);code=int(p.match.group(1))
 results.append({'check':name,'exit_code':code});(run/'checks.json').write_text(json.dumps(results,indent=2))
 if code:raise RuntimeError(name+' failed: '+str(code))
 p.expect('AE# ',30);print('PASS',name,flush=True)
def shutdown():
 global p,log
 p.sendline('systemctl poweroff');p.expect(pexpect.EOF,180);p.close();p=None;log.close();log=None
try:
 if prepared:
  identifier=(run/'slot-id').read_text().strip();assert re.fullmatch(r'[0-9]{8}T[0-9]{6}-[0-9a-f]{8}',identifier)
  path='/var/lib/aether/slots/'+identifier+'/root'
  boot()
  check('trial root and shared home',f"test \"$(cat /etc/aether-slot-id)\" = {identifier} && test \"$(cat /etc/aether-checkpoint-proof)\" = before && test \"$(cat /home/aether/aether-checkpoint-proof)\" = shared && mountpoint -q /run/aether-origin && systemctl is-active --quiet lightdm")
  shutdown();boot()
  check('uncommitted trial falls back',"! grep -q 'aether.slot=' /proc/cmdline && test \"$(cat /etc/aether-checkpoint-proof)\" = after")
  check('restore health commit',f'ln -s ../aether-system-health.service {path}/etc/systemd/system/graphical.target.wants/aether-system-health.service')
  p.sendline('aether-recovery boot '+identifier);p.expect('Type BOOT to select one trial boot:',90);p.sendline('BOOT');p.expect('AE# ')
  shutdown();boot()
  check('health commits successful trial',f"systemctl start aether-system-health.service && test \"$(cat /etc/aether-slot-id)\" = {identifier} && grub-editenv /run/aether-origin/boot/grub/grubenv list | grep -qx saved_entry=aether-slot-{identifier}",240)
  shutdown();(run/'PASS').write_text('Native Aether checkpoint creation on disposable ext4 image; emulated trial boot, shared home, fallback and health commit passed.\n')
  print('RECOVERY_PASS',run,flush=True);sys.exit(0)
 boot()
 if '--faults' in sys.argv:
  p.sendline("printf 'modern-20261006\\n' > /run/aether-disposable-test");p.expect('AE# ',30)
  fixture=Path(__file__).with_name('failed-update-fixture.py').read_text()
  p.sendline("cat > /tmp/failed-update-fixture.py <<'AETHER_FIXTURE_EOF'")
  for line in fixture.splitlines():p.sendline(line)
  p.sendline('AETHER_FIXTURE_EOF');p.expect('AE# ',60)
  check('failed and interrupted installation remain isolated','python3 /tmp/failed-update-fixture.py && test -f /tmp/update-fault-fixture-PASS',1800)
  shutdown();(run/'PASS').write_text('Real failing maintainer script and killed install group remain confined to incomplete candidate. Download/verification boundary mocked; TUF/GPG tested separately.\n')
  print('FAULT_ISOLATION_PASS',run,flush=True);sys.exit(0)
 check('firmware daemon starts','systemctl start fwupd.service && systemctl is-active --quiet fwupd.service',240)
 check('KDE Connect service responds','sudo -H -u aether -- env QT_QPA_PLATFORM=offscreen dbus-run-session -- kdeconnect-cli --list-devices',120)
 check('base identity',"! grep -q 'aether.slot=' /proc/cmdline && printf before > /etc/aether-checkpoint-proof && printf shared > /home/aether/aether-checkpoint-proof")
 p.sendline('aether-recovery create');p.expect('Type CREATE to continue:',90);p.sendline('CREATE');p.expect(r'Checkpoint ready: ([0-9]{8}T[0-9]{6}-[0-9a-f]{8})',1200)
 identifier=p.match.group(1);assert re.fullmatch(r'[0-9]{8}T[0-9]{6}-[0-9a-f]{8}',identifier);p.expect('AE# ')
 (run/'slot-id').write_text(identifier)
 path='/var/lib/aether/slots/'+identifier+'/root'
 check('prepare uncommitted trial',f"rm -- {path}/etc/systemd/system/graphical.target.wants/aether-system-health.service && printf after > /etc/aether-checkpoint-proof")
 p.sendline('aether-recovery boot '+identifier);p.expect('Type BOOT to select one trial boot:',90);p.sendline('BOOT');p.expect('AE# ')
 shutdown();boot()
 check('trial root and shared home',f"test \"$(cat /etc/aether-slot-id)\" = {identifier} && test \"$(cat /etc/aether-checkpoint-proof)\" = before && test \"$(cat /home/aether/aether-checkpoint-proof)\" = shared && mountpoint -q /run/aether-origin && systemctl is-active --quiet lightdm")
 shutdown();boot()
 check('uncommitted trial falls back',"! grep -q 'aether.slot=' /proc/cmdline && test \"$(cat /etc/aether-checkpoint-proof)\" = after")
 check('restore health commit',f'ln -s ../aether-system-health.service {path}/etc/systemd/system/graphical.target.wants/aether-system-health.service')
 p.sendline('aether-recovery boot '+identifier);p.expect('Type BOOT to select one trial boot:',90);p.sendline('BOOT');p.expect('AE# ')
 shutdown();boot()
 check('health commits successful trial',f"systemctl start aether-system-health.service && test \"$(cat /etc/aether-slot-id)\" = {identifier} && grub-editenv /run/aether-origin/boot/grub/grubenv list | grep -qx saved_entry=aether-slot-{identifier}",240)
 shutdown()
 (run/'PASS').write_text('Manual checkpoint, shared home, one-shot fallback and health commit passed.\n')
 print('RECOVERY_PASS',run,flush=True)
except Exception as e:
 (run/'FAIL').write_text(str(e));raise
finally:
 if p is not None:p.terminate(force=True)
 if log is not None:log.close()
