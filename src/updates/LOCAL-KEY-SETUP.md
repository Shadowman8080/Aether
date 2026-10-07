# Release trust setup

Aether checks automatically and asks before installing. It never restarts
automatically. Public OS updates stay disabled until an administrator installs
the three trust files below. There are no release private keys in the images.

## Prepare signing keys locally

Use a trusted, offline machine and a new encrypted storage directory. Run:

```sh
umask 077
aether-signing-setup --output /path/on/encrypted-storage/aether-signing
```

The command asks for a new passphrase without displaying it. Do not send it in
chat, put it in a shell command, or upload the resulting private files. It refuses
an existing output directory. The default root threshold is two signatures.

Move the two `root/root-*.pem` keys to separately held offline storage, with
independent encrypted backups. Check that each backup can be restored before
removing the working copies. Generating two keys on one computer is only a
bootstrap step; it does not provide independent custody by itself. Root keys
authorize key changes and must not stay on the routine build/publishing server.

Keep `signers/targets.pem`, `snapshot.pem`, and `timestamp.pem` separately from
upload credentials. The repository tooling prompts locally when unlocking them.
Review each release before targets are signed. Refresh timestamp metadata before
expiry; expired metadata must fail visibly. Practice root rotation and key-loss
recovery in a disposable repository before publishing production updates.

Create a separate OpenPGP signing key using `gpg --full-generate-key`, choosing
an appropriate signing-capable key and a protected passphrase. Record its **full
fingerprint**, then export only its public key:

```sh
gpg --fingerprint
gpg --export FULL_FINGERPRINT > package-signers.gpg
```

Back up its secret key to encrypted offline storage using GnuPG's local tools.
Neither this secret key nor TUF private keys belong in Git, R2, an ISO or a VMDK.

## Provision clients after release validation

Independently verify the public trust material and repository URL. Install:

- `/etc/aether-updates/trusted-root.json`: the reviewed TUF public root.
- `/etc/aether-updates/package-signers.gpg`: exported OpenPGP public key.
- `/etc/aether-updates/repository.json`: repository configuration below.

All three must be regular root-owned files, without group/other write access.
The configuration contains no secret:

```json
{
  "url": "https://YOUR-REVIEWED-UPDATE-ENDPOINT/aether",
  "channel": "development",
  "package_fingerprint": "REPLACE_WITH_FULL_PUBLIC_KEY_FINGERPRINT"
}
```

This example is deliberately invalid until real values are substituted. This
installed HTTP client requires an HTTPS endpoint accessible to the device. A
private R2 publisher token must **never** be used here. Private distribution needs
a separately configured download gateway; the installed client does not consume
R2 publisher credentials or generate signed download URLs.

```sh
sudo aether-update check
aether-update status
systemctl list-timers aether-update-check.timer
```

Before enabling a public repository, validate its package ownership/dependencies,
trial boot, interrupted-update recovery and signing rotation. Checkpoints share
user homes and consume space on the same disk; they are not independent backups.
Keep the recovery ISO and a separately stored encrypted backup available.
