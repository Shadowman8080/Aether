#!/usr/bin/env python3
"""Destructive-to-test-resources checks; run ONLY in a disposable test VM."""
from pathlib import Path
import json
import os
import secrets
import socket
import subprocess
import tempfile
import threading
import time

assert os.geteuid() == 0
assert Path('/run/aether-disposable-test').is_file(), 'Must explicitly mark disposable test guest'

def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)

for unit in ('aether-firewall', 'apparmor', 'lightdm', 'NetworkManager', 'aether-zram'):
    run('systemctl', 'is-active', unit)
assert '/dev/zram0' in Path('/proc/swaps').read_text()
assert '/swapfile' not in Path('/proc/swaps').read_text()
assert Path('/proc/sys/kernel/dmesg_restrict').read_text().strip() == '1'
assert Path('/proc/sys/kernel/kptr_restrict').read_text().strip() == '2'
assert Path('/proc/sys/kernel/yama/ptrace_scope').read_text().strip() == '1'
denied = subprocess.run(['dmesg'], capture_output=True, user=1000, group=1000, extra_groups=[])
assert denied.returncode != 0, 'Unprivileged kernel log read succeeded'
for p in ('/tmp/aether-public-probe', '/tmp/aether-private-probe'):
    Path(p).write_text('Disposable boundary-test data\n')
    Path(p).chmod(0o644)
run('/usr/libexec/aether-boundary-probe')
for p in ('/tmp/aether-public-probe', '/tmp/aether-private-probe'):
    Path(p).unlink()

# Real packets across a veth pair exercise both IP families, then deliberate
# allow/revoke. The same route must work after opening the port.
suffix = str(os.getpid())
ns = 'aether-fw-' + suffix
v0, v1 = 'afv' + suffix, 'afc' + suffix
port = 48231
original = Path('/etc/aether-security/firewall.json').read_bytes()
assert json.loads(original) == {'tcp': [], 'udp': []}, 'Expected pristine firewall configuration'
sockets = []
def serve(sock):
    while True:
        try:
            conn, _ = sock.accept()
            conn.sendall(b'AETHER_FIREWALL_TEST')
            conn.close()
        except OSError:
            return
try:
    run('ip', 'netns', 'add', ns)
    run('ip', 'link', 'add', v0, 'type', 'veth', 'peer', 'name', v1)
    run('ip', 'link', 'set', v1, 'netns', ns)
    run('ip', 'addr', 'add', '10.77.0.1/24', 'dev', v0)
    run('ip', '-6', 'addr', 'add', 'fd42:77::1/64', 'dev', v0, 'nodad')
    run('ip', 'link', 'set', v0, 'up')
    run('ip', '-n', ns, 'link', 'set', 'lo', 'up')
    run('ip', '-n', ns, 'addr', 'add', '10.77.0.2/24', 'dev', v1)
    run('ip', '-n', ns, '-6', 'addr', 'add', 'fd42:77::2/64', 'dev', v1, 'nodad')
    run('ip', '-n', ns, 'link', 'set', v1, 'up')
    for family, address in [(socket.AF_INET, '10.77.0.1'), (socket.AF_INET6, 'fd42:77::1')]:
        sock = socket.socket(family, socket.SOCK_STREAM)
        if family == socket.AF_INET6:
            sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        sock.bind((address, port))
        sock.listen(5)
        sockets.append(sock)
        threading.Thread(target=serve, args=(sock,), daemon=True).start()
    client = '''import socket,sys
s=socket.socket(socket.AF_INET6 if ':' in sys.argv[1] else socket.AF_INET,socket.SOCK_STREAM)
s.settimeout(3)
try:
 s.connect((sys.argv[1],48231)); assert s.recv(64)==b'AETHER_FIREWALL_TEST'
except socket.timeout: sys.exit(10)
'''
    def check(expected):
        for address in ('10.77.0.1', 'fd42:77::1'):
            result = subprocess.run(['ip', 'netns', 'exec', ns, 'python3', '-c', client, address])
            assert result.returncode == expected, (address, result.returncode, expected)
    check(10)
    run('aether-firewall', 'allow-tcp', str(port))
    check(0)
    run('aether-firewall', 'remove-tcp', str(port))
    check(10)
    print('PASS: IPv4/IPv6 incoming blocked, explicit allowance worked, revocation blocked again', flush=True)
finally:
    Path('/etc/aether-security/firewall.json').write_bytes(original)
    run('aether-firewall', 'apply')
    for sock in sockets:
        sock.close()
    subprocess.run(['ip', 'link', 'del', v0], check=False)
    subprocess.run(['ip', 'netns', 'del', ns], check=False)

with tempfile.TemporaryDirectory(prefix='aether-restic-test-', dir='/var/tmp') as directory:
    test = Path(directory)
    os.chmod(test, 0o700)
    source = test / 'data'
    source.mkdir()
    content = secrets.token_bytes(8192)
    (source / 'restore-test.bin').write_bytes(content)
    key = test / 'key'
    key.write_text(secrets.token_urlsafe(32))
    key.chmod(0o600)
    common = ['restic', '--repo', str(test / 'repository'), '--password-file', str(key)]
    run(*common, 'init')
    run(*common, 'backup', '.', cwd=source)
    run(*common, 'check', '--read-data')
    restored = test / 'restored'
    run(*common, 'restore', 'latest', '--target', str(restored), '--verify')
    restored_files = list(restored.rglob('restore-test.bin'))
    assert len(restored_files) == 1 and restored_files[0].read_bytes() == content
    key.write_text(secrets.token_urlsafe(32))
    rejected = subprocess.run([*common, 'snapshots'], capture_output=True)
    assert rejected.returncode != 0, 'Wrong backup passphrase accepted'
    print('PASS: encrypted backup, full repository check, byte-for-byte restore, wrong key rejected', flush=True)

failed = subprocess.check_output(['systemctl', '--failed', '--no-legend', '--no-pager'], text=True).strip()
assert not failed, failed
kernel_log = subprocess.check_output(['journalctl', '-b', '-k', '--no-pager', '-o', 'cat'], text=True)
unexpected = [line for line in kernel_log.splitlines() if 'apparmor="DENIED"' in line
              and 'aether-boundary-probe' not in line]
assert not unexpected, '\n'.join(unexpected)
print('AETHER_RUNTIME_BOUNDARIES_PASS', flush=True)
