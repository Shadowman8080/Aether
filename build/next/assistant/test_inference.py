#!/usr/bin/env python3
"""Integration test: invoke in a network namespace with only loopback enabled."""
import importlib.util
import json
import os
import socket
from pathlib import Path
import urllib.error
import urllib.request

spec = importlib.util.spec_from_file_location('aether_ai', Path(__file__).with_name('aether-ai.py'))
ai = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ai)

assert {name for _, name in socket.if_nameindex()} == {'lo'}, 'Run in an isolated network namespace'
info = ai.manifest()
session = ai.Session(info)
try:
    # A bogus proxy must not intercept local chat requests.
    os.environ['http_proxy'] = os.environ['HTTP_PROXY'] = 'http://127.0.0.1:1'
    os.environ['no_proxy'] = os.environ['NO_PROXY'] = ''
    session.start()
    private_dir = Path(session.private_dir.name)
    process = session.proc
    request = urllib.request.Request(session.endpoint+'/v1/chat/completions',
        data=json.dumps({'messages':[{'role':'user','content':'Hello'}]}).encode(),
        headers={'Content-Type':'application/json'})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        opener.open(request, timeout=5)
        raise AssertionError('Unauthenticated inference was accepted')
    except urllib.error.HTTPError as error:
        assert error.code in (401, 403), error.code
    session.answer('In one sentence, what is a Linux kernel?')
    assert session.history[-1]['role'] == 'assistant'
    assert session.history[-1]['content'].strip()
finally:
    session.close()
assert process.poll() is not None, 'Backend leaked after session close'
assert not private_dir.exists(), 'Authentication file leaked after session close'
print('PASS: offline inference, proxy bypass, authentication, process and key cleanup')
