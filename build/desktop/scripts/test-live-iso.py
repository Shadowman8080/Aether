#!/usr/bin/env python3
"""Verify the live ISO reaches the Aether desktop without any login.

Live media auto-logs in as the disposable `live` account (see
aether-live-autologin), so the installed-image harness, which expects a
greeter, does not apply. This waits for the initramfs handoff marker, captures
the desktop as PNG, then requests a clean poweroff and requires the live
shutdown marker.
"""
from pathlib import Path
import json, shutil, socket, struct, subprocess, sys, time, zlib

mode = sys.argv[1] if len(sys.argv) > 1 else 'uefi'
if mode not in ('uefi', 'bios'):
    raise SystemExit('usage: test-live-iso.py uefi|bios')
iso = Path('/opt/aether/images/aether-0.3-x86_64-desktop.iso')
if not iso.is_file():
    raise SystemExit('ISO missing: ' + str(iso))
work = Path('/opt/aether/build') / ('live-test-' + mode + '-' + time.strftime('%Y%m%d-%H%M%S'))
work.mkdir(mode=0o700)
Path('/opt/aether/logs/desktop/current-test-live-' + mode).write_text(str(work) + '\n')
qmp = work / 'qmp.sock'
args = ['qemu-system-x86_64', '-machine', 'q35', '-accel', 'tcg,thread=multi', '-cpu', 'qemu64', '-smp', '6', '-m', '6144',
        '-display', 'none', '-vga', 'none', '-device', 'virtio-vga', '-monitor', 'none',
        '-serial', 'stdio', '-no-reboot', '-qmp', 'unix:' + str(qmp) + ',server=on,wait=off',
        '-drive', 'file=' + str(iso) + ',media=cdrom,readonly=on', '-boot', 'd']
if mode == 'uefi':
    shutil.copyfile('/usr/share/OVMF/OVMF_VARS_4M.fd', work / 'OVMF_VARS.fd')
    args += ['-drive', 'if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd',
             '-drive', 'if=pflash,format=raw,file=' + str(work / 'OVMF_VARS.fd')]

def phase(text):
    (work / 'status').write_text(text + '\n')
    print(text, flush=True)

class QMP:
    def __init__(self, path):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(str(path))
        self.stream = self.sock.makefile('rwb', buffering=0)
        json.loads(self.stream.readline())
        self.call('qmp_capabilities')

    def call(self, name, arguments=None):
        self.stream.write((json.dumps({'execute': name, 'arguments': arguments or {}}) + '\n').encode())
        while True:
            result = json.loads(self.stream.readline())
            if 'error' in result:
                raise RuntimeError(result)
            if 'return' in result:
                return result['return']

def ppm_to_png(source, target):
    data = Path(source).read_bytes()
    if data[:2] != b'P6':
        raise RuntimeError('expected binary PPM from screendump')
    header = data.split(maxsplit=4)
    width, height, maxval = int(header[1]), int(header[2]), int(header[3])
    if maxval != 255:
        raise RuntimeError('unexpected maxval ' + str(maxval))
    pixels = header[4]

    def chunk(tag, body):
        return struct.pack('>I', len(body)) + tag + body + struct.pack('>I', zlib.crc32(tag + body) & 0xffffffff)

    raw = b''.join(b'\x00' + pixels[y * width * 3:(y + 1) * width * 3] for y in range(height))
    out = b'\x89PNG\r\n\x1a\n'
    out += chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
    out += chunk(b'IDAT', zlib.compress(raw, 6))
    out += chunk(b'IEND', b'')
    Path(target).write_bytes(out)

log = (work / 'serial.log').open('w', buffering=1)
process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT)
try:
    deadline = time.time() + 480
    while time.time() < deadline:
        if b'AETHER_LIVE_SWITCH_ROOT' in (work / 'serial.log').read_bytes():
            break
        if process.poll() is not None:
            raise RuntimeError('QEMU exited during boot; inspect ' + str(work / 'serial.log'))
        time.sleep(2)
    else:
        raise RuntimeError('live initramfs never signalled the switch_root handoff')

    phase('SWITCH_ROOT_SEEN: waiting for Plasma')
    time.sleep(120)
    q = QMP(qmp)
    q.call('screendump', {'filename': str(work / 'desktop.ppm')})
    ppm_to_png(work / 'desktop.ppm', work / 'desktop.png')
    phase('SCREENSHOT: ' + str(work / 'desktop.png'))
    q.call('system_powerdown')

    deadline = time.time() + 180
    while time.time() < deadline:
        if b'AETHER_LIVE_SHUTDOWN_CLEAN' in (work / 'serial.log').read_bytes():
            phase('PASS: live ISO booted to the desktop and powered off cleanly')
            break
        if process.poll() is not None:
            raise RuntimeError('QEMU exited before the clean shutdown marker')
        time.sleep(2)
    else:
        raise RuntimeError('live shutdown marker not observed; inspect ' + str(work / 'serial.log'))
finally:
    if process.poll() is None:
        process.terminate()
    log.close()
