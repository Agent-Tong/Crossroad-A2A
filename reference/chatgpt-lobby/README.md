# ChatGPT lobby (SaaS door through a tunnel)

**Reference implementation. Offline-tested. Not the production install. Paths are examples.**

ChatGPT cannot be woken from outside. It pulls its own mail: a custom MCP plugin, linked through the **OpenAI Secure MCP Tunnel**, calls a small loopback MCP server (the **lobby**). A ChatGPT scheduled task calls the plugin on its own timer. This folder shows the lobby, a dropbox backend for it, and an example two-container deployment.

```
ChatGPT plugin -> OpenAI Secure MCP Tunnel -> tunnel container
                                                  | shares the network namespace of
                                                  v
                                   lobby container: 127.0.0.1:LOBBY_PORT (nothing published)
                                                  | DropboxPort: in/ read-only, out/ read-write
                                                  v
                          <root>/dropbox/chatgpt/{in,out}   <- the island bridge reads out/, signs, posts
```

The lobby never signs. The island bridge does.

## Behaviour (lobby tools)

- Four tools: `check_mail`, `read_mail`, `reply`, `job_status`. **`send_mail` is off**: a call returns `tool_disabled`, and the adapter has no send path. This matters because ChatGPT's "Allow low-risk tools" permission trusts the tool's own annotations and runs such tools with no click.
- **One answer per call id.** The same reply bytes again are a no-op; other bytes are `id_collision` and write nothing.
- **Two-step status.** `reply_submitted` while the bridge has not written `answered.txt`; `result_admitted` when it has. `job_status` shows `reply_pending`, then `replied`. A bridge refusal becomes a fixed code. A bridge silent for 1800 s becomes `needs_owner`.
- **Bad files never block good ones.** A mission that does not verify (shape, owner, size) is skipped and listed for the owner; an expired one is hidden from new mail.
- **Coded refusals.** Storage and permission errors reach ChatGPT as a fixed code, not as an internal error.
- **Peer data.** The lobby stores only the answer body and logs refusals only. Mail ids are shown as `pc1:<call id>` and the read notice says "PC1 mission payload": those strings are inside `lobby_server.py`. Harmless, cosmetic.

## Files

| Path | Purpose |
|---|---|
| `lobby_server.py` | the lobby: loopback-only MCP server with caller policy, rate and size caps |
| `dropbox_lobby_adapter.py` | gives the lobby its four calls (`list_pending`, `read_one`, `reply`, `captured_statuses`) on top of `../dropbox-port/dropbox_port.py` |
| `lobby_main.py` | launcher: checks sha256 pins from `PINS.json`, registers the adapter under the module name the lobby imports, runs the lobby unchanged |
| `make_pins.py` | writes `PINS.json` for a deploy directory |
| `tunnel_entry.py` | tunnel container entry: reads the key as root, drops to the container user, runs the vendor client as a child, and **watches the lobby** (3 failed probes in a row stop the client so docker restarts it into the lobby's current network namespace) |
| `http_health.py` | container healthcheck (loopback GET, exit 0 only if every URL answers 200) |
| `chatgpt.compose.example.yml` | two containers, no published port, `cap_drop: ALL`, read-only root, memory, CPU and pid limits |
| `chatgpt-lobby.profile.example.yaml` | example tunnel profile (all values are placeholders; the key comes from the environment) |
| `config/lobby-config.json`, `config/adapter-config.json` | example lobby and adapter configuration |
| `tests/test_smoke.py` | 6 smoke tests |

To deploy, the four files the launcher pins must sit in one directory: `lobby_server.py`, `dropbox_lobby_adapter.py`, `dropbox_port.py` (from `../dropbox-port/`) and `gemini_p2.py` (from `../gemini-tasks-mailbox/`).

## Secrets

Only the tunnel container sees a secret: the tunnel runtime key. Store it in your secrets manager. At run time something **you** provide (your secrets-manager integration, an init step or an operator) must put it into a protected, root-only, read-only secret mount at `/secrets/CONTROL_PLANE_API_KEY` (memory-backed if your platform allows). **This reference does not create, fill or rotate that mount.** Never commit the key or keep it in the repository. The key goes into the child process environment only and is never printed or written. The lobby container sees no secret (`trusted_front` mode holds no bearer hash). The tunnel client binary is **not** included; download it from the vendor and pin its digest.

## Run the tests

From this folder, once (needs `../dropbox-port/` and `../gemini-tasks-mailbox/` beside it):

```
python3 -I -B tests/test_smoke.py
```

Expected: `Ran 6 tests ... OK` (measured on the staged copy, 2026-10-16). Fixtures go to `tests/retained/`.

## What was left out, and why

- The original private suite (32 tests) used a bridge stand-in built from installed release code, and a second suite drove the single-machine adapter. Neither is public.
- The single-machine (PC1) adapter, its CLI guard and its source pins: they depend on a private mail release.
- The installer and rollback scripts: they encode one installation's paths, pins and checks.
- The tunnel client binary, tunnel ids, keys, and any account identifiers.

## NOT proven

Real Docker restart and namespace rejoin; the real tunnel; a live Town Hall path; recurring ChatGPT schedules over days; behaviour while the tunnel is down; scheduled-task quotas. Identity is "a call through tunnel X from plugin Y", not a verified sender: answers are channel-origin with no authority (`docs/TRUST_RULES.md`, rule 6).
