# Checkpoint — 2026-09-28

User requested implementation of signed software packages using best practices.
Default remains automatic checks, explicit approval to install, no auto restart.

Local implementation and validation are in this directory. Latest receipt:
`../../outputs/Aether-update-signing-validation/validation.json` and `test.log`.
24 tests passed with no skips. These are Windows tests, real disposable GnuPG
signatures, upstream TUF verification and mocked R2 transport. No private release
keys were created. No packages were installed into Aether and nothing was uploaded.

Builder SSH to root@192.168.48.135 timed out twice. Network permission was granted
for the turn. VMware vmrun reports zero running VMs. Found matching builder:
`C:\Users\User\OneDrive\Documents\Virtual Machines\Ubuntu (2)\Ubuntu (2).vmx`
displayName Ubuntu, 16 CPUs, 16 GiB, MAC 00:0c:29:3a:82:b2 matching known builder.
VMnetDHCP and VMware NAT Service are running. Requested/granted write permission
to that VM folder to start it. Both forward-slash and native-backslash vmrun
start attempts returned “The virtual machine cannot be found”, despite the VMX
and disk descriptor being readable. No VMware settings or disks were edited.

An async question asks the user to start Ubuntu and provide `hostname -I`.
Await that prerequisite before native build/deployment. Do not repeatedly retry
the same failed start command or claim that the VM was started.

Next: upload this source tree (excluding .venv/test caches) to /opt/aether/updates;
install pinned Linux dependencies in an isolated venv and record their hashes;
run the test suite on Linux; integrate real dpkg/apt install/upgrade/removal tests
in a disposable root against the shipped dpkg and apt.
Check available disk capacity first (last known 2.7 GiB free).

Production key custody, trust provisioning, rotation/revocation, private read-only
device access, safe R2 publication with serialized versions, timestamp refresh,
source-base ownership migration, recovery, and desktop/timer integration remain.
The release assembler works with externally provisioned signer keys; its key
loading path and CLI have not yet been exercised on Linux. Do not promote the
disposable test keys or present these libraries as an operational OS updater.
