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
x11 = 'x11' in sys.argv[2:]
label = mode + ('-iso' if live else '') + ('-x11' if x11 else '')
base = Path('/opt/aether/build/aether-0.3-system.raw')
if not live:
    assert not subprocess.check_output(['losetup', '-j', str(base)], text=True).strip(), 'Image is mounted'
work = Path('/opt/aether/build') / ('desktop-test-' + label + '-' + time.strftime('%Y%m%d-%H%M%S'))
work.mkdir(mode=0o700)
Path('/opt/aether/logs/desktop/current-test-' + label).write_text(str(work) + '\n')
disk = work / 'disk.qcow2'
if live:
    iso = Path('/opt/aether/images/aether-0.3-x86_64-desktop.iso')
    assert iso.is_file()
    drive = ['-drive', 'file=' + str(iso) + ',media=cdrom,readonly=on', '-boot', 'd']
else:
    subprocess.run(['qemu-img', 'create', '-f', 'qcow2', '-F', 'raw', '-b', str(base), str(disk)], check=True)
    drive = ['-drive', 'file=' + str(disk) + ',format=qcow2,if=virtio']
password = re.search(r'^Temporary password: (.+)$', Path('/opt/aether/build/persistent-credentials.txt').read_text(), re.M)[1]
newpassword = 'Aether9' + secrets.token_hex(16)
firmware = []
if mode == 'uefi':
    shutil.copyfile('/usr/share/OVMF/OVMF_VARS_4M.fd', work / 'OVMF_VARS.fd')
    firmware = ['-drive', 'if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd',
                '-drive', 'if=pflash,format=raw,file=' + str(work / 'OVMF_VARS.fd')]
qmp = work / 'qmp.sock'
args = ['-machine', 'q35', '-accel', 'tcg,thread=multi', '-cpu', 'qemu64', '-smp', '6', '-m', '6144',
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
    qmp_command('send-key', {'keys': [{'type': 'qcode', 'data': name} for name in names]})
    time.sleep(0.2)

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
    time.sleep(12)
    screenshot(name)
    gate = work / ('continue-' + name)
    phase('INSPECT ' + name + ': create ' + str(gate) + ' after visual verification')
    while not gate.exists():
        if not p.isalive():
            raise RuntimeError('VM exited before GUI verification')
        time.sleep(1)

try:
    for boot in ((1,) if live else (1, 2)):
        phase('BOOT ' + str(boot))
        bootargs = args.copy()
        audiofile = work / ('audio-' + str(boot) + '.wav')
        bootargs[bootargs.index('-audiodev') + 1] = 'wav,id=sound,path=' + str(audiofile)
        p = pexpect.spawn('qemu-system-x86_64', bootargs, encoding='utf-8', codec_errors='replace', timeout=240)
        p.logfile_read = log
        expect('aether login:', 420)
        # Exercise the actual greeter before any console login can change expiry.
        if boot == 1:
            inspect_gate('greeter-first-boot')
            if x11:
                keys('shift', 'tab')
                keys('end')
                keys('tab')
                inspect_gate('x11-session-selected')
            type_password('IntentionallyWrong9' + secrets.token_hex(8))
            keys('ret')
            inspect_gate('wrong-password-rejected')
            type_password(password)
            keys('ret')
            inspect_gate('expired-password-current')
            type_password(password)
            keys('ret')
            inspect_gate('expired-password-new')
            type_password()
            keys('ret')
            inspect_gate('expired-password-repeat')
            type_password()
            keys('ret')
            inspect_gate('first-desktop')
        else:
            time.sleep(30)
            screenshot('greeter-reboot')
            if x11:
                keys('shift', 'tab')
                keys('end')
                keys('tab')
            type_password()
            keys('ret')
        p.sendline('aether')
        expect('Password:')
        p.sendline(newpassword)
        expect(r'aether@aether:.*\$ ')
        p.sendline("bind 'set enable-bracketed-paste off'; export PS1='DESKTOPTEST> '")
        expect("DESKTOPTEST> '")
        expect('DESKTOPTEST> ')
        command('sudo -k')
        p.sendline('sudo -v')
        expect(r'\[sudo\] password for aether:')
        p.sendline(newpassword)
        expect('DESKTOPTEST> ')
        command('sudo -n true && test "$(id -u)" = 1000')
        command('systemctl get-default | grep -x graphical.target')
        command('systemctl is-active lightdm NetworkManager systemd-resolved')
        command('timeout 90 sh -c \'until ip -4 addr show | grep -q "10.0.2.15/"; do sleep 1; done\'')
        command('getent ahostsv4 example.com')
        command('curl --fail --silent --show-error --max-time 45 https://example.com -o /tmp/aether-network-test.html && grep -q "Example Domain" /tmp/aether-network-test.html', 60)
        command('sudo -n passwd -S root | grep " L "')
        if mode == 'uefi':
            command('test -d /sys/firmware/efi && findmnt -rn /sys/firmware/efi/efivars -o FSTYPE | grep -x efivarfs')
        else:
            command('test ! -d /sys/firmware/efi')
        command('timeout 240 sh -c \'until pgrep -u 1000 -x plasmashell >/dev/null; do sleep 2; done\'', 270)
        command('pgrep -u 1000 -x ' + ('kwin_x11' if x11 else 'kwin_wayland'))
        command('loginctl list-sessions --no-legend')
        time.sleep(20)
        screenshot('desktop-' + str(boot))
        user_bus('systemctl --user is-active pipewire wireplumber')
        assert 'alsa_output' in user_bus('wpctl inspect @DEFAULT_AUDIO_SINK@')
        tone = "import math,struct,wave; f=wave.open('/tmp/aether-audio.wav','wb'); f.setparams((1,2,48000,0,'NONE','not compressed')); f.writeframes(b''.join(struct.pack('<h',int(4000*math.sin(2*math.pi*440*i/48000))) for i in range(48000))); f.close()"
        command('python3 -c ' + shlex.quote(tone))
        user_bus('pw-play /tmp/aether-audio.wav')
        command('! ldd /usr/bin/plasmashell /usr/bin/krunner /usr/bin/kwin_wayland /usr/bin/dolphin | grep "not found"')
        if boot == 1:
            command('mkdir -p ~/Documents && printf "AuraSearch local file test\\n" > ~/Documents/AuraSearchTest.txt')
            keys('meta_l', 'spc')
            time.sleep(8)
            screenshot('aurasearch-shortcut')
            user_bus('gdbus call --session --dest org.kde.krunner --object-path /App --method org.kde.krunner.App.query "2+2"')
            time.sleep(12)
            screenshot('aurasearch-calculator')
            user_bus('gdbus call --session --dest org.kde.krunner --object-path /App --method org.kde.krunner.App.query "konsole"')
            time.sleep(8)
            screenshot('aurasearch-application')
            keys('ret')
            command('timeout 90 sh -c \'until pgrep -u 1000 -x konsole >/dev/null; do sleep 1; done\'')
            time.sleep(8)
            screenshot('aurasearch-launched-terminal')
            command('pkill -TERM -u 1000 -x konsole')
            time.sleep(2)
            user_bus('balooctl6 index /home/aether/Documents/AuraSearchTest.txt')
            user_bus('timeout 120 sh -c \'until baloosearch6 AuraSearchTest | grep -q AuraSearchTest.txt; do sleep 2; done\'')
            user_bus('gdbus call --session --dest org.kde.krunner --object-path /App --method org.kde.krunner.App.query "AuraSearchTest"')
            time.sleep(8)
            screenshot('aurasearch-local-file')
            keys('esc')
            user_bus('systemd-run --user --collect --unit=aether-test-dolphin /usr/bin/dolphin /home/aether/Documents')
            command('timeout 60 sh -c \'until pgrep -u 1000 -x dolphin >/dev/null; do sleep 1; done\'')
            time.sleep(12)
            screenshot('file-manager')
            user_bus('systemctl --user stop aether-test-dolphin.service')
            for application in ('konsole', 'kate', 'systemsettings', 'kcalc', 'gwenview', 'okular', 'ark'):
                user_bus('systemd-run --user --collect --unit=aether-test-' + application + ' /usr/bin/' + application)
                command('timeout 90 sh -c \'until pgrep -u 1000 -x ' + application + ' >/dev/null; do sleep 1; done\'')
                time.sleep(8)
                screenshot('application-' + application)
                user_bus('systemctl --user stop aether-test-' + application + '.service')
            user_bus('gdbus call --session --dest org.freedesktop.ScreenSaver --object-path /ScreenSaver --method org.freedesktop.ScreenSaver.Lock')
            time.sleep(10)
            assert 'true' in user_bus('gdbus call --session --dest org.freedesktop.ScreenSaver --object-path /ScreenSaver --method org.freedesktop.ScreenSaver.GetActive')
            screenshot('locked')
            keys('ret')
            type_password()
            keys('ret')
            time.sleep(10)
            assert 'false' in user_bus('gdbus call --session --dest org.freedesktop.ScreenSaver --object-path /ScreenSaver --method org.freedesktop.ScreenSaver.GetActive')
            screenshot('unlocked')
            phase('FIRST_BOOT_CHECKS_COMPLETE')
            authenticate_sudo()
            p.sendline('sudo -n systemctl poweroff' if live else 'sudo -n systemctl reboot')
        else:
            command('grep -x "AuraSearch local file test" ~/Documents/AuraSearchTest.txt')
            authenticate_sudo()
            p.sendline('sudo -n systemctl poweroff')
        expect(pexpect.EOF, 180)
        p.close()
        assert p.exitstatus == 0
        with wave.open(str(audiofile), 'rb') as captured:
            assert captured.getsampwidth() == 2
            samples = array.array('h', captured.readframes(captured.getnframes()))
        assert samples and max(map(abs, samples)) > 100, 'No audible samples reached the virtual sound card'
    phase('PASS: ' + label + ' graphical startup, login, Plasma ' + ('X11' if x11 else 'Wayland') + ', core application launches, network, captured virtual audio output, lock/unlock' + ('. Live session is temporary.' if live else ' and reboot persistence.') + ' Screenshots require visual review.')
except Exception:
    phase('FAILED: inspect serial.log and screenshots in ' + str(work))
    if p is not None and p.isalive():
        screenshot('failure')
        p.sendline('sudo -n journalctl -b --no-pager -n 120; systemctl --failed; ps -eo user,pid,comm')
        try:
            expect('DESKTOPTEST> ', 15)
        except Exception:
            pass
    raise
finally:
    if p is not None and p.isalive():
        p.terminate(force=True)
    log.close()
