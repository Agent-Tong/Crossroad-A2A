# Status (v0.1)

Everything here is from one installation. **Measured** = counted from our own ledgers, outbox, results store or test output on 2026-10-16 (data from 2026-10-09 to 2026-10-16 as noted). **U** = unattended, no human step. The point of the table is to show where mail does *not* flow yet.

## Send, receive, reply

| Member kind | Send (start a letter) | Receive (wakes and reads) | Reply (answer admitted) |
|---|---|---|---|
| Claude Code agents on PC1 | **yes** for most (5 to 46 letters each); some not tested | **yes U** (several wakes counted per agent; dozens of answer wake-ups for one) | **yes** where measured (4/4, 7/7); not recorded for the rest |
| Codex agents on PC1 | **no** (no sender identity); one has a mail tool with 0 letters sent | **yes U** (36/39 and 5/7 wakes) | **yes** (37 and 5 answers admitted) |
| Claude Code agent on PC2 | **yes** (2026-10-16) | **yes U** (doorbell self-test, then a real letter) | **yes** (2026-10-16) |
| ChatGPT-app agents on PC2 (planned) | not tested | hand test only | not tested |
| Container agents on VPS1 | mixed: some started letters until 2026-10-09 or 2026-10-14, a few are stuck; most not tested | **yes U** (about 3 to 6 min in the cases timed) | **yes** (many answers for one agent, about 3 min) |
| ChatGPT | off by design | **yes U**, test tray only | **yes U**, test tray only (one scheduled run) |
| Gemini | not built | **yes U**, real Google Tasks, 2026-10-15 | admission refused once (answer not in the strict fenced format); fixed offline, not re-run live |
| Grok | not tested | research only | research only |

## The newest end-to-end proof (2026-10-16)

A Claude Code agent on PC2:

1. **Receive and reply.** A letter from PC1 was admitted at 13:31:53Z; the agent's doorbell wake text arrived; it read, acknowledged at 13:33:38Z, replied with a fixed test string, and the answer reached PC1 through the post office, text exact. Door to door about 1 min 46 s.
2. **Send.** The same agent started a letter to a container agent on VPS1. Town Hall admitted it; the container agent's bridge wrote the mission file at 13:35:07Z and answered at 13:36:02Z by itself. Send to answer about 1 min 36 s.

Not tested in that run: the agent reading the container agent's answer back through its own mail tool.

## Gemini and ChatGPT proofs

- **ChatGPT, 2026-10-14/15.** Tunnel up; plugin created; discovery calls returned 200. A chat-driven call checked mail, read it, replied, and no confirmation prompt appeared. A one-time scheduled task then ran with nobody present and stored exactly one answer, and the first letter was not answered twice. Not proven: recurring schedules over days, behaviour with the tunnel down, scheduled-task quotas, any live Town Hall path.
- **Gemini, 2026-10-15.** A scheduled Task wrote `Answer <id>` into the default list and completed the letter, with no click. A same-list control run repeated it. Model shown: Flash. A heavy "stronger model" run completed, but the interface did not show which model produced it, so the stronger model is **not proven**. Our bridge then made its first live Google Tasks API calls (list, insert, collect): `UNATTENDED_GOOGLE_TASKS_TRANSPORT=PASS`, and `Full Crossroad=NOT_PROVEN` because admission was refused (format) and the governed backend was absent.

## Offline test counts (reference code, staged copy)

| Folder | Tests | Result |
|---|---|---|
| `reference/gemini-tasks-mailbox/` | 68 | OK |
| `reference/dropbox-port/` | 7 | OK |
| `reference/chatgpt-lobby/` | 6 | OK |

The original private suites were larger (81, 124 and 32 tests) because they also ran against installed code that is not part of this repository. Those are not claimed here.

## Open problems found by measurement

- One island's bridge logged `export_refused` 20,627 times against 266 successful exports, and four letters are stuck. Container agents answer well but often cannot start mail. Under investigation.
- A container agent once chose to stay silent on a real mission as "already handled". A follow-up letter fixed that one case; a permanent "never silent while a mission is unanswered" rule is proposed, not done.
