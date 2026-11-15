# Aether Pilot — assistant proposes, person confirms

Pilot is Aether's Copilot-style layer: the assistant can *offer* to do something
on the machine, a person approves it, and the action is logged. It is deliberately
the narrowest possible way to give a model hands.

## Why it is not "the AI runs commands"

Nimbrel's engine is a 0.8B text model on the CPU. Asking it to invent shell
commands and running them as root would be a security hole with extra steps.
Pilot instead works from a **catalog** of admin-vetted actions:

```
model output  ──▶  one action id + typed parameters
                        │  validated against actions.json
                        ▼
                  pending proposal (TTL 300 s, single use)
                        │  a person runs `aether-pilot run <id>`
                        ▼
                  user action  ──────────────▶ subprocess (argv list)
                  admin action ──▶ pkexec /usr/libexec/aether-pilot-admin
                                          │ re-reads a root-owned catalog
                                          ▼
                                    subprocess (argv list)
```

A model can name an action that does not exist, or fill a parameter with
`; rm -rf /`. Both are rejected: the id must be in the catalog and every
parameter is checked against a `pattern` or `choice` from that catalog. The
administrator helper never receives a command line, only an id and values, and
builds the argv itself.

The model also never sees the audit log, and the engine still cannot open an IP
socket — the on-device guarantee is unchanged.

## Catalog

`actions.json` ships with the actions the image can actually run. Each entry is:

```json
{
  "id": "install.flatpak",
  "title": "Install an application",
  "summary": "Installs one Flatpak application for this account.",
  "phrases": ["install app", "install application"],
  "privilege": "user",
  "risk": "medium",
  "params": {"ref": {"type": "pattern", "pattern": "...", "title": "Flatpak reference"}},
  "argv": ["/usr/bin/flatpak", "install", "--noninteractive", "--user", "{ref}"]
}
```

Validation refuses duplicate ids, unknown or unused parameters, non-absolute
programs, unsafe argument tokens, bad risks, bad privileges and patterns that do
not compile. A catalog with a shell metacharacter in `argv` does not load at all.

`privilege: admin` actions run through the root helper only. `risk: read` actions
need no confirmation flag; `high` additionally needs `--yes` after the person has
read what it does.

## Commands

```sh
aether-pilot catalog                      # what this machine can offer
aether-pilot suggest "check for updates"  # propose; nothing runs
aether-pilot suggest --model-answer reply.md   # validate an assistant's proposal block
aether-pilot run 4f2c9a1b7d3e5f60         # single-use confirmation
aether-pilot audit --limit 20             # what was confirmed and what happened
aether-pilot disable                      # refuse everything for this account
```

An assistant reply becomes a proposal only if it contains a JSON block such as:

```json
{"action": "install.flatpak", "params": {"ref": "org.example.Tool"}}
```

Prose that describes a command is not executable. That is the whole point.

## Privacy

- Proposals, the audit log and the enable/disable flag live in
  `$XDG_STATE_HOME/aether/pilot` with mode `0700`; the log is `0600`.
- Audit entries contain the action id, the validated parameters, the privilege,
  the status and the exit code. They contain no conversation text, no secrets and
  no command output.
- Pilot is local-only. It does not call a service and does not need an account.

## Status

Implemented and unit-tested offline (`test_pilot.py`): catalog validation,
rejection of forged and malformed model proposals, parameter re-validation,
single-use and expiring confirmations, high-risk confirmation, the disabled
switch, the audit file's permissions, and the fact that execution never passes a
shell. The root helper is tested against its own catalog re-read and rejects
non-admin ids, wrong parameter counts and invalid values.

Not done: no booted image contains Pilot; the `pkexec` hand-off to the helper has
not been exercised on a real image; there is no in-app confirmation pane — the
confirmed flow today is the `aether-pilot` command and the Aether Settings page;
and the action list is small on purpose and must be extended by review, not by
the model.
