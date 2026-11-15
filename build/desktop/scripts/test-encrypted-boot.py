#!/usr/bin/env python3
"""Boot a backend-installed encrypted Aether disk under OVMF Secure Boot.

This is a disposable laboratory fixture.  It does not use or copy private
keys: the firmware DB is populated with the public certificate from the
installed UKI asset.  The credentials file is written by
test-installer-backend.sh with mode 0600 and is never printed.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pexpect


DEFAULT_WORK = Path("/opt/aether/build/installer-test")
DEFAULT_OVMF_CODE = Path("/usr/share/OVMF/OVMF_CODE_4M.secboot.fd")
DEFAULT_OVMF_VARS = Path("/usr/share/OVMF/OVMF_VARS_4M.fd")
EFI_GLOBAL = "8be4df61-93ca-11d2-aa0d-00e098032b8c"


def fail(message):
    print("ENCRYPTED_BOOT_FAIL: " + message, file=sys.stderr)
    raise SystemExit(1)


def make_vars(work, template, asset):
    variables = work / "OVMF_VARS.fd"
    if variables.exists():
        variables.unlink()
    cert = asset.parent / "db.crt"
    if not cert.is_file():
        fail("missing public db certificate beside the asset: " + str(cert))
    command = [
        "virt-fw-vars", "-i", str(template), "-o", str(variables),
        "--set-pk", EFI_GLOBAL, str(cert),
        "--add-kek", EFI_GLOBAL, str(cert),
        "--add-db", EFI_GLOBAL, str(cert),
        "--set-shim-verbose", "--sb",
    ]
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL)
    return variables


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--disk", type=Path, default=DEFAULT_WORK / "disk.raw")
    parser.add_argument("--credentials", type=Path,
                        default=DEFAULT_WORK / "encrypted-credentials.json")
    parser.add_argument("--asset", type=Path,
                        default=Path("build/desktop/assets/usr/share/aether/secureboot/aether-installed.efi"))
    parser.add_argument("--workdir", type=Path, default=DEFAULT_WORK / "boot")
    parser.add_argument("--ovmf-code", type=Path, default=DEFAULT_OVMF_CODE)
    parser.add_argument("--ovmf-vars", type=Path, default=DEFAULT_OVMF_VARS)
    parser.add_argument("--passphrase", choices=("storage", "recovery"),
                        default="storage")
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()

    for path, description in ((args.disk, "installed disk"),
                              (args.credentials, "credentials"),
                              (args.asset, "installed UKI asset"),
                              (args.ovmf_code, "OVMF Secure Boot firmware"),
                              (args.ovmf_vars, "OVMF variable template")):
        if not path.is_file():
            fail("missing " + description + ": " + str(path))
    if os.geteuid() != 0:
        fail("run as root (the fixture creates a disposable OVMF variable store)")
    args.workdir.mkdir(parents=True, exist_ok=True)
    credentials = json.loads(args.credentials.read_text())
    passphrase = credentials.get(args.passphrase)
    if not isinstance(passphrase, str) or not passphrase:
        fail("credentials file has no " + args.passphrase + " passphrase")
    variables = make_vars(args.workdir, args.ovmf_vars, args.asset)
    log = (args.workdir / (args.passphrase + "-console.log")).open("w")
    qemu = [
        "qemu-system-x86_64", "-machine", "q35,smm=on",
        "-accel", "tcg,thread=multi", "-cpu", "qemu64", "-smp", "2",
        "-m", "2048", "-display", "none", "-monitor", "none",
        "-serial", "stdio", "-no-reboot", "-nic", "none",
        "-global", "driver=cfi.pflash01,property=secure,value=on",
        "-drive", "if=pflash,format=raw,readonly=on,file=" + str(args.ovmf_code),
        "-drive", "if=pflash,format=raw,file=" + str(variables),
        "-drive", "format=raw,file=" + str(args.disk) + ",if=virtio",
    ]
    child = pexpect.spawn(qemu[0], qemu[1:], encoding="utf-8",
                          codec_errors="replace", timeout=args.timeout)
    child.logfile_read = log
    try:
        prompt = child.expect([
            r"Enter passphrase for .*",
            r"Unlock Aether encrypted storage",
            r"Verification failed",
            r"AETHER_ERROR",
            r"No unauthenticated",
            pexpect.TIMEOUT,
            pexpect.EOF,
        ])
        if prompt not in (0, 1):
            print(child.before[-6000:], file=sys.stderr)
            fail("no LUKS unlock prompt")
        if prompt == 1:
            child.expect(r"Enter passphrase for .*", timeout=args.timeout)
        child.sendline(passphrase)
        login = child.expect([r"aether login:", r"Kernel panic",
                              r"AETHER_ERROR", pexpect.TIMEOUT, pexpect.EOF])
        if login != 0:
            print(child.before[-6000:], file=sys.stderr)
            fail("installed system did not reach aether login:")
        log.flush()
        transcript = Path(log.name).read_text(errors="replace")
        for marker in ("Verification succeeded", "AETHER_ENCRYPTED_ROOT_MOUNTED",
                       "AETHER_INITRAMFS_SWITCHING_TO_ROOT"):
            if marker not in transcript:
                print(transcript[-6000:], file=sys.stderr)
                fail("missing marker " + marker)
        print("ENCRYPTED_BOOT_PASS passphrase=" + args.passphrase)
        print("console log: " + str(log.name))
    finally:
        if child.isalive():
            child.terminate(force=True)
        child.close()
        log.close()


if __name__ == "__main__":
    main()