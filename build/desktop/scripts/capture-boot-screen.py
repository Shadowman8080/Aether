#!/usr/bin/env python3
"""Capture the display of one disposable Aether QEMU boot test."""
from pathlib import Path
import json
import re
import socket
import sys

work = Path(sys.argv[1]).resolve(strict=True)
assert work.parent == Path('/opt/aether/build')
assert work.name.startswith('desktop-test-')
name = sys.argv[2] if len(sys.argv) > 2 else 'inspection'
assert re.fullmatch(r'[A-Za-z0-9_-]+', name)
output = work / (name + '.ppm')
with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
    sock.connect(str(work / 'qmp.sock'))
    stream = sock.makefile('rwb', buffering=0)
    json.loads(stream.readline())
    for request in [dict(execute='qmp_capabilities'),
                    dict(execute='screendump', arguments=dict(filename=str(output)))]:
        stream.write((json.dumps(request) + '\n').encode())
        while True:
            result = json.loads(stream.readline())
            if 'error' in result:
                raise RuntimeError(result['error'])
            if 'return' in result:
                break
print(output)
