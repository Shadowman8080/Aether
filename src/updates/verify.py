#!/usr/bin/env python3
"""Run local security regressions and write an explicit validation receipt."""
import argparse
import importlib.metadata
import io
import json
import platform
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
suite = unittest.defaultTestLoader.discover(str(Path(__file__).parent), pattern="test_updates.py")
log = io.StringIO()
result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
args.output.mkdir(parents=True, exist_ok=True)
(args.output / "test.log").write_text(log.getvalue())
receipt = {
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "platform": platform.system(), "python": platform.python_version(),
    "tests_run": result.testsRun, "failures": len(result.failures),
    "errors": len(result.errors), "skipped": len(result.skipped),
    "passed": result.wasSuccessful() and not result.skipped,
    "dependencies": {name: importlib.metadata.version(name) for name in
        ("tuf", "securesystemslib", "cryptography", "urllib3")},
    "scope": "Local package signatures, TUF metadata and staging, mocked private R2 transport",
    "linux_installation_tested": False, "r2_live_tested": False,
    "iso_modified": False, "vmdk_modified": False,
    "release_keys_created": False,
}
(args.output / "validation.json").write_text(json.dumps(receipt, indent=2) + "\n")
print(log.getvalue())
sys.exit(0 if receipt["passed"] else 1)
