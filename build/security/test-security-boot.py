#!/usr/bin/env python3
"""Exercise an offline desktop image through firmware, LightDM, and a user session.

Uses disposable overlays. Passwords are read privately and never printed.
The first run pauses at the greeter for visual inspection; create `continue-gui`
in the reported test directory to continue the keyboard-driven login test.
"""
from pathlib import Path
import json
import re
import secrets
import shlex
import shutil
import socket
import subprocess
import sys
import time
import wave
import array
import pexpect

mode = sys.argv[1]
assert mode in ('uefi', 'bios')
live = 'iso' in sys.argv[2:]
user_image = 'user-image' in sys.argv[2:]
assert not (live and user_image)
quick = 'quick' in sys.argv[2:]
x11 = 'x11' in sys.argv[2:]
unattended = 'unattended' in sys.argv[2:]
smoke = 'smoke' in sys.argv[2:]
session_only = 'session-only' in sys.argv[2:]
assert not smoke or live, 'Smoke mode is only for read-only ISO boot'
label = mode + ('-iso' if live else '') + ('-x11' if x11 else '') + ('-smoke' if smoke else '') + ('-session' if session_only else '')
label += '-user' if user_image else ''
base = Path('/opt/aether/build/aether-login-failure.vmdk' if user_image else '/opt/aether/build/aether-security.qcow2')
if not live:
    assert not subprocess.check_output(['losetup', '-j', str(base)], text=True).strip(), 'Image is mounted'
work = Path('/opt/aether/build') / ('security-test-' + label + '-' + time.strftime('%Y%m%d-%H%M%S'))
work.mkdir(mode=0o700)
Path('/opt/aether/logs/desktop/current-test-' + label).write_text(str(work) + '\n')
disk = work / 'disk.qcow2'
if live:
    iso = Path('/opt/aether/images/aether-0.3-x86_64-security.iso' if 'release-iso' in sys.argv else '/opt/aether/images/aether-0.3-x86_64-security-preview.iso')
    assert iso.is_file()
    drive = ['-drive', 'file=' + str(iso) + ',media=cdrom,readonly=on', '-boot', 'd']
else:
    subprocess.run(['qemu-img', 'create', '-f', 'qcow2', '-F', 'vmdk' if user_image else 'qcow2', '-b', str(base), str(disk)], check=True)
    drive = ['-drive', 'file=' + str(disk) + ',format=qcow2,if=virtio']
password = re.search(r'^Password: (.+)$', Path('/opt/aether/build/Aether-VMware-repaired-login.txt').read_text(), re.M)[1]
newpassword = password
firmware = []
if mode == 'uefi':
    shutil.copyfile('/usr/share/OVMF/OVMF_VARS_4M.fd', work / 'OVMF_VARS.fd')
    firmware = ['-drive', 'if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd',
                '-drive', 'if=pflash,format=raw,file=' + str(work / 'OVMF_VARS.fd')]
qmp = work / 'qmp.sock'
args = ['-machine', 'q35', '-accel', 'tcg,thread=multi', '-cpu', 'qemu64', '-smp', '6', '-m', '4096' if quick else '6144',
        '-display', 'none', '-vga', 'none', '-device', 'virtio-vga', '-monitor', 'none',
        '-serial', 'stdio', '-no-reboot', '-qmp', 'unix:' + str(qmp) + ',server=on,wait=off',
        '-nic', 'user,model=vmxnet3',
        '-audiodev', 'none,id=sound', '-device', 'intel-hda', '-device', 'hda-duplex,audiodev=sound'] + firmware + drive
log = (work / 'serial.log').open('w', buffering=1)
p = None

def phase(message):
    (work / 'status').write_text(message + '\n')
    print(message, flush=True)

def expect(pattern, timeout=240):
    p.expect(pattern, timeout=timeout)

def command(text, timeout=180):
    p.sendline(text + '; r=$?; printf "\\nAETHER_RC_%s_END\\n" "$r"')
    expect(r'AETHER_RC_([0-9]+)_END\r*\n', timeout)
    output, status = p.before, p.match.group(1)
    expect('DESKTOPTEST> ')
    assert status == '0', output
    return output

def authenticate_sudo():
    p.sendline('sudo -k; sudo -v')
    expect(r'\[sudo\] password for aether:')
    p.sendline(newpassword)
    expect('DESKTOPTEST> ')
    command('sudo -n true')


def qmp_command(name, arguments=None):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.connect(str(qmp))
        stream = sock.makefile('rwb', buffering=0)
        json.loads(stream.readline())
        def call(method, arguments=None):
            stream.write((json.dumps({'execute': method, 'arguments': arguments or {}}) + '\n').encode())
            while True:
                result = json.loads(stream.readline())
                if 'error' in result:
                    raise RuntimeError(result)
                if 'return' in result:
                    return result['return']
        call('qmp_capabilities')
        return call(name, arguments)

def keys(*names):
    # Send modifiers separately: QEMU send-key chords can lose shifted characters
    # in a busy emulated Wayland session.
    for name in names:
        qmp_command('input-send-event', {'events': [{'type': 'key', 'data': {'down': True, 'key': {'type': 'qcode', 'data': name}}}]})
        time.sleep(0.15)
    for name in reversed(names):
        qmp_command('input-send-event', {'events': [{'type': 'key', 'data': {'down': False, 'key': {'type': 'qcode', 'data': name}}}]})
        time.sleep(0.15)
    time.sleep(0.15)


def type_password(value=None):
    for character in (newpassword if value is None else value):
        if character.isupper():
            keys('shift', character.lower())
        elif character in '!@#$%^&*()':
            keys('shift', '1234567890'['!@#$%^&*()'.index(character)])
        elif character in '-_=+':
            key = 'minus' if character in '-_' else 'equal'
            keys(*(['shift', key] if character in '_+' else [key]))
        else:
            assert character.isascii() and character.isalnum(), 'Unsupported test password character'
            keys(character)

def screenshot(name):
    qmp_command('screendump', {'filename': str(work / (name + '.ppm'))})

def user_bus(text):
    return command('env XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus ' + text)


def inspect_gate(name):
    time.sleep((90 if name == 'first-desktop' else 40 if name == 'greeter-first-boot' else 12) if unattended else 12)
    screenshot(name)
    if unattended:
        phase('CAPTURED ' + name + ': visual review required')
        return
    gate = work / ('continue-' + name)
    phase('INSPECT ' + name + ': create ' + str(gate) + ' after visual verification')
    while not gate.exists():
        if not p.isalive():
            raise RuntimeError('VM exited before GUI verification')
        time.sleep(1)


try:
    phase('BOOT repaired account image in disposable UEFI overlay')
    p = pexpect.spawn('qemu-system-x86_64', args, encoding='utf-8', codec_errors='replace', timeout=240)
    p.logfile_read = log
    expect('aether login:', 420)
    if not quick:
        time.sleep(90)
        screenshot('greeter')
        if x11:
            keys('shift', 'tab')
            keys('end')
            keys('tab')
            screenshot('x11-selected')
        keys('caps_lock')
        time.sleep(1)
        screenshot('caps-lock-warning')
        keys('caps_lock')
        type_password('incorrect' + secrets.token_hex(6))
        keys('ret')
        time.sleep(10)
        screenshot('wrong-password')
        type_password(password)
        keys('tab')
        keys('spc')
        time.sleep(1)
        screenshot('visible-password')
        keys('tab')
        keys('spc')
        keys('ret')
        time.sleep(35)
        screenshot('desktop')
    p.sendline('aether')
    expect('Password:')
    p.sendline(password)
    expect(r'aether@aether:.*\$ ')
    p.sendline("bind 'set enable-bracketed-paste off'; export PS1='DESKTOPTEST> '")
    expect("DESKTOPTEST> '")
    expect('DESKTOPTEST> ')
    authenticate_sudo()
    if not quick:
        command('timeout 120 sh -c ' + shlex.quote('until pgrep -u 1000 -x ' + ('kwin_x11' if x11 else 'kwin_wayland') + ' && pgrep -u 1000 -x plasmashell; do sleep 2; done'), 150)
    command('systemctl is-active lightdm')
    command('test -x /usr/bin/aether-vmware-session && test -x /usr/libexec/aether-guest-display-setup')
    command('test -f /etc/xdg/autostart/vmware-user.desktop && test -u /usr/bin/vmware-user-suid-wrapper')
    command('! ldd /usr/bin/vmtoolsd /usr/lib/open-vm-tools/plugins/vmusr/libdndcp.so /usr/lib/open-vm-tools/plugins/vmusr/libresolutionSet.so | grep "not found"')
    if not quick:
        time.sleep(90)
        if x11:
            command('DISPLAY=:0 XAUTHORITY="$HOME/.Xauthority" xrandr --current')
            command('DISPLAY=:0 XAUTHORITY="$HOME/.Xauthority" xrandr -s 1024x768')
            time.sleep(5)
            command('DISPLAY=:0 XAUTHORITY="$HOME/.Xauthority" xrandr --current | grep "current 1024 x 768"')
            screenshot('resized-desktop')
        screenshot('verified-desktop')
    phase('SECURITY: checking active protections and negative boundaries')
    authenticate_sudo()
    command('sudo -n touch /run/aether-disposable-test')
    command('sudo -n aether-security-status --text')
    command('sudo -n journalctl -b -u apparmor -u aether-firewall -u aether-zram --no-pager')
    command('sudo -n python3 /usr/libexec/aether-security-runtime-tests.py', 300)
    phase('SECURITY: PAM temporary lockout and authenticated recovery')
    authenticate_sudo()
    def pam_attempt(value, wanted):
        p.sendline('stty -echo; printf "AUTH_READY\\n"; sudo -n /usr/libexec/aether-auth-check; r=$?; stty echo; printf "\\nAUTH_RESULT_%s_END\\n" "$r"')
        expect(r'AUTH_READY\r*\n')
        p.sendline(value)
        expect(r'AUTH_RESULT_([0-9]+)_END\r*\n', 30)
        assert p.match.group(1) == str(wanted), p.before
        expect('DESKTOPTEST> ')
    command('sudo -n faillock --user aether --reset')
    for attempt in range(5): pam_attempt('deliberatelyIncorrectProbe', 1)
    pam_attempt(password, 1)
    command('sudo -n faillock --user aether')
    command('sudo -n faillock --user aether --reset')
    pam_attempt(password, 0)
    command('systemctl --failed --no-legend --no-pager')

    if not quick and x11:
        command('env DISPLAY=:0 XAUTHORITY="$HOME/.Xauthority" XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus aether-security-center >/tmp/aether-security-center.log 2>&1 & center_pid=$!; sleep 30; kill -0 "$center_pid"')
        screenshot('security-center')
        if 'inspect-center' in sys.argv:
            phase('INSPECT_CENTER ' + str(work))
            deadline = time.monotonic() + 600
            while not (work / 'continue-center').exists():
                if time.monotonic() > deadline: raise RuntimeError('Security Center inspection timed out')
                time.sleep(1)
    authenticate_sudo()
    p.sendline('sudo -n poweroff')
    expect(pexpect.EOF, 120)
    p.close()
    assert p.exitstatus == 0
    if live:
        output=(work/'serial.log').read_text(errors='replace')
        assert 'AETHER_LIVE_SHUTDOWN_CLEAN' in output, 'Live shutdown did not confirm clean unmount'
        assert 'AETHER_LIVE_SHUTDOWN_ERROR' not in output
        assert 'Failed unmounting' not in output
        assert 'Could not detach loopback' not in output
    phase('PASS: ' + ('console ' if quick else 'desktop ') + 'security boot, IPv4/IPv6 allow/revoke, AppArmor deny, kernel restrictions, encrypted backup/restore, PAM lockout/recovery and clean shutdown')
finally:
    if p is not None and p.isalive():
        qmp_command('quit')
        p.close()
    log.close()
