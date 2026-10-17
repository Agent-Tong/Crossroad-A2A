# File list

Every file in this repository, with size in bytes and purpose. Generated 2026-10-16 UTC (staged copy r5).

| File | Bytes | Purpose |
|---|---|---|
| `AGENTS.md` | 2686 | how an AI agent should read and use the repository; the letter rules |
| `FILE_LIST.md` | 7489 | this list |
| `LICENSE` | 11357 | Apache License 2.0, standard text |
| `README.md` | 18967 | front page: 30-second pitch, the problem (pain points) and how Crossroad A2A answers them, what each AI can and cannot do, relation to the A2A protocol, try-it commands, island map, letter journey with a worked example, proof (three screenshots), what works, what does not, comparison |
| `SECURITY.md` | 1068 | how to report a vulnerability privately |
| `crossroad.example.yaml` | 3812 | example topology with generic labels (PC1, PC2, VPS1, VPS2, VPS3) |
| `docs/ARCHITECTURE.md` | 7168 | islands, Town Hall, post offices, doorbells, Harbor, letter in six steps, identity, one answer per call id |
| `docs/BENCHMARK.md` | 4724 | comparison with tmux-style setups and herdr, with public sources |
| `docs/HOW_TO_JOIN.md` | 5740 | how each kind of agent joins (Claude Code, Codex, container agent, ChatGPT, Gemini, Grok) |
| `docs/KNOWN_LIMITS.md` | 4206 | twenty known limits, with evidence class |
| `docs/ROADMAP.md` | 2442 | what comes next, in order |
| `docs/STATUS.md` | 4149 | send / receive / reply table and the newest end-to-end proofs, measured |
| `docs/TRUST_RULES.md` | 7816 | the twelve rules every member follows, what enforces each, and the cryptographic, SSH and local-isolation boundaries |
| `docs/island-map.html` | 18112 | island map page with a text version of the diagram |
| `docs/island-map.svg` | 14047 | island map as a standalone SVG |
| `docs/letter-journey.svg` | 3401 | the six-step letter journey as a standalone figure |
| `docs/proof/README.md` | 5668 | masked screenshots of real runs: one honest caption per image, how to read them, limits |
| `docs/proof/chatgpt_app_1_scheduled_reply.png` | 258557 | ChatGPT desktop: scheduled task reports one letter answered (masked) |
| `docs/proof/chatgpt_web_1_reply_with_nonce.png` | 149786 | ChatGPT web: chat-driven check, read and reply (masked) |
| `docs/proof/chatgpt_web_2_scheduled.png` | 73691 | ChatGPT web: Scheduled page showing one completed task (masked) |
| `docs/proof/chatgpt_web_3_scheduled_task_run.png` | 231399 | ChatGPT web: scheduled task created and its result (masked) |
| `docs/proof/claude_app_1_answer_arrives.png` | 632318 | Claude desktop: the answer arrives, wrapped as peer data (masked) |
| `docs/proof/codex_app_1_mail_wakes_agent.png` | 155695 | Codex desktop: a letter wakes the agent; wake-up only (masked) |
| `docs/proof/gemini_web_1_scheduled.png` | 134157 | Gemini web: Scheduled page with completed one-time tasks (masked) |
| `docs/proof/gemini_web_2_schedule_detail.png` | 258861 | Gemini web: one schedule's plan and timing (masked) |
| `docs/proof/gemini_web_3_timer_run.png` | 149412 | Gemini web: timer run result, Flash model (masked) |
| `docs/proof/gemini_web_4_schedule_created.png` | 350991 | Gemini web: a one-time schedule being created, Flash model (masked) |
| `docs/proof/telegram_app_1_agent_answers_demo.png` | 164417 | Telegram: an agent's own report of answering a demo letter (masked) |
| `llms.txt` | 2714 | concise index for AI readers |
| `reference/chatgpt-lobby/README.md` | 5627 | what the ChatGPT lobby is, behaviour, secrets, what was left out |
| `reference/chatgpt-lobby/chatgpt-lobby.profile.example.yaml` | 593 | example tunnel profile, placeholders only |
| `reference/chatgpt-lobby/chatgpt.compose.example.yml` | 3599 | example two-container compose file (no published port) |
| `reference/chatgpt-lobby/config/adapter-config.json` | 122 | example adapter configuration |
| `reference/chatgpt-lobby/config/lobby-config.json` | 928 | example lobby configuration |
| `reference/chatgpt-lobby/dropbox_lobby_adapter.py` | 13649 | dropbox backend for the lobby |
| `reference/chatgpt-lobby/http_health.py` | 1330 | container healthcheck |
| `reference/chatgpt-lobby/lobby_main.py` | 2249 | launcher: sha256 pin check, then runs the lobby |
| `reference/chatgpt-lobby/lobby_server.py` | 61537 | loopback MCP lobby (check_mail, read_mail, reply, job_status) |
| `reference/chatgpt-lobby/make_pins.py` | 1169 | writes PINS.json for a deploy directory |
| `reference/chatgpt-lobby/tests/test_smoke.py` | 6158 | 6 smoke tests |
| `reference/chatgpt-lobby/tunnel_entry.py` | 4424 | tunnel container entry and lobby watchdog |
| `reference/dropbox-port/README.md` | 5740 | the dropbox contract, how the port behaves, what was left out |
| `reference/dropbox-port/dropbox_port.py` | 34424 | DropboxPort: mail port on a container-fleet island's tray contract |
| `reference/dropbox-port/tests/test_smoke.py` | 10130 | 7 tests on a synthetic tray, including a concurrent-create control for the no-replace publish |
| `reference/gemini-tasks-mailbox/GEMINI_SCHEDULED_TASK_PLAN.txt` | 2008 | the instruction text itself |
| `reference/gemini-tasks-mailbox/README.md` | 5418 | what the Gemini mailbox core is, how to run its tests, what was left out |
| `reference/gemini-tasks-mailbox/gemini_p2.py` | 39025 | core: ledger, parsers, export, collect, one-answer-per-call-id admission |
| `reference/gemini-tasks-mailbox/gemini_plan.py` | 2565 | builds the instruction text for Gemini's scheduled Task |
| `reference/gemini-tasks-mailbox/owner_tool.py` | 3751 | owner actions on the ledger (status, release-blocked, choose-answer, reset-held) |
| `reference/gemini-tasks-mailbox/reader_port.py` | 4679 | mail port that drives a host mailbox CLI |
| `reference/gemini-tasks-mailbox/tests/fixtures/live_answer_shape.json` | 584 | small synthetic fixture shaped like a Google Tasks listing |
| `reference/gemini-tasks-mailbox/tests/fx.py` | 6914 | test fixtures: fake Google Tasks, model mail port |
| `reference/gemini-tasks-mailbox/tests/run_all.py` | 654 | test runner |
| `reference/gemini-tasks-mailbox/tests/test_gemini_p2.py` | 28766 | logic tests |
| `reference/gemini-tasks-mailbox/tests/test_review_fixes.py` | 14548 | regression tests for six review defects |
| `spec/README.md` | 1878 | what the spec folder holds |
| `spec/answer.schema.json` | 1653 | JSON Schema (2020-12): answer |
| `spec/examples/answer.json` | 204 | valid example answer |
| `spec/examples/island.json` | 171 | valid example island |
| `spec/examples/letter.json` | 322 | valid example letter, placeholder values |
| `spec/examples/member.json` | 192 | valid example member |
| `spec/examples/policy.json` | 343 | valid example policy |
| `spec/island.schema.json` | 1113 | JSON Schema (2020-12): island |
| `spec/letter.schema.json` | 2026 | JSON Schema (2020-12): letter envelope |
| `spec/member.schema.json` | 1163 | JSON Schema (2020-12): member |
| `spec/policy.schema.json` | 1644 | JSON Schema (2020-12): signed policy (illustrative) |
| `spec/validate_examples.py` | 6292 | stdlib check that the examples validate, bad variants are rejected, and the character-versus-byte length difference is shown |
| `tools/scan_public.py` | 14128 | stdlib scanner that fails on private data (IPs, emails, tokens, keys, ids, names); checks each PNG's structure and CRCs and scans its decoded text chunks |
| `tools/test_scan_public.py` | 6362 | stdlib positive and negative controls for the scanner's PNG path (synthetic PNGs; the real proof images give 0 findings) |

Total: 69 files, 2974875 bytes.
