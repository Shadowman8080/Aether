#!/usr/bin/env python3
"""Boot an unmounted source image via isolated qcow2; exercise real login/reboot."""
from pathlib import Path
import os, re, secrets, shutil, subprocess, sys, time
import pexpect

mode = sys.argv[1]
assert mode in ('bios', 'uefi', 'sata')
base = Path('/opt/aether/build/aether-system.raw')
assert not subprocess.check_output(['losetup', '-j', str(base)], text=True).strip(), 'Detach image before booting'
test = Path('/opt/aether/build/persistent-test-' + mode)
test.mkdir(exist_ok=True)
disk = test / 'disk.qcow2'
assert not disk.exists(), 'Test overlay already exists; use a fresh test directory'
subprocess.run(['qemu-img', 'create', '-f', 'qcow2', '-F', 'raw', '-b', str(base), str(disk)], check=True)
creds = Path('/opt/aether/build/persistent-credentials.txt').read_text()
temporary = re.search(r'^Temporary password: (.+)$', creds, re.M)[1]
newpassword = 'Test7!' + secrets.token_hex(12)
marker = secrets.token_hex(16)
firmware = []
if mode == 'uefi':
    varsfile = test / 'OVMF_VARS.fd'
    shutil.copyfile('/usr/share/OVMF/OVMF_VARS_4M.fd', varsfile)
    firmware = ['-drive', 'if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd', '-drive', 'if=pflash,format=raw,file=' + str(varsfile)]
storage = ['-drive', 'file=' + str(disk) + ',format=qcow2,if=virtio,discard=unmap']
if mode == 'bios':
    storage = ['-device', 'pvscsi,id=scsi', '-drive', 'file=' + str(disk) + ',format=qcow2,if=none,id=osdisk,discard=unmap', '-device', 'scsi-hd,drive=osdisk,bus=scsi.0']
elif mode == 'sata':
    storage = ['-drive', 'file=' + str(disk) + ',format=qcow2,if=none,id=osdisk,discard=unmap', '-device', 'ide-hd,drive=osdisk,bus=ide.0']
nic = {'uefi': 'vmxnet3', 'bios': 'virtio-net-pci', 'sata': 'e1000'}[mode]
command = ['qemu-system-x86_64', '-machine', 'q35', '-accel', 'tcg,thread=multi', '-cpu', 'qemu64', '-smp', '4', '-m', '2048', '-display', 'none', '-monitor', 'none', '-serial', 'stdio', '-no-reboot', '-nic', 'user,model=' + nic] + storage + firmware
log = open('/opt/aether/logs/next/persistent-' + mode + '.log', 'w', buffering=1)
p = None

def expect(pattern, timeout=180):
    p.expect(pattern, timeout=timeout)

def send(s):
    p.sendline(s)

def shell():
    # Wait for a real prompt before setting a stable automation prompt.
    expect(r'aether@aether:.*\$ ')
    send("bind 'set enable-bracketed-paste off'; export PS1='AETHERTEST> '")
    expect("AETHERTEST> '")  # command echo
    expect('AETHERTEST> ')   # actual prompt, possibly preceded by terminal escapes

def run(cmd, timeout=120):
    # Marker is split in the command so an echoed command cannot satisfy the check.
    send(cmd + "; r=$?; printf '\\nAETHER_RC_%s_END\\n' \"$r\"")
    expect(r'AETHER_RC_([0-9]+)_END\r*\n', timeout)
    result = p.before
    assert p.match.group(1) == '0', result
    expect('AETHERTEST> ')
    return result

def sudo(cmd):
    run('sudo -k')
    send('sudo -v')
    expect(r'\[sudo\] password for aether:')
    send(newpassword)
    expect('AETHERTEST> ')
    run('sudo -n ' + cmd)

try:
    for boot in ((1, 2, 3) if mode == 'sata' else (1, 2)):
        log.write('\n=== ' + mode + ' boot ' + str(boot) + ' ===\n')
        current_command = command.copy()
        if boot == 3:
            current_command[current_command.index('-nic') + 1] = 'none'
        p = pexpect.spawn(current_command[0], current_command[1:], encoding='utf-8', codec_errors='replace', timeout=180)
        p.logfile_read = log
        expect('aether login:', 240)
        send('aether')
        expect('Password:')
        send(temporary if boot == 1 else newpassword)
        if boot == 1:
            expect(r'(?i)(current|old).*password:')
            send(temporary)
            expect(r'(?i)new password:')
            send(newpassword)
            expect(r'(?i)(retype|repeat|re-enter).*password:')
            send(newpassword)
        shell()
        run('test "$(id -u)" = 1000 && test "$(uname -m)" = x86_64 && test "$(cat /proc/1/comm)" = systemd')
        run('test ! -w / && test ! -w /etc && test ! -w /usr')
        run('systemctl is-active systemd-networkd systemd-resolved systemd-timesyncd')
        if boot != 3:
            run('timeout 45 sh -c \'until ip -4 addr show | grep -q "10.0.2.15/"; do sleep 1; done\'')
            run('getent ahostsv4 example.com')
        else:
            run('ip -br link')
            run('test -z "$(ip -o link show | grep link/ether)" && aether-system-status')
        run('test "$(findmnt -n -o FSTYPE /)" = ext4 && findmnt -rn --mountpoint /boot/efi -o FSTYPE | grep -x vfat')
        run('test "$(swapon --noheadings --show=NAME)" = /swapfile')
        run('test -z "$(systemctl --failed --no-legend --plain)"')
        if boot == 1:
            run("printf '#include <stdio.h>\\nint main(void){puts(\"AETHER_NATIVE_OK\");return 0;}\\n' > ~/native-check.c && cc -O2 ~/native-check.c -o ~/native-check && ~/native-check | grep -x AETHER_NATIVE_OK")
            run("printf '%s\\n' '" + marker + "' > ~/persistence-check.txt")
            sudo("sh -c 'test \"$(id -u)\" = 0 && printf admin-ok > /etc/aether-persistence-check'")
            run('sudo -n test -f /etc/aether-persistence-check')
            run('sudo -n test -f /boot/efi/EFI/BOOT/BOOTX64.EFI')
            run("cat /etc/machine-id > ~/first-machine-id; cat /proc/sys/kernel/random/boot_id > ~/first-boot-id")
            run("sudo -n passwd -S root | grep '^root L '")
        else:
            run("test \"$(cat ~/persistence-check.txt)\" = '" + marker + "'")
            run("test \"$(cat /etc/aether-persistence-check)\" = admin-ok")
            run('cmp /etc/machine-id ~/first-machine-id && test "$(cat /proc/sys/kernel/random/boot_id)" != "$(cat ~/first-boot-id)"')
            sudo('journalctl --list-boots --no-pager')
            run("test \"$(sudo -n journalctl --list-boots --no-pager | grep -Ec '^[[:space:]]*-?[0-9]+[[:space:]]+[0-9a-f]{32}[[:space:]]')\" -ge 2")
        sudo('true')
        send('sudo -n systemctl ' + ('reboot' if boot == 1 else 'poweroff'))
        expect(pexpect.EOF, 120)
        p.close()
        assert p.exitstatus == 0, (p.exitstatus, p.signalstatus)
    log.write('\nPASS: ' + mode + ' login/password change, sudo, locked root, DHCP/DNS, swap, clean services, bootloader, persistent home/settings/identity/journal across reboot.\n')
    print('PASS persistent ' + mode)
finally:
    if p is not None and p.isalive():
        p.terminate(force=True)
    log.close()
