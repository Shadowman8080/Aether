#!/usr/bin/env python3
"""Boot the deliverable ISO, log into its serial console, and test userspace."""
import os, pathlib, selectors, shutil, subprocess, sys, time
base = pathlib.Path('/opt/aether')
firmware = 'uefi'
log_path = base/'logs/boot-network-arm64-uefi.log'
variables = base/'build/test-arm64-uefi-vars.fd'
shutil.copyfile('/usr/share/AAVMF/AAVMF_VARS.fd', variables)
cmd = ['qemu-system-aarch64', '-machine', 'virt', '-accel', 'tcg',
       '-cpu', 'cortex-a53', '-smp', '2', '-m', '1024', '-display', 'none',
       '-serial', 'stdio', '-monitor', 'none', '-no-reboot', '-nic', 'user,model=virtio-net-pci',
       '-drive', 'if=pflash,format=raw,readonly=on,file=/usr/share/AAVMF/AAVMF_CODE.fd',
       '-drive', f'if=pflash,format=raw,file={variables}',
       '-device', 'virtio-scsi-pci,id=scsi0',
       '-drive', f'if=none,id=cd0,format=raw,media=cdrom,readonly=on,file={base}/images/aether-0.1.1-arm64-vm.iso',
       '-device', 'scsi-cd,drive=cd0,bus=scsi0.0,bootindex=1']
proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
sel = selectors.DefaultSelector()
sel.register(proc.stdout, selectors.EVENT_READ)
data = bytearray()
login_sent = False
test_sent = False
deadline = time.monotonic() + 600
try:
    with log_path.open('wb') as log:
        while time.monotonic() < deadline:
            for key, _ in sel.select(1):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if not chunk:
                    sel.unregister(key.fileobj)
                    continue
                data.extend(chunk)
                log.write(chunk)
                log.flush()
            if not login_sent and b'aether login:' in data:
                proc.stdin.write(b'root\n'); proc.stdin.flush()
                login_sent = True
            if login_sent and not test_sent and b'# ' in data[-4096:]:
                proc.stdin.write(b"ip -4 addr show dev eth0; if ping -c 1 -W 3 10.0.2.2; then echo AETHER_NET_PASS; fi; /etc/init.d/S99aether selftest\n"); proc.stdin.flush()
                test_sent = True
            if proc.poll() is not None and not sel.get_map():
                break
        else:
            raise RuntimeError('Boot timed out; see ' + str(log_path))
    expected = ('AETHER_FIRMWARE=' + firmware.upper()).encode()
    assert proc.returncode == 0, f'QEMU exit {proc.returncode}'
    assert login_sent and test_sent, 'Interactive console not reached'
    assert b'10.0.2.15/' in data, 'DHCP lease missing'
    assert b'\r\nAETHER_NET_PASS\r\n' in data, 'Gateway test failed'
    assert b'AETHER_SELFTEST_PASS' in data, 'Self-test did not pass'
    assert b'AETHER_SELFTEST_FAIL' not in data, 'Self-test failed'
    assert expected in data, 'Unexpected firmware boot mode'
    print(f'{firmware.upper()}: PASS - ISO boot, root console, target executable, userspace checks, poweroff')
finally:
    if proc.poll() is None:
        proc.kill(); proc.wait()
