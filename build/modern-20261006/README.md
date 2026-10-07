# Native modern-desktop build

These recipes run inside the existing source-built Aether root, never against
Ubuntu's target libraries. The Ubuntu VM supplies the build host and virtualization
tools only. Compile parallelism uses all available CPUs.

`sources.lock.json` records the upstream URLs and SHA-256 hashes. Extract each
source under `inspect/KEY`, with its single upstream root directory beneath it.
The build scripts bind this workspace at `/modern` in a private mount namespace.
The established Aether build root is `/opt/aether/build/apt-root`.

1. `build-native.sh` builds the upstream components into the build root and `stage`.
2. `build-python.sh` builds TUF and cryptography dependencies from source using
   the separately bootstrapped build-only Rust toolchain. The final dependency
   artifacts and upstream source hashes are recorded in `python-build-report.json`.
3. `build-firstparty.sh` compiles Settings and Nimbrel from `project/src`.
4. `package-native.sh` creates individual native dpkg packages, records ownership
   conflicts and shared-library dependencies, and stops on unresolved linkage.
   Unowned existing base libraries are recorded separately in `native-packages.json`.
5. `install-integration.py ROOT SOURCE BUILD` prepares an explicit offline Aether
   root. It normalizes text launchers to Linux line endings and installs no keys.
6. `package-integration.py` packages the first-party integration and rebuilds its
   initramfs during installation. Its paths are fixed to this candidate workspace.
7. `build-iso.sh`, `build-disk.sh` and `test-boot.py` build and check disposable
   images. They never select a user's VMware disk automatically.

These are recorded development recipes, not yet a one-command clean bootstrap.
Keep all native source archives and Python source archives alongside these
recipes, plus the Rust crate sources used by cryptography. Build-only Rust
compiler binaries are not installed in the distributable root. Release artifacts
must have their own hashes and boot-test receipts; source compilation alone is
not evidence that an image boots or that an OS upgrade can recover.
