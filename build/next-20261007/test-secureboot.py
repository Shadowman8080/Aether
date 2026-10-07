#!/usr/bin/env python3
"""Disposable-key OVMF probe of the native Aether kernel and systemd EFI stub.

This is not production enrollment or a desktop-image certification.
"""
import hashlib,json,os,re,shutil,stat,subprocess,sys,tempfile,uuid
from pathlib import Path
import pexpect
b=Path('/opt/aether/build/next-20261007');source=Path('/opt/aether/build/modern-20261006/root')
os.umask(0o077);test=Path(tempfile.mkdtemp(prefix='secureboot-fixture-',dir=b))
def run(args,**kwargs):return subprocess.run([str(a) for a in args],check=True,**kwargs)
init=test/'initrd';init.mkdir()
for directory in ('bin','dev','proc','sys','run','etc'):(init/directory).mkdir()
def copy_binary(name,dest):
 target=init/dest.lstrip('/');target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source/name.lstrip('/'),target)
 output=subprocess.check_output(['chroot',str(source),'ldd',name],text=True)
 assert 'not found' not in output
 for path in re.findall(r'(/[^\s()]+)',output):
  canonical=subprocess.check_output(['chroot',str(source),'realpath',path],text=True).strip()
  to=init/path.lstrip('/');to.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source/canonical.lstrip('/'),to)
copy_binary('/usr/lib/aether-initramfs/busybox','/bin/busybox')
copy_binary('/usr/bin/od','/usr/bin/od')
(init/'bin/sh').symlink_to('busybox')
os.mknod(init/'dev/console',stat.S_IFCHR|0o600,os.makedev(5,1))
(init/'init').write_text('''#!/bin/sh
/bin/busybox --install -s /bin
mount -t devtmpfs devtmpfs /dev
mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t securityfs securityfs /sys/kernel/security
mount -t efivarfs efivarfs /sys/firmware/efi/efivars
/usr/bin/od -An -tu1 /sys/firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c
set -- $(/usr/bin/od -An -tu1 /sys/firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c)
shift 4
sb=$1
cat /sys/kernel/security/lockdown
cat /sys/module/module/parameters/sig_enforce
echo "SecureBoot variable: $sb"
if [ "$sb" -eq 1 ] && grep -q '\\[integrity\\]' /sys/kernel/security/lockdown && grep -q Y /sys/module/module/parameters/sig_enforce; then
 echo AETHER_SECUREBOOT_PROBE_PASS
else
 echo AETHER_SECUREBOOT_PROBE_FAIL
fi
poweroff -f
''');(init/'init').chmod(0o755)
with (test/'probe.cpio').open('wb') as output:
 names=['.']+[str(p.relative_to(init)) for p in init.rglob('*')]
 run(['cpio','--null','--quiet','-o','--format=newc','--owner=0:0'],input=('\0'.join(names)+'\0').encode(),stdout=output,cwd=init)
key=test/'test-only.key';cert=test/'test-only.crt'
run(['openssl','req','-new','-x509','-newkey','rsa:2048','-nodes','-subj','/CN=Aether disposable Secure Boot test/','-days','1','-keyout',key,'-out',cert],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
key.chmod(0o600)
env={**os.environ,'PYTHONPATH':str(b/'stage/boot-python/usr/lib/python3.14/site-packages')}
uki=test/'signed.efi'
run([sys.executable,b/'stage/systemd/usr/lib/systemd/ukify','build','--linux',source/'boot/vmlinuz-6.18.54-aether4','--initrd',test/'probe.cpio','--stub',b/'stage/systemd/usr/lib/systemd/boot/efi/linuxx64.efi.stub','--os-release','@'+str(source/'etc/os-release'),'--cmdline','console=ttyS0,115200 lockdown=integrity module.sig_enforce=1 rdinit=/init','--uname','6.18.54-aether4','--secureboot-private-key',key,'--secureboot-certificate',cert,'--sign-kernel','--output',uki],env=env)
run(['sbverify','--cert',cert,uki])
sys.path.insert(0,env['PYTHONPATH']);import pefile
tampered=test/'tampered.efi';data=bytearray(uki.read_bytes());pe=pefile.PE(data=bytes(data))
section=next(s for s in pe.sections if s.Name.rstrip(b'\0')==b'.cmdline');data[section.PointerToRawData]^=1;tampered.write_bytes(data)
assert subprocess.run(['sbverify','--cert',str(cert),str(tampered)],capture_output=True).returncode!=0
guid=str(uuid.uuid4());variables=test/'enrolled.fd'
run(['virt-fw-vars','-i','/usr/share/OVMF/OVMF_VARS_4M.fd','-o',variables,'--set-pk',guid,cert,'--add-kek',guid,cert,'--add-db',guid,cert,'--sb'])
def boot(name,image,expected):
 directory=test/name;directory.mkdir();esp=directory/'esp.img'
 run(['mformat','-C','-i',esp,'-F','-T','262144','::'])
 run(['mmd','-i',esp,'::/EFI','::/EFI/BOOT']);run(['mcopy','-i',esp,image,'::/EFI/BOOT/BOOTX64.EFI'])
 shutil.copy2(variables,directory/'vars.fd')
 args=['-machine','q35,smm=on','-accel','tcg,thread=multi','-cpu','qemu64','-smp','4','-m','2048','-display','none','-monitor','none','-serial','stdio','-no-reboot','-nic','none','-global','driver=cfi.pflash01,property=secure,value=on','-drive','if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.secboot.fd','-drive','if=pflash,format=raw,file='+str(directory/'vars.fd'),'-drive','format=raw,file='+str(esp)]
 with (directory/'console.log').open('w') as log:
  process=pexpect.spawn('qemu-system-x86_64',args,encoding='utf-8',codec_errors='replace',timeout=180);process.logfile_read=log
  try:process.expect(expected)
  finally:process.terminate(force=True)
boot('accepted',uki,'AETHER_SECUREBOOT_PROBE_PASS')
boot('rejected',tampered,r'[Ss]ecurity [Vv]iolation|Access Denied -- rejected probably by Secure Boot')
(test/'result.json').write_text(json.dumps({'signed_kernel_and_stub_boot':True,'secureboot_enabled':True,'lockdown_integrity':True,'module_signature_enforcement':True,'tampered_signature_rejected':True,'tampered_firmware_boot_rejected':True,'production_enrollment':False,'desktop_test':False,'signed_sha256':hashlib.sha256(uki.read_bytes()).hexdigest()},indent=2)+'\n')
print('SECUREBOOT_FIXTURE_PASS')
(b/'secureboot-fixture-latest.txt').write_text(str(test)+'\n')
