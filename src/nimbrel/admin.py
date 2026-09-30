#!/usr/bin/env python3
"""Local administrator controls for Nimbrel device enrollment."""
import argparse, hashlib, json, os, secrets, ssl, time
from pathlib import Path
from server import atomic_json, StateLock

p = argparse.ArgumentParser()
p.add_argument("command", choices=["pair", "devices", "revoke"])
p.add_argument("--state", default="/var/lib/nimbrel")
p.add_argument("--device")
args = p.parse_args()
if os.geteuid() != 0:
    p.error("Run as administrator on the AI server.")
state = Path(args.state)
with StateLock(state):
    if args.command == "pair":
        code = str(secrets.randbelow(100000000)).zfill(8)
        pairing = state / "pairing.json"
        atomic_json(pairing, {"hash": hashlib.sha256(code.encode()).hexdigest(), "expires": time.time()+600})
        owner = state.stat()
        os.chown(pairing, owner.st_uid, owner.st_gid)
        certificate = ssl.PEM_cert_to_DER_cert((state/"server.crt").read_text())
        print(json.dumps({"server": "https://192.168.48.135:9443", "fingerprint": hashlib.sha256(certificate).hexdigest(),
            "code": code, "expires_seconds": 600}))
    else:
        path = state / "devices.json"
        devices = json.loads(path.read_text()) if path.exists() else {}
        if args.command == "devices":
            print(json.dumps([{"id": key, **value} for key,value in devices.items()], indent=2))
        else:
            if args.device not in devices: p.error("Device ID was not found.")
            del devices[args.device]
            atomic_json(path, devices)
            owner = state.stat()
            os.chown(path, owner.st_uid, owner.st_gid)
            print("Device revoked.")
