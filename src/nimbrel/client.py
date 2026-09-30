#!/usr/bin/env python3
"""Nimbrel desktop transport: pinned TLS, explicit file sharing, no command execution."""
import hashlib, hmac, http.client, json, os, re, shutil, ssl, stat, subprocess, sys
import tempfile, urllib.parse, zipfile, socket
from pathlib import Path
from xml.etree import ElementTree

LIMIT = 12000
def config_path():
    return Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home()/".config")))/"nimbrel"/"connection.json"

def load_remote_config():
    path = config_path()
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(path, flags)
    except FileNotFoundError:
        return {}
    with os.fdopen(fd, "r", encoding="utf-8") as f:
        info = os.fstat(f.fileno())
        if not stat.S_ISREG(info.st_mode) or (hasattr(os, "getuid") and info.st_uid != os.getuid()):
            raise ValueError("Connection settings must belong to this user.")
        if os.name != "nt" and info.st_mode & 0o077:
            raise ValueError("Connection settings must be private (mode 0600).")
        return json.loads(f.read(16384))

def load_config():
    # On-device AI is the default, including for users previously paired to Ubuntu.
    return {"mode":"local", "server":"On this device"}

class LocalConnection(http.client.HTTPConnection):
    def connect(self):
        self.sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect('/run/nimbrel/api.sock')

def save_config(value):
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    fd, name = tempfile.mkstemp(prefix="connection-", dir=path.parent)
    try:
        os.chmod(name, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(value, f); f.flush(); os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name): os.unlink(name)

def endpoint(value):
    if not isinstance(value, str) or any(ord(c)<33 for c in value):
        raise ValueError("Enter the server's HTTPS address.")
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
        raise ValueError("Use an HTTPS server address without a path or embedded credentials.")
    port = parsed.port or 443
    if not 1 <= port <= 65535: raise ValueError("Invalid server port.")
    return parsed.hostname, port

def fingerprint(value):
    value = str(value).replace(":", "").strip().lower()
    if not re.fullmatch("[0-9a-f]{64}", value):
        raise ValueError("Enter the SHA-256 certificate fingerprint shown on your server.")
    return value

def request(config, path, data=None):
    if config.get("mode") == "local":
        connection=LocalConnection('localhost',timeout=300)
        try:
            payload=json.dumps(data).encode() if data is not None else None
            connection.request('POST' if data is not None else 'GET',path,body=payload,headers={'Content-Type':'application/json'})
            response=connection.getresponse();raw=response.read(1024*1024+1)
            if len(raw)>1024*1024:raise ValueError('Local response exceeded the limit.')
            value=json.loads(raw)
            if response.status!=200:raise ValueError(value.get('error','Local AI is unavailable.'))
            return value
        finally:connection.close()
    host, port = endpoint(config.get("server"))
    pin = fingerprint(config.get("fingerprint"))
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    # The administrator-provided exact certificate pin replaces CA/hostname trust.
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    connection = http.client.HTTPSConnection(host, port, timeout=10, context=context)
    try:
        connection.connect()
        connection.sock.settimeout(300)
        actual = hashlib.sha256(connection.sock.getpeercert(binary_form=True)).hexdigest()
        if not hmac.compare_digest(actual, pin):
            raise ValueError("Server certificate changed or fingerprint is incorrect. Verify it with the server owner before pairing again.")
        headers = {"Accept":"application/json"}
        token = config.get("token")
        if token: headers["Authorization"] = "Bearer " + token
        payload = None
        if data is not None:
            headers["Content-Type"] = "application/json"
            payload = json.dumps(data).encode()
        connection.request("POST" if data is not None else "GET", path, body=payload, headers=headers)
        response = connection.getresponse()
        raw = response.read(1024*1024+1)
        if len(raw) > 1024*1024: raise ValueError("Server response is too large.")
        value = json.loads(raw)
        if response.status != 200:
            raise ValueError(value.get("error", "The server rejected the request."))
        return value
    finally:
        connection.close()

def extract(path_string):
    path = Path(path_string).expanduser().resolve(strict=True)
    if not path.is_file() or path.stat().st_size > 10*1024*1024:
        raise ValueError("Choose a regular file smaller than 10 MiB.")
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        exe = shutil.which("pdftotext")
        if not exe: raise ValueError("PDF text extraction is not installed.")
        with tempfile.TemporaryDirectory(prefix="nimbrel-pdf-") as folder:
            target = Path(folder)/"text.txt"
            def limits():
                import resource
                resource.setrlimit(resource.RLIMIT_FSIZE, (4*1024*1024, 4*1024*1024))
                resource.setrlimit(resource.RLIMIT_AS, (512*1024*1024, 512*1024*1024))
                resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
            result = subprocess.run([exe, "-nopgbrk", str(path), str(target)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30,
                preexec_fn=limits if os.name == "posix" else None)
            if result.returncode: raise ValueError("Could not read this PDF. Scanned pages need OCR.")
            with target.open("rb") as f: raw = f.read(65536)
        text = raw.decode("utf-8", errors="replace")
    elif suffix == ".docx":
        with zipfile.ZipFile(path) as z:
            info = z.getinfo("word/document.xml")
            if info.file_size > 4*1024*1024: raise ValueError("This document is too large.")
            raw = z.read(info)
        if b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
            raise ValueError("Unsupported document XML.")
        root = ElementTree.fromstring(raw)
        ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        text = "\n".join("".join(t.text or "" for t in p.iter(ns+"t")) for p in root.iter(ns+"p"))
    else:
        with path.open("rb") as f: raw = f.read(65536)
        if b"\x00" in raw: raise ValueError("Choose a text, PDF, or DOCX document.")
        text = raw.decode("utf-8-sig", errors="strict")
    text = text.strip()
    if not text: raise ValueError("No text was found. Scanned images require an OCR-capable server.")
    return {"text": text[:9000], "source": path.name, "truncated": len(text)>9000 or path.stat().st_size>65536 and suffix not in (".pdf",".docx")}

def diagnostics():
    # Fixed read-only commands only. No arbitrary model-provided arguments or shell.
    sections = []
    for label,args in [
        ("Kernel", ["uname","-srmo"]),
        ("Memory", ["free","-m"]),
        ("Root disk space", ["df","-h","/"]),
        ("Failed system units", ["systemctl","--failed","--no-legend","--no-pager","--plain"]),
    ]:
        try:
            result = subprocess.run(args,capture_output=True,text=True,timeout=10)
            sections.append(label + ":\n" + (result.stdout.strip()[:1800] or "None reported"))
        except (OSError,subprocess.TimeoutExpired):
            sections.append(label + ": unavailable")
    return {"text":"\n\n".join(sections), "source":"System summary", "truncated":False}

def perform(item):
    action = item.get("action")
    if action == "pair":
        config = {"server": item["server"].rstrip("/"), "fingerprint": fingerprint(item["fingerprint"])}
        endpoint(config["server"])
        result = request(config, "/v1/pair", {"code":item["code"],"label":item.get("label","Aether desktop")})
        token = result.get("token")
        if not isinstance(token,str) or not re.fullmatch(r"[A-Za-z0-9_-]{32,128}",token):
            raise ValueError("Invalid pairing response.")
        config["token"] = token
        save_config(config)
        return {"paired":True,"server":config["server"]}
    if action == "status":
        try:
            caps=request(load_config(),'/v1/capabilities')
            return {"paired":True,"local":True,"server":"On this device","ready":caps.get('ready',False),"model":caps.get('model','Local model'),"speech_output":bool(shutil.which('spd-say'))}
        except (OSError,ValueError,http.client.HTTPException):
            return {"paired":False,"local":True,"server":"On this device","ready":False,"model":"Qwen3.5 0.8B","speech_output":bool(shutil.which('spd-say'))}
    if action == "capabilities":
        config = load_config()
        if not config: raise ValueError("Connect to your AI server in Settings first.")
        return request(config,"/v1/capabilities")
    if action == "forget":
        config_path().unlink(missing_ok=True)
        return {"forgotten":True}
    if action == "unpair":
        config = load_config()
        if config: request(config,"/v1/unpair", {})
        config_path().unlink(missing_ok=True)
        return {"removed":True}
    if action == "extract": return extract(item["path"])
    if action == "diagnostics": return diagnostics()
    if action == "ask":
        config = load_config()
        if not config: raise ValueError("Connect to your server first.")
        prompt = item.get("prompt","")
        if not isinstance(prompt,str) or not prompt.strip() or len(prompt)>LIMIT:
            raise ValueError("Enter a message under 12,000 characters, including attachments.")
        history = item.get("history",[])
        if not isinstance(history,list): raise ValueError("Invalid history.")
        history=history[-12:]
        while history and sum(len(v.get("content","")) for v in history)+len(prompt)>LIMIT:
            history=history[2:]
        return request(config,"/v1/answer",{"task":item.get("task","chat"),"prompt":prompt,"history":history})
    raise ValueError("Unknown action.")

def main():
    try:
        raw = sys.stdin.buffer.read(256*1024+1)
        if len(raw)>256*1024: raise ValueError("Request too large.")
        item = json.loads(raw)
        if not isinstance(item,dict): raise ValueError("Invalid request.")
        result=perform(item)
        print(json.dumps({"ok":True,**result}))
    except (ValueError,OSError,KeyError,TypeError,ssl.SSLError,http.client.HTTPException,
            zipfile.BadZipFile,ElementTree.ParseError,subprocess.TimeoutExpired) as error:
        # No payload, token or file contents appear in diagnostics.
        print(json.dumps({"ok":False,"error":str(error)}))
        sys.exit(1)

if __name__ == "__main__": main()
