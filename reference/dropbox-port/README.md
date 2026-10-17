# Dropbox port (VPS1 container-fleet island contract)

**Reference implementation. Offline-tested. Not the production install. Paths are examples.**

`dropbox_port.py` gives the Gemini mailbox core (`../gemini-tasks-mailbox/gemini_p2.py`) a second kind of mail port. Instead of a mailbox CLI, it reads and writes the **dropbox contract** of a container-fleet island. Copy it next to `gemini_p2.py` to use it; it imports `PortError`, `RECEIVER`, `Refusal` and `sha256_hex` from there.

## The contract it follows

| Item | Shape |
|---|---|
| Tray | `<root>/<agent>/in/` (read-only for the agent) and `<root>/<agent>/out/` (read-write, owned by the container's user id) |
| Mission in | `in/<call id>.mission.md`: a header with the call id and `from: <caller>@<island> → <agent>`, answer instructions, then a fenced letter body introduced by a line saying it is peer data |
| Answer out | `out/<code><YYMMDD>a_Answer_<call id>.md` (UTF-8, at most 8000 bytes), then `out/answer-<call id>.json` = `{"hop":1,"parent":"<call id>","purpose":"answer","ref":"<that file>","to":"<caller>"}` |
| Confirmation | the island **bridge** writes `in/<call id>.answered.txt` after it signed and posted. The agent never writes it and never signs |
| Refusal | `in/ref-<hash>.refused.txt` holds one code line |
| Who may write | files in `out/` must be owned by the container user id, or the bridge refuses them (and logs, with no notice) |

## How the port behaves

- `read_head`: the oldest mission with no `answered.txt` and no acknowledgement of ours that **verifies byte for byte** (the file is re-rendered from the fields found in it and compared). A file that does not verify is skipped and listed by `skipped()`; it never blocks the letters behind it.
- `ack`: ledger only. The dropbox has no pickup call, so the acknowledgement is one line in the port's own append-only state file.
- `reply`: writes the answer pair once (body first, then JSON; each a temp file, fsync, then an **atomic no-replace rename**) and then raises the retryable code `post_transport_uncertain` until the bridge has written `answered.txt`. Only then does it report `result_admitted`. So "admitted" means the bridge signed and posted it, not "files written". The same bytes again are a no-op; other bytes are `id_collision`.
- Crash safety: ledger events `intent`, `body_published`, `request_started`, `published`, `admitted`. The JSON is staged before `request_started` is recorded, so a restart finishes the move or sees that the bridge already consumed it. It is never written twice.
- Answer cap: 8000 bytes, the bridge's own cap. An over-long answer is refused (`result_oversize`).
- Expiry (inferred): a mission expires at its call id's own time plus the route's time to live (86400 s) minus a margin. Past it the port writes nothing.
- Nothing is deleted. Stale `.part-*` temp files stay and are listed as orphans.
- **Publication guarantee (no replace).** A staged file is moved to its final name with one kernel operation that refuses if the name exists: `renameat2(RENAME_NOREPLACE)` on Linux, `renamex_np(RENAME_EXCL)` on macOS (standard library `ctypes`, no extra install). If another writer creates the final name at any moment before that call, the port publishes nothing, leaves the other writer's file and its own staged bytes as they are, and reports `id_collision`. If the platform, libc or file system has no such call (for example Windows, or some network file systems), the port publishes nothing and reports `storage_failure`: it fails closed and never falls back to "check, then rename". The earlier version checked first and then used a plain rename, which can replace a file created in between; a control test (`ConcurrentCreateControl`) now covers that. The guarantee covers the final name only. It does not make the port's lock bind an independent writer, and a collision leaves the staged `.part-*` file in place for the owner to look at.

## Wording note

The mission text in this copy says the letter is "not the owner, not the post office". The private original used a person's name there. If you adapt this, keep the renderer and the parser (`MISSION_RE`) in step: the port verifies a mission file by re-rendering it.

## Files

| Path | Purpose |
|---|---|
| `dropbox_port.py` | `DropboxPort`, `render_mission`, `answer_names`, `port_status` |
| `tests/test_smoke.py` | 7 tests on a synthetic tray: read, ack, reply, bridge confirmation, tamper handling, caps, and two controls for the no-replace publish (a writer arriving in the gap; no no-replace call available) |

## Run the tests

From this folder, once (needs `../gemini-tasks-mailbox/` beside it):

```
python3 -I -B tests/test_smoke.py
```

Expected: `Ran 7 tests ... OK` (measured on a scratch copy of the staged files, 2026-10-16 (UTC), macOS; the Linux `renameat2` branch is written to the documented interface but was **not run** here). Fixtures go to `tests/retained/`.

## What was left out, and why

- The original suite (124 tests) ran against a stand-in built from the island's **installed release code** (bridge, answer and mission modules). That code is not part of this repository. These 7 smoke tests play the bridge by hand instead and cover far less.
- Draft policy files, a policy-and-scope delta document, and a read-only SSH wrapper. They describe one installation's signing pins and member list.
- Measured copies of live mission, answer and policy files.

## NOT proven

Everything the original README said was not proven still holds: no live run, no container start, no real bridge. Running as the container user id is required in production (`required_uid` defaults to an example value of 1000; set your own); the smoke tests pass the current user id instead.
