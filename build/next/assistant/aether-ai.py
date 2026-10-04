#!/usr/bin/env python3
"""User-owned, local-only inference session and verified model downloader."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

def emit(kind, **fields):
    print(json.dumps({'type': kind, **fields}), flush=True)

def manifest():
    location = Path(os.environ.get('AETHER_AI_MANIFEST', '/usr/share/aether-assistant/model.json'))
    return json.loads(location.read_text())

def model_directory():
    path = Path(os.environ.get('XDG_DATA_HOME', str(Path.home()/'.local/share')))/'aether-assistant/models'
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path

def model_path(info):
    name = info['filename']
    if Path(name).name != name:
        raise ValueError('Invalid model filename')
    return model_directory()/name

def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()

def download(info):
    dest = model_path(info)
    if dest.exists() and sha256(dest) == info['sha256']:
        emit('downloaded', path=str(dest)); return
    tmp = dest.with_name(dest.name+'.'+secrets.token_hex(8)+'.part')
    try:
        request = urllib.request.Request(info['url'], headers={'User-Agent':'Aether-Assistant/0.2'})
        total = 0
        h = hashlib.sha256()
        with urllib.request.urlopen(request, timeout=60) as response, tmp.open('xb') as out:
            os.chmod(tmp, 0o600)
            while chunk := response.read(1024*1024):
                total += len(chunk)
                if total > info['bytes']:
                    raise ValueError('Model download exceeded its expected size')
                out.write(chunk); h.update(chunk)
                emit('progress', received=total, total=info['bytes'])
        if total != info['bytes'] or h.hexdigest() != info['sha256']:
            raise ValueError('Model checksum verification failed')
        os.replace(tmp, dest)
        emit('downloaded', path=str(dest))
    finally:
        tmp.unlink(missing_ok=True)

class Session:
    def __init__(self, info):
        self.info = info
        self.proc = None
        self.token = secrets.token_urlsafe(32)
        self.history = []
        self.endpoint = ''
        self.private_dir = None

    def close(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try: self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill(); self.proc.wait()
        self.proc = None
        if self.private_dir:
            self.private_dir.cleanup()
            self.private_dir = None

    def request(self, path, payload=None, timeout=120):
        headers = {'Authorization':'Bearer '+self.token}
        data = None
        if payload is not None:
            data = json.dumps(payload).encode()
            headers['Content-Type'] = 'application/json'
        req = urllib.request.Request(self.endpoint+path, data=data, headers=headers)
        # Do not send local chat through environment-configured HTTP proxies.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req, timeout=timeout) as response:
            raw = response.read(2*1024*1024 + 1)
            if len(raw) > 2*1024*1024: raise ValueError('Response too large')
            return json.loads(raw)

    def start(self):
        if self.proc and self.proc.poll() is None: return
        self.close()
        path = model_path(self.info)
        if not path.exists(): raise ValueError('Download the local model first.')
        emit('status', message='Verifying the local model…')
        if sha256(path) != self.info['sha256']:
            emit('model_invalid')
            raise ValueError('The local model failed verification. Download it again.')
        executable = os.environ.get('AETHER_LLAMA_SERVER') or shutil.which('llama-server')
        if not executable: raise ValueError('The local inference engine is not installed.')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
        self.endpoint = f'http://127.0.0.1:{port}'
        self.private_dir = tempfile.TemporaryDirectory(prefix='aether-ai-')
        key_file = Path(self.private_dir.name)/'key'
        key_file.write_text(self.token+'\n')
        key_file.chmod(0o600)
        threads = len(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else (os.cpu_count() or 1)
        self.proc = subprocess.Popen([executable, '--model', str(path), '--host', '127.0.0.1',
            '--port', str(port), '--api-key-file', str(key_file), '--ctx-size', '4096',
            '--threads', str(threads), '--parallel', '1', '--n-gpu-layers', '0',
            '--log-disable'], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        emit('status', message='Loading the local model…')
        for _ in range(180):
            if self.proc.poll() is not None:
                self.close()
                raise RuntimeError('The inference engine could not load the model.')
            try:
                if self.request('/health', timeout=1).get('status') == 'ok': return
            except (OSError, ValueError, urllib.error.URLError): pass
            time.sleep(0.5)
        self.close(); raise TimeoutError('Model loading timed out.')

    def answer(self, text):
        if not isinstance(text, str) or not text.strip() or len(text) > 6000:
            raise ValueError('Enter a message between 1 and 6,000 characters.')
        self.start()
        message = {'role':'user', 'content':text}
        history = list(self.history)
        while history and sum(len(m['content']) for m in history)+len(text) > 8000:
            history = history[2:]
        system = {'role':'system','content':
            'You are Aether Assistant, running locally on Aether Linux. Help with Linux questions, '
            'explanations, and text the user shares. You have no access to the user\'s files or tools '
            'and cannot execute commands. Do not claim to inspect or change the system. '
            'Aether uses KDE Plasma, and dpkg/apt for the packages Aether builds itself. '
            'Do not suggest apt-get install of arbitrary third-party packages; there is no '
            'distribution repository attached. Be concise and candid '
            'when uncertain. Explain any command you suggest, especially destructive commands.'}
        emit('status', message='Thinking on this computer…')
        result = self.request('/v1/chat/completions', {'messages':[system]+history+[message],
            'max_tokens':512, 'temperature':0.4, 'stream':False,
            'chat_template_kwargs':{'enable_thinking':False}}, timeout=300)
        answer = result['choices'][0]['message']['content']
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError('The model returned no answer. Try a shorter question.')
        self.history = history+[message, {'role':'assistant', 'content':answer}]
        emit('answer', text=answer)

def main():
    def interrupted(*_): raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    p = argparse.ArgumentParser()
    p.add_argument('command', choices=['status', 'download', 'session'])
    args = p.parse_args()
    info = manifest()
    if args.command == 'status':
        emit('model', name=info['name'], bytes=info['bytes'], installed=model_path(info).exists(),
             license=info['license']); return
    if args.command == 'download': download(info); return
    session = Session(info)
    def stop(*_):
        session.close(); raise SystemExit(0)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        emit('ready')
        for line in sys.stdin:
            try:
                item = json.loads(line)
                if item.get('action') == 'clear':
                    session.history.clear(); emit('cleared')
                else: session.answer(item.get('text'))
            except Exception as e: emit('error', message=str(e))
    finally: session.close()

if __name__ == '__main__':
    try: main()
    except KeyboardInterrupt: sys.exit(130)
    except Exception as e:
        emit('error', message=str(e)); sys.exit(1)
