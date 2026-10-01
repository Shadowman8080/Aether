#!/usr/bin/env python3
"""Boot the deliverable ISO, log into its serial console, and test userspace."""
import os, pathlib, selectors, shutil, subprocess, sys, time
base = pathlib.Path('/opt/aether')
firmware = sys.argv[1] if len(sys.argv) > 1 else 'bios'
assert firmware == 'bios', 'This 32-bit prototype supports BIOS boot only'
log_path = base / 'logs' / f'boot-x86-{firmware}.log'
cmd = ['qemu-system-i386', '-machine', 'pc', '-accel', 'tcg',
       '-cpu', 'pentium3', '-smp', '2', '-m', '512', '-display', 'none',
       '-serial', 'stdio', '-monitor', 'none', '-no-reboot', '-nic', 'none',
       '-boot', 'd', '-cdrom', str(base/'images/aether-0.1-x86.iso')]
if firmware == 'uefi':
    variables = base/'build/test-uefi-vars.fd'
    shutil.copyfile('/usr/share/OVMF/OVMF_VARS_4M.fd', variables)
    cmd += ['-drive', 'if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd',
            '-drive', f'if=pflash,format=raw,file={variables}']
proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
sel = selectors.DefaultSelector()
sel.register(proc.stdout, selectors.EVENT_READ)
data = bytearray()
login_sent = False
test_sent = False
deadline = time.monotonic() + 300
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
                proc.stdin.write(b'/etc/init.d/S99aether selftest\n'); proc.stdin.flush()
                test_sent = True
            if proc.poll() is not None and not sel.get_map():
                break
        else:
            raise RuntimeError('Boot timed out; see ' + str(log_path))
    expected = ('AETHER_FIRMWARE=' + firmware.upper()).encode()
    assert proc.returncode == 0, f'QEMU exit {proc.returncode}'
    assert login_sent and test_sent, 'Interactive console not reached'
    assert b'AETHER_SELFTEST_PASS' in data, 'Self-test did not pass'
    assert b'AETHER_SELFTEST_FAIL' not in data, 'Self-test failed'
    assert expected in data, 'Unexpected firmware boot mode'
    print(f'{firmware.upper()}: PASS - ISO boot, root console, target executable, userspace checks, poweroff')
finally:
    if proc.poll() is None:
        proc.kill(); proc.wait()
