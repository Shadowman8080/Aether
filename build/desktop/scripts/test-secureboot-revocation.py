#!/usr/bin/env python3
"""Execute signed dbx and SBAT revocation paths in disposable OVMF firmware.

This is a laboratory fixture, not a production enrollment or revocation tool.
It never uses the Aether release keys.  The PK, KEK and db used by firmware are
generated for every run.  The shim and revocations test chain uses the
disposable test CA in secureboot/test-ca, whose certificate is embedded in the
test shim.

The two revocation paths are deliberately different:

* dbx: a disposable db certificate signs a test GRUB image.  The image is first
  accepted, then a dbx ESL containing that certificate is signed by the
  disposable KEK and applied to NVRAM with virt-fw-vars.  The same image is
  rejected by OVMF.  A wrong-key image is also rejected.  virt-fw-vars parses
  the signed update structure, but it is an offline NVRAM builder and does not
  perform firmware signature enforcement; this fixture therefore does not claim
  an update-rejection result for a wrong-key dbx update.

* SBAT: shim will not apply an SbatLevel that revokes the shim that is already
  running.  The fixture therefore boots a test shim advertising shim,5, which
  verifies the signed revocations.efi and applies an SbatLevel revoking shim,4.
  The next boot uses the same test shim rebuilt with shim,4 and must fail its
  SBAT self-check.  A wrong-key revocations.efi is rejected and leaves shim,4
  bootable.

Usage:
    python3 build/desktop/scripts/test-secureboot-revocation.py
    python3 .../test-secureboot-revocation.py --only dbx
    python3 .../test-secureboot-revocation.py --only sbat

The fixture needs Linux, QEMU, OVMF 4 MiB Secure Boot firmware, mtools,
sbsign/sbverify, efitools, virt-fw-vars, objcopy, openssl, make/gcc/ld (to build
the test shim), and pexpect.  Its test CA is expected at
/opt/aether/secureboot/test-ca unless --test-ca is supplied; the shim source is
expected at /opt/aether/secureboot/src/shim unless --shim-source is supplied.
"""
import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import pexpect

DEFAULT_TEST_CA = Path("/opt/aether/secureboot/test-ca")
DEFAULT_SHIM_SOURCE = Path("/opt/aether/secureboot/src/shim")
DEFAULT_GRUB = Path("/opt/aether/secureboot/out/grubx64.efi")
DEFAULT_OVMF_CODE = Path("/usr/share/OVMF/OVMF_CODE_4M.secboot.fd")
DEFAULT_OVMF_VARS = Path("/usr/share/OVMF/OVMF_VARS_4M.fd")
GLOBAL_GUID = "8be4df61-93ca-11d2-aa0d-00e098032b8c"
GRUB_MARKER = r"grub_archelp_open|GNU GRUB|Aether Linux"
DENIED_MARKER = r"Access Denied|Security Violation"


class FixtureError(RuntimeError):
    pass


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SecureBootRevocationFixture:
    def __init__(self, args):
        self.args = args
        self.root = Path(tempfile.mkdtemp(
            prefix="aether-secureboot-revocation-",
            dir=str(args.workdir) if args.workdir else None,
        ))
        os.umask(0o077)
        self.command_log = (self.root / "commands.log").open("w")
        self.result = {
            "fixture": "secureboot-revocation",
            "production_keys_used": False,
            "disposable_firmware_keys": True,
            "tests": {},
            "limitations": [
                "offline dbx update through virt-fw-vars; firmware update-policy enforcement is not tested",
                "fixed disposable test CA embedded in the test shim; not an Aether release key",
                "test shim/GRUB/revocations only; no Aether production image or physical firmware",
            ],
        }

    def close(self):
        self.command_log.close()

    def run(self, argv, check=True):
        argv = [str(value) for value in argv]
        self.command_log.write("$ " + shlex.join(argv) + "\n")
        self.command_log.flush()
        process = subprocess.run(argv, text=True, capture_output=True)
        if process.stdout:
            self.command_log.write(process.stdout)
        if process.stderr:
            self.command_log.write(process.stderr)
        self.command_log.flush()
        if check and process.returncode != 0:
            raise FixtureError(
                "command failed (%d): %s\n%s%s" % (
                    process.returncode,
                    shlex.join(argv),
                    process.stdout,
                    process.stderr,
                )
            )
        return process

    def require(self, path, description):
        path = Path(path)
        if not path.is_file():
            raise FixtureError("missing %s: %s" % (description, path))
        return path

    def require_tools(self, names):
        missing = [name for name in names if shutil.which(name) is None]
        if missing:
            raise FixtureError("missing required tools: " + ", ".join(missing))

    def generate_key(self, name, common_name):
        key = self.root / (name + ".key")
        cert = self.root / (name + ".crt")
        self.run([
            "openssl", "req", "-new", "-x509", "-newkey", "rsa:2048", "-nodes",
            "-subj", "/CN=" + common_name, "-days", "1",
            "-keyout", key, "-out", cert,
        ])
        key.chmod(0o600)
        return key, cert

    def prepare_keys(self):
        self.guid = str(uuid.uuid4())
        self.pk_key, self.pk_cert = self.generate_key(
            "pk", "Aether disposable lab PK")
        self.kek_key, self.kek_cert = self.generate_key(
            "kek", "Aether disposable lab KEK")
        self.db_key, self.db_cert = self.generate_key(
            "db", "Aether disposable lab db")
        self.rogue_key, self.rogue_cert = self.generate_key(
            "rogue", "Aether disposable lab wrong key")
        self.result["owner_guid"] = self.guid
        self.result["certificates"] = {
            "pk": sha256(self.pk_cert),
            "kek": sha256(self.kek_cert),
            "db": sha256(self.db_cert),
            "wrong_key": sha256(self.rogue_cert),
        }

    def make_vars(self, name):
        variables = self.root / (name + ".fd")
        self.run([
            "virt-fw-vars", "-i", self.args.ovmf_vars, "-o", variables,
            "--set-pk", self.guid, self.pk_cert,
            "--add-kek", self.guid, self.kek_cert,
            "--add-db", self.guid, self.db_cert,
            "--set-shim-verbose", "--sb",
        ])
        return variables

    def strip_signature(self, source, destination):
        shutil.copy2(source, destination)
        process = self.run(["sbattach", "--remove", destination], check=False)
        if process.returncode != 0 and "No signature table" not in (
                process.stdout + process.stderr):
            raise FixtureError(
                "could not remove existing signature from %s\n%s%s" % (
                    source, process.stdout, process.stderr))
        return destination

    def sign(self, source, destination, key, cert):
        self.run(["sbsign", "--key", key, "--cert", cert,
                  "--output", destination, source])
        self.run(["sbverify", "--cert", cert, destination])
        return destination

    def sign_copy(self, source, destination, key, cert):
        return self.sign(source, destination, key, cert)

    def build_test_shim(self, test_ca):
        """Build a shim whose embedded vendor certificate is the test CA.

        The checked-in test-ca binaries embed Aether's db certificate, which
        would require the release private key to sign revocations.  Build a
        disposable test shim from the shim source instead.
        """
        source = Path(self.args.shim_source)
        if not source.is_dir():
            raise FixtureError("missing shim source directory: %s" % source)
        testca_cert = self.require(test_ca / "testca.crt", "test CA certificate")
        testca_der = self.root / "testca.der"
        self.run(["openssl", "x509", "-in", testca_cert,
                  "-outform", "DER", "-out", testca_der])
        build = self.root / "shim-build"
        shutil.copytree(source, build, symlinks=True)
        self.run(["make", "-C", build, "clean"], check=False)
        self.run([
            "make", "-C", build, "-j4", "shimx64.efi",
            "VENDOR_CERT_FILE=" + str(testca_der),
            # The host binutils may not provide the efi-app-x86_64 target.
            # pei-x86-64 plus post-process-pe produces the same EFI image.
            "FORMAT=-O pei-x86-64 --subsystem 10",
        ])
        shim = self.require(build / "shimx64.efi", "built test shim")
        vendor = self.root / "shim-vendor-cert.bin"
        self.run(["objcopy", "--dump-section",
                  ".vendor_cert=" + str(vendor), shim])
        if testca_der.read_bytes() not in vendor.read_bytes():
            raise FixtureError(
                "built test shim does not embed the supplied test CA")
        return shim

    def strip_and_sign(self, source, destination, key, cert):
        unsigned = destination.with_name(destination.stem + "-unsigned.efi")
        self.strip_signature(source, unsigned)
        return self.sign(unsigned, destination, key, cert)

    def make_esp(self, name, loader, extra=()):
        image = self.root / (name + ".img")
        self.run(["mformat", "-C", "-i", image, "-F", "-T", "262144", "::"])
        self.run(["mmd", "-i", image, "::/EFI", "::/EFI/BOOT"])
        self.run(["mcopy", "-i", image, loader, "::/EFI/BOOT/BOOTX64.EFI"])
        for source, target in extra:
            self.run(["mcopy", "-i", image, source, target])
        return image

    def boot(self, name, variables, esp, pattern, timeout=None):
        directory = self.root / "boots" / name
        directory.mkdir(parents=True)
        console = directory / "console.log"
        qemu = [
            "qemu-system-x86_64",
            "-machine", "q35,smm=on",
            "-accel", "tcg,thread=multi",
            "-cpu", "qemu64",
            "-smp", "4",
            "-m", "2048",
            "-display", "none",
            "-monitor", "none",
            "-serial", "stdio",
            "-no-reboot",
            "-nic", "none",
            "-global", "driver=cfi.pflash01,property=secure,value=on",
            "-drive", "if=pflash,format=raw,readonly=on,file=" + str(self.args.ovmf_code),
            "-drive", "if=pflash,format=raw,file=" + str(variables),
            "-drive", "format=raw,file=" + str(esp),
        ]
        compiled = re.compile(pattern, re.DOTALL) if isinstance(pattern, str) else pattern
        self.command_log.write("$ " + shlex.join(qemu) + " > " + str(console) + "\n")
        self.command_log.flush()
        child = None
        try:
            with console.open("w") as log:
                child = pexpect.spawn(
                    "qemu-system-x86_64", qemu[1:], encoding="utf-8",
                    codec_errors="replace", timeout=timeout or self.args.timeout)
                child.logfile_read = log
                try:
                    matched = child.expect([compiled, pexpect.EOF, pexpect.TIMEOUT])
                except pexpect.ExceptionPexpect as error:
                    matched = None
                    self._boot_failure(name, console, str(error))
            if matched != 0:
                self._boot_failure(name, console,
                                   "marker not observed: %s" % pattern)
            self.result["tests"].setdefault(name, {})
            self.result["tests"][name]["console"] = str(console)
            self.result["tests"][name]["console_sha256"] = sha256(console)
            return console
        finally:
            if child is not None:
                child.terminate(force=True)
                child.close()

    def _boot_failure(self, name, console, message):
        tail = ""
        if console.is_file():
            tail = console.read_text(errors="replace")[-5000:]
        raise FixtureError(
            "boot %s failed: %s\nconsole: %s\n%s" % (name, message, console, tail))

    def test_dbx(self):
        self.result["tests"]["dbx"] = {}
        grub = self.require(self.args.grub, "test GRUB source")
        dbx_esl = self.root / "dbx.esl"
        dbx_auth = self.root / "dbx.auth"
        self.run(["cert-to-efi-sig-list", "-g", self.guid,
                  self.db_cert, dbx_esl])
        self.run(["sign-efi-sig-list", "-g", self.guid,
                  "-k", self.kek_key, "-c", self.kek_cert,
                  "dbx", dbx_esl, dbx_auth])
        self.require(dbx_auth, "signed dbx update")

        image = self.root / "dbx-test-image.efi"
        wrong_image = self.root / "dbx-wrong-key-image.efi"
        self.strip_and_sign(grub, image, self.db_key, self.db_cert)
        self.strip_and_sign(grub, wrong_image, self.rogue_key, self.rogue_cert)

        baseline = self.make_vars("dbx-baseline")
        revoked = self.root / "dbx-revoked.fd"
        shutil.copy2(baseline, revoked)
        self.run(["virt-fw-vars", "-i", revoked, "-o", revoked,
                  "--add-dbx", dbx_auth])

        signed_esp = self.make_esp("dbx-signed", image)
        wrong_esp = self.make_esp("dbx-wrong-key", wrong_image)

        self.boot("dbx-baseline-accepted", baseline, signed_esp, GRUB_MARKER)
        self.boot("dbx-wrong-key-rejected", baseline, wrong_esp, DENIED_MARKER)
        self.boot("dbx-after-signed-update-rejected", revoked, signed_esp,
                  DENIED_MARKER)
        self.boot("dbx-recovery-accepted", baseline, signed_esp, GRUB_MARKER)

        self.result["tests"]["dbx"] = {
            "signed_update_applied": True,
            "signed_image_baseline_accepted": True,
            "signed_image_after_update_rejected": True,
            "wrong_key_image_rejected": True,
            "baseline_recovery_accepted": True,
            "dbx_esl_sha256": sha256(dbx_esl),
            "dbx_auth_sha256": sha256(dbx_auth),
            "test_image_sha256": sha256(image),
            "wrong_key_image_sha256": sha256(wrong_image),
            "firmware_update_policy_tested": False,
        }

    def test_sbat(self):
        self.result["tests"]["sbat"] = {}
        test_ca = Path(self.args.test_ca)
        if not test_ca.is_dir():
            raise FixtureError("missing disposable test CA directory: %s" % test_ca)
        self.require(self.args.grub, "test GRUB source")
        testca_cert = self.require(test_ca / "testca.crt", "test CA certificate")
        testca_key = self.require(test_ca / "testca.key", "test CA private key")
        if "keys" in test_ca.parts:
            raise FixtureError(
                "refusing test CA under release key directory: %s" % test_ca)
        shim_unsigned = self.build_test_shim(test_ca)

        old_shim = self.root / "shim-old.efi"
        new_shim = self.root / "shim-new.efi"
        old_sbat = self.root / "shim-old.sbat"
        new_sbat = self.root / "shim-new.sbat"
        new_unsigned = self.root / "shim-new-unsigned.efi"
        self.run(["objcopy", "--dump-section", ".sbat=" + str(old_sbat),
                  shim_unsigned])
        old_contents = old_sbat.read_text()
        if "shim,4," not in old_contents:
            raise FixtureError(
                "test shim does not advertise shim,4:\n" + old_contents)
        new_sbat.write_text(old_contents.replace("shim,4,", "shim,5,", 1))
        if "shim,5," not in new_sbat.read_text():
            raise FixtureError("failed to build shim,5 SBAT metadata")
        self.run(["objcopy", "--update-section", ".sbat=" + str(new_sbat),
                  shim_unsigned, new_unsigned])
        self.sign_copy(shim_unsigned, old_shim, self.db_key, self.db_cert)
        self.sign_copy(new_unsigned, new_shim, self.db_key, self.db_cert)

        grub_test = self.root / "sbat-grubx64.efi"
        self.strip_and_sign(self.args.grub, grub_test,
                            testca_key, testca_cert)

        sbata = self.root / "sbata"
        sbatl = self.root / "sbatl"
        sbata.write_text("sbat,1,2025010100\nshim,5\n")
        sbatl.write_text("sbat,1,2025010100\nshim,5\n")
        revocations_added = self.root / "revocations-added.efi"
        revocations_fixed = self.root / "revocations-fixed.efi"
        self.run([
            "objcopy",
            "--add-section", ".sbata=" + str(sbata),
            "--add-section", ".sbatl=" + str(sbatl),
            shim_unsigned, revocations_added,
        ])
        # objcopy places newly added sections at VMA 0.  shim rejects sections
        # below SizeOfHeaders, so move the payload sections into the image's
        # valid VMA range before signing.
        self.run([
            "objcopy",
            "--change-section-vma", ".sbata=0x1000",
            "--change-section-vma", ".sbatl=0x2000",
            revocations_added, revocations_fixed,
        ])
        revocations = self.root / "revocations.efi"
        self.sign(revocations_fixed, revocations, testca_key, testca_cert)
        wrong_revocations = self.root / "revocations-wrong-key.efi"
        self.sign(revocations_fixed, wrong_revocations,
                  self.rogue_key, self.rogue_cert)

        extra = [
            (grub_test, "::/EFI/BOOT/grubx64.efi"),
            (revocations, "::/EFI/BOOT/revocations.efi"),
        ]
        wrong_extra = [
            (grub_test, "::/EFI/BOOT/grubx64.efi"),
            (wrong_revocations, "::/EFI/BOOT/revocations.efi"),
        ]
        new_esp = self.make_esp("sbat-new", new_shim, extra)
        old_esp = self.make_esp("sbat-old", old_shim, extra)
        wrong_esp = self.make_esp("sbat-wrong-key", new_shim, wrong_extra)
        old_wrong_esp = self.make_esp("sbat-old-wrong-key", old_shim, wrong_extra)

        vars_applied = self.make_vars("sbat-applied")
        vars_rejected = self.make_vars("sbat-rejected")

        self.boot(
            "sbat-new-shim-applies-signed-revocations",
            vars_applied,
            new_esp,
            r"verified revocations[\s\S]*?SbatLevel variable initialization succeeded",
        )
        self.boot(
            "sbat-old-shim-revoked",
            vars_applied,
            old_esp,
            r"SBAT self-check failed: Security Policy Violation",
        )
        self.boot(
            "sbat-wrong-key-revocations-rejected",
            vars_rejected,
            wrong_esp,
            r"revocations failed to verify",
        )
        self.boot(
            "sbat-old-shim-passes-after-rejected-revocations",
            vars_rejected,
            old_wrong_esp,
            r"SBAT self-check succeeded",
        )

        self.result["tests"]["sbat"] = {
            "new_shim_generation": 5,
            "old_shim_generation": 4,
            "signed_revocations_applied": True,
            "old_shim_revoked": True,
            "wrong_key_revocations_rejected": True,
            "old_shim_bootable_after_rejected_revocations": True,
            "revocations_sha256": sha256(revocations),
            "wrong_key_revocations_sha256": sha256(wrong_revocations),
            "old_shim_sha256": sha256(old_shim),
            "new_shim_sha256": sha256(new_shim),
            "test_ca_certificate_sha256": sha256(testca_cert),
        }

    def run_all(self):
        self.require_tools([
            "openssl", "cert-to-efi-sig-list", "sign-efi-sig-list",
            "sbsign", "sbverify", "sbattach", "objcopy", "make",
            "mformat", "mmd", "mcopy", "virt-fw-vars",
            "qemu-system-x86_64",
        ])
        self.require(self.args.ovmf_code, "OVMF Secure Boot code")
        self.require(self.args.ovmf_vars, "OVMF variable template")
        self.prepare_keys()
        if self.args.only in ("dbx", "all"):
            self.test_dbx()
        if self.args.only in ("sbat", "all"):
            self.test_sbat()
        self.write_result()

    def write_result(self):
        self.result["artifact_directory"] = str(self.root)
        self.result["result"] = "PASS"
        (self.root / "result.json").write_text(
            json.dumps(self.result, indent=2, sort_keys=True) + "\n")
        sums = []
        for path in sorted(self.root.rglob("*")):
            if "shim-build" in path.parts:
                continue
            if path.is_file() and path.name not in ("result.json",) \
                    and path.suffix not in (".key", ".log", ".img"):
                sums.append("%s  %s" % (sha256(path), path.relative_to(self.root)))
        (self.root / "SHA256SUMS").write_text("\n".join(sums) + "\n")
        print("artifact directory:", self.root)
        print("result:", self.root / "result.json")


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", choices=("dbx", "sbat", "all"), default="all")
    parser.add_argument("--test-ca", type=Path, default=DEFAULT_TEST_CA)
    parser.add_argument("--shim-source", type=Path, default=DEFAULT_SHIM_SOURCE)
    parser.add_argument("--grub", type=Path, default=DEFAULT_GRUB)
    parser.add_argument("--ovmf-code", type=Path, default=DEFAULT_OVMF_CODE)
    parser.add_argument("--ovmf-vars", type=Path, default=DEFAULT_OVMF_VARS)
    parser.add_argument("--workdir", type=Path, default=None)
    parser.add_argument("--timeout", type=int, default=180)
    return parser.parse_args()


def main():
    args = parse_args()
    fixture = SecureBootRevocationFixture(args)
    try:
        fixture.run_all()
    except FixtureError as error:
        print("SECUREBOOT_REVOCATION_FIXTURE_FAIL", file=sys.stderr)
        print(str(error), file=sys.stderr)
        fixture.result["result"] = "FAIL"
        fixture.result["error"] = str(error)
        fixture.result["artifact_directory"] = str(fixture.root)
        (fixture.root / "result.json").write_text(
            json.dumps(fixture.result, indent=2, sort_keys=True) + "\n")
        print("artifact directory:", fixture.root, file=sys.stderr)
        return 1
    finally:
        fixture.close()
    print("SECUREBOOT_REVOCATION_FIXTURE_PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
