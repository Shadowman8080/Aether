# Nimbrel — on-device AI

Nimbrel is Aether's AI assistant. The defining property is that **inference runs
on the CPU of the machine you are sitting at**. There is no API key, no account,
no pairing, and no outbound request.

## What ships in the 0.3 image

| File | Role |
|---|---|
| `nimbrel-engine.service` | llama.cpp CPU inference, Unix socket only |
| `nimbrel-engine-start` | engine launcher wrapper |
| `nimbrel-local.service` | local gateway for desktop sessions |
| `local_server.py` | Unix-socket gateway + `SO_PEERCRED` authorisation |
| `server.py` | shared request handling and task definitions |
| `client.py` | desktop transport, TLS pinning, explicit file sharing |
| `main.cpp` | Qt desktop client |
| `runner.cpp`, `runner.json`, `dock.py` | launcher helper and dock integration |
| `model.json` | pinned model provenance (repo, revision, SHA-256, licence) |
| `setup-remote-gateway.sh` | **legacy** network-gateway deployment — see below |

## Request path

```
Qt client
   │  AF_UNIX
   ▼
/run/nimbrel/api.sock            (mode 0666, owned by nimbrel)
   │  LocalHandler.authorized()
   │  SO_PEERCRED → uid == 0 or uid >= 1000
   ▼
/run/nimbrel-engine/engine.sock  (mode 0700, private runtime dir)
   │
   ▼
llama-server  (Qwen3.5 0.8B Q4_0, nproc threads, no GPU layers)
```

There is no network hop at any stage. `client.py` returns
`{"mode": "local", "server": "On this device"}` unconditionally — on-device is
the default, including for users previously paired to a remote host.

## Why the engine cannot leak

`nimbrel-engine.service` sets `RestrictAddressFamilies=AF_UNIX`. That is a
kernel-level restriction, not an application convention: the engine is not
permitted to create an `AF_INET` or `AF_INET6` socket at all. Combined with
`ProtectSystem=strict`, `ProtectHome=yes`, `PrivateDevices=yes`,
`NoNewPrivileges=yes` and a 3 GB `MemoryMax`, the model process has no route to
the network, to your home directory, or to most of the filesystem.

The desktop-facing socket is deliberately mode `0666` so any local account can
talk to it; authorisation is per-request via `SO_PEERCRED`, which the kernel
supplies and cannot be spoofed.

## Honest limits

- **The model is 0.8B.** It is good at definitions and light drafting and it will
  state wrong things confidently. The UI labels answers *"Check important
  answers"*. Do not treat its output as authoritative.
- **No command execution, no network access, no vision, no speech-to-text, no
  image generation.** These are declared `false` in `/v1/capabilities` and are
  refused, not merely undocumented.
- Context window is 8192 tokens and the client truncates at 12000 characters.
- Chats are stored locally under the Nimbrel state directory (`0700`).
- Performance is CPU-bound and varies substantially with the machine and load.
  The current baseline x86-64 engine disables BMI2, SSE4.2, AVX/AVX2 and FMA.
  Earlier performance measurements do not certify this rebuilt engine.

## `setup-remote-gateway.sh` is not what the image uses

This script provisions the **earlier** design: a TLS gateway reachable over the
network on `192.168.48.135:9443` plus an engine on `127.0.0.1:8088`. It is kept
for historical reference and for anyone who explicitly wants a remote host.

The 0.3 image does **not** use it. The shipped image uses the two Unix-socket
units in this directory. If you are auditing the running system, read those two
unit files, not the script.

## Model provenance

`model.json` pins everything needed to reproduce or audit the weights:

- Repository `ggml-org/Qwen3.5-0.8B-GGUF`
- Revision `8fea620810c4afa23dd6443f999a48574c1611a3`
- SHA-256 `57d1997790d1744fba5b40a7317df71ea5e2acee28c47e78f0cce39c0703f8cf`
- 563,036,064 bytes, Apache-2.0

The inference engine is llama.cpp at commit
`2145525a4081d66ff1a87cf43ef809f95a85ac0c`, built as a generic CPU target.

## Status

Implemented and verified on-device. **Not** wired to any hosted model, and there
is no model downloader — the weights ship in the image. Model updates, larger
models and any hardware acceleration are unfinished work.
