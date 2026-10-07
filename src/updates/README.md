# Aether signed-package foundation

Status: the verifier and installed updater are prepared in the development build.
Public OS updates remain disabled pending operator-provisioned release trust.
No production release keys have been created. See [local key setup](LOCAL-KEY-SETUP.md).
The 0.3.2 recovery path passed trial/fallback/health boot checks and failed or
interrupted installation tests. See the [development record](../../docs/modern-desktop-20261006.md)
for test scope and remaining limitations, including base package ownership work.

## What exists

- `package_signing.py`: GnuPG detached package signatures and verification against
  an explicitly pinned full fingerprint. Existing signatures are not overwritten.
- `repository.py`: TUF metadata generation using upstream python-tuf. A new root
  requires at least two distinct root signers. Role keys are supplied by the
  operator; no private keys enter the generated repository. Artifacts and
  metadata use SHA-256, lengths, consistent snapshots, and signed expiration.
- `release.py`: executable Linux release assembler. It verifies package signatures,
  reviewed SHA-256 digests, `.PKGINFO` identity and architecture before copying
  package bytes into staging and signing the catalog and TUF metadata.
- `client.py`: verifies the pinned trust root and fresh metadata before downloading
  authorized artifacts. It persists trusted metadata to enforce rollback checks
  across restarts. It does not install or restart anything.
- `r2_fetcher.py`: private R2 transport using a separately supplied S3 client.
  Requests are restricted to one repository prefix. No credential is bundled.
- `test_updates.py` and `verify.py`: regressions covering real GnuPG signatures,
  end-to-end signed-package staging through TUF, expired/unsigned/tampered
  metadata, rollback, mixed repository versions, root quorum, wrong trust,
  architecture/channel mismatch, path escape and cached-file modification.

## Run the verification

Use an isolated Python environment, install `requirements.txt`, then run:

```text
python verify.py --output /path/to/validation
```

GnuPG and gpgv must be available. Windows tests can use Git for Windows' bundled
tools. Tests generate disposable keys and remove them afterward. A skipped test
is not counted as a fully passed validation. No release credential is needed.
`dependency-install-report.json` records the actual locally installed dependency
artifacts and hashes; it is not a Linux dependency lock file.

The suite also passes on the Linux build VM: 24 tests, 0 failures, 0 errors,
0 skips, Python 3.14.4, with `tuf` 7.0.1, `securesystemslib` 1.4.0,
`cryptography` 50.0.1 and `urllib3` 2.8.0.

## Bootstrap the trust root

`make_root.py` is the one-time ceremony that creates the four role keys and the
self-signed root:

```text
python make_root.py --output /secure/aether-root
```

It writes `root/root-1.pem .. root-N.pem` (the offline trust anchors),
`signers/{targets,snapshot,timestamp}.pem` (the online signer directory that
`release.py` consumes) and `trusted-root.json`. Private keys are mode 0600 and
the signer directory is mode 0700. At least two root signers are required.
`--no-encrypt` exists only for throwaway test roots.

Two root keys created on one machine are a bootstrap/development root, not
independent custody. Move each `root/*.pem` to separate offline media, and use
a real signing ceremony on separate hosts before trusting this root for
releases.

## Release assembly

After key provisioning:

```text
python release.py --plan release-plan.json --root trusted-root.json --signer-directory /protected/online-signers --output /staging/release-1
```

The release plan supplies a monotonically increasing integer `version`, `channel`,
`architecture`, exported `public_keyring`, full `signer_fingerprint`, and a
`packages` array containing `name`, `version`, absolute `archive`, and reviewed
`sha256`. Package archives must already have detached `.sig` siblings.

The signer directory must be owned by the invoking Linux user and mode 0700.
It contains mode-0600 `targets.pem`, `snapshot.pem`, and `timestamp.pem`. Encrypted
keys are unlocked through a local hidden prompt. Root private keys are never
required by this release command. PEM loading is an initial signer integration;
hardware-backed signing needs a separate tested adapter before being claimed.

Publish immutable targets and numbered root/targets/snapshot metadata first.
Publish `timestamp.json` last. The publisher still needs serialized version
allocation, interrupted-publication tests and authenticated R2 readback gates;
this implementation does not yet automate publication.

## Key custody and release gates still required

1. Keep public-release root keys independently held, offline or hardware-backed,
   with an independently recoverable backup and a tested rotation/revocation
   procedure. Two keys on one online builder do not provide compromise resilience.
   Disposable test keys must never become release trust roots.
2. Keep package signing, TUF role signing and R2 upload credentials separate.
   A release signature authorizes software from the signer; it does not establish
   that the software itself is safe. Review and test source/build recipes first.
3. Provision bucket-scoped read-only credentials separately for private clients.
   The existing publisher credential must never be put in an ISO, VMDK or client.
4. Pin initial public trust in an independently verified Aether installation.
   Never download the initial trust root from the repository and trust it blindly.
5. Automate timestamp refresh before its one-day expiry and monitor failures.
   Expired metadata must produce a visible failure, not “no updates available.”
6. Establish package file ownership and dependencies for the existing source-built
   base before core upgrades. Do not attach Arch or Ubuntu binary repositories.
7. Test native dpkg/apt install/upgrade/removal and recovery from interrupted kernel,
   initramfs and desktop updates on an isolated disk before user-disk deployment.
8. Preserve the requested policy: check automatically, ask before installation,
   no automatic restart. This policy is recorded; no timer is enabled yet.

The listed architecture identifiers are validation rules, not evidence that all
architectures have been built or tested. x64 and x86_64 are the same architecture.

References:
- https://theupdateframework.io/docs/security/
- https://manpages.debian.org/bookworm/apt/apt-get.8.en.html
- https://manpages.debian.org/bookworm/dpkg/dpkg.1.en.html
- https://github.com/theupdateframework/python-tuf
