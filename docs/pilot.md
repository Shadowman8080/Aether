# Aether Pilot — help that asks first

Aether Pilot is the Copilot-style part of Aether. The assistant can offer to do
something on your computer; **you** decide whether it happens, and the machine
keeps a record of what actually ran.

It is not an assistant with a shell. Pilot works from a fixed list of actions that
ship with the system. A model may *name* one of them and fill in its parameters.
Anything else — an action that is not on the list, a parameter that does not fit
its format, a shell command in a reply — is refused.

```sh
aether-pilot catalog                       # what Pilot can offer on this machine
aether-pilot suggest "check for updates"   # propose; nothing runs
aether-pilot run <id from the proposal>    # confirm exactly that one action
aether-pilot audit                         # what you confirmed, and what happened
aether-pilot disable                       # refuse everything, for this account
```

Aether Settings has the same controls under **Aether Pilot**.

## What a proposal looks like

A proposal shows the action, the parameters, whether it needs administrator
approval, and the exact command that will run. Proposals expire after five
minutes and work once. A high-risk action such as turning off on-device AI for
every account needs an extra confirmation flag after you have read what it does.

## Why it is built this way

Nimbrel runs a small language model on your CPU and cannot open a network socket.
That guarantee is unchanged: Pilot reads the same local catalog whether a proposal
came from the model or from you typing a request. Administrator actions are
re-checked by a separate root helper that receives an action name and values — not
a command line — so a compromised desktop process still cannot ask root to run
something new.

The catalog is small on purpose. Adding an action is a reviewed change to a
data file, not something the model can do.

## Limits worth knowing

- A 0.8B model will sometimes suggest the wrong action. The confirmation step is
  what protects you, so read the proposal instead of approving on reflex.
- There is no in-app confirmation pane yet; confirmed actions run through
  `aether-pilot` and Aether Settings.
- No published image contains Pilot, and the administrator hand-off has not been
  run on a real image.
- The audit log records the action and its exit status. It does not record
  conversation text or command output.

Implementation notes: [`../src/pilot/README.md`](../src/pilot/README.md).
