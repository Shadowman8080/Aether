#!/usr/bin/env python3
"""Boot an Aether x86_64 ISO to a login prompt on the serial console.

A bounded smoke test: it proves firmware -> GRUB -> kernel -> initrd ->
rootfs.squashfs -> systemd -> greeter all come up. It is not the full
interactive desktop exercise in build/desktop/scripts/test-desktop-boot.py.

The CPU model is pinned to `qemu64` (the oldest baseline QEMU models), so a
pass is also evidence that the image carries no instructions above the
x86-64 v1 baseline that all modern CPUs implement.

Usage: smoke-boot.py {bios|uefi} [iso-path]
"""
import shutil
import sys

import pexpect

mode = sys.argv[1]
assert mode in ('bios', 'uefi')
iso = sys.argv[2] if len(sys.argv) > 2 else '/opt/aether/images/aether-0.3-x86_64.iso'

firmware = []
if mode == 'uefi':
    shutil.copyfile('/usr/share/OVMF/OVMF_VARS_4M.fd', '/tmp/aether-OVMF_VARS.fd')
    firmware = [
        '-drive', 'if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd',
        '-drive', 'if=pflash,format=raw,file=/tmp/aether-OVMF_VARS.fd',
    ]

args = [
    '-machine', 'q35', '-accel', 'tcg,thread=multi', '-cpu', 'qemu64',
    '-smp', '6', '-m', '6144', '-display', 'none', '-vga', 'none',
    '-device', 'virtio-vga', '-monitor', 'none', '-serial', 'stdio', '-no-reboot',
    '-drive', 'file=' + iso + ',media=cdrom,readonly=on', '-boot', 'd',
] + firmware

print('booting %s ...' % mode, flush=True)
p = pexpect.spawn('qemu-system-x86_64', args, encoding='utf-8',
                  codec_errors='replace', timeout=900)
p.logfile_read = sys.stdout
rc = 1
try:
    p.expect('aether login:', timeout=900)
    print('\nSMOKE[%s]: reached login prompt' % mode, flush=True)
    rc = 0
except Exception as exc:  # noqa: BLE001
    print('\nSMOKE[%s] FAILED: %r' % (mode, exc), flush=True)
finally:
    p.terminate(force=True)
sys.exit(rc)
