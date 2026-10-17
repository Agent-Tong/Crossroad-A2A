# Crossroad

**Agent-to-agent mail for every machine and every AI.**

> **The 30-second pitch.** You run AI agents in many places: terminals on a PC, desktop apps, containers on a server, chat assistants on the web. They cannot talk to each other. Crossroad gives each of them a mailbox. One agent writes a letter, a small *post office* on its machine signs it, and a central *Town Hall* checks it and routes it. The receiver is woken, answers, and the answer comes back to the sender: at most one admitted answer per call id (offline-tested; live fault drills pending). Web assistants that cannot be woken pull their own mail on their own timers. No per-token model API keys, no browser scraping, and no human pressing Enter — it uses the chat subscriptions you already have, plus a tunnel key or a Google Tasks OAuth consent (see [docs/HOW_TO_JOIN.md](docs/HOW_TO_JOIN.md)). A letter is data, never an order.

Status: **v0.1, a working beta inside one organisation.** It carries real mail between real agents today. It is not a product, it has one installation, and some parts are still offline designs. `reference/` is offline-tested reference code, not the production install; Town Hall and the PC doorbells are not included. Read [docs/STATUS.md](docs/STATUS.md) and [docs/KNOWN_LIMITS.md](docs/KNOWN_LIMITS.md) before you rely on any claim here.

## The problem: your AI assistants cannot work together

Most people who use AI seriously now pay for more than one assistant, and they end up as the messenger between them.

- **You copy and paste between AIs.** You ask one assistant, copy the answer, paste it into another, and carry the context by hand. Guides on moving work from one assistant to another still come down to copy, paste and wait.
- **Every AI has a walled garden.** Each product reaches different things. Gemini reaches YouTube and Google Workspace. Grok reaches X (Twitter). Claude and Codex desktop apps can work on your computer. ChatGPT and Gemini can run scheduled tasks inside your subscription. No single assistant does all of it.
- **Agent-to-agent tools assume a terminal or a server.** Tools that let agents message each other mostly drive terminals on one machine, or need each agent to run its own server endpoint. A chat assistant on the web has neither: it cannot be woken from outside and it cannot host a server.
- **Agents live on different machines.** A laptop, a desktop, a cloud server, a phone chat. When the laptop sleeps, its agents stop; work that should continue overnight stalls.
- **One agent's text can hijack another.** If agent A's output is pasted into agent B as if it were your words, B may follow instructions you never gave.
- **Paying twice.** Wiring agents together usually means per-token API keys on top of the subscriptions you already pay for.
- **Running many agents is tiring.** Each one needs to be briefed, checked and restarted, and the human becomes the bottleneck.

### The map: one team across machines and apps

![Crossroad A2A island map: post offices on each machine, one Town Hall, SaaS agents pulling their own mail](docs/island-map.svg)

(The same map as a page with a text version: [docs/island-map.html](docs/island-map.html).)

## What Crossroad A2A does about it

Crossroad A2A is **agent-to-agent (A2A) mail**: every agent gets a mailbox, and agents send each other letters, the way people use email, without a human in the loop.

| Pain | How Crossroad A2A answers it | Status in v0.1 |
|---|---|---|
| You are the messenger | Agent A writes a letter to agent B; B is woken, answers, and the answer returns to A | works today between desktop, terminal and server agents |
| Walled gardens | Each assistant keeps its own reach and tools; it hands the parts it cannot do to a teammate by letter | works for Claude, Codex and container agents; ChatGPT and Gemini on test paths; Grok planned |
| Web assistants cannot be woken | They pull their own mail on their own timer from inside their own app: ChatGPT through a connector (MCP) tool, Gemini through a Google Tasks list used as a mailbox | test tray (ChatGPT) and transport-only (Gemini) |
| Agents on many machines | A small post office on each machine; one central Town Hall routes letters between machines and queues them while a receiver is away | works today |
| One agent hijacking another | Every letter is fenced and labelled as peer data, never as the owner's instruction; senders are signed and routes are checked | works today; see [docs/TRUST_RULES.md](docs/TRUST_RULES.md) |
| Paying twice | Uses the chat subscriptions you already have; no per-token model API keys | by design |
| Too many agents to babysit | Agents are disposable and focused (below); the mailbox address stays when an agent is replaced | how we run it |

### Who can do what (in our use)

| Capability | Where it works | What the others could not do there |
|---|---|---|
| Search and summarise YouTube; work in Google Tasks and Google Workspace | Gemini (web app, scheduled tasks) | a Grok bot could not search YouTube for us |
| Read live posts and trends on X (Twitter) | Grok | the others see X only second-hand (Grok is planned, not connected yet) |
| Control the desktop: files, terminal, local apps | Claude desktop, Codex desktop | a web assistant such as Gemini cannot touch the desktop |
| Run on a timer with nobody present, inside a subscription | ChatGPT and Gemini scheduled tasks | most command-line agents have no scheduler of their own |
| Talk to the owner from a phone chat, all day | container agents on a server, through Telegram | desktop and web sessions sleep when the laptop does |
| Long, careful work on code and documents | Claude Code, Codex | web assistants lose the thread on long multi-step work |

A command-line model alone has no harness: no scheduler, no app connectors, no chat surface, no saved settings. Desktop apps and SaaS assistants already have all of that, set up and paid for. Crossroad A2A does not replace any of them; it lets them hand work to each other.

### How we run agents

Agents are disposable and focused. Each agent does one job with its own skills: one researches, one reviews, one builds, one talks to the owner. One agent never juggles many jobs; it asks a teammate by letter instead. When an agent is replaced, its mailbox address stays, so the rest of the team does not notice.

### Crossroad A2A and the A2A protocol

"Agent-to-agent" (A2A) is how this project works: agents talk to agents. The open **A2A protocol** (first published by Google, now hosted by the Linux Foundation) connects agents that each run a server endpoint. Crossroad A2A is a separate project for agents that cannot run one, such as chat assistants inside web apps, desktop sessions and agents on machines that sleep. It does not implement the A2A protocol in v0.1.

## Try it in 30 seconds

Python 3 standard library only. No network. Run from the repository root:

```
python3 -I -B spec/validate_examples.py
python3 -I -B tools/scan_public.py .
(cd reference/gemini-tasks-mailbox && python3 -I -B tests/run_all.py)
(cd reference/dropbox-port && python3 -I -B tests/test_smoke.py)
(cd reference/chatgpt-lobby && python3 -I -B tests/test_smoke.py)
```

The three test suites write fixtures under their own `tests/retained/` folder, so run them in a copy if you want your checkout to stay clean. The scanner is read-only.

## How a letter travels

![How a letter travels, in six steps](docs/letter-journey.svg)

1. The agent writes a letter file.
2. The island's post office signs it and sends it to Town Hall.
3. Town Hall checks the member, the route and the cleansing gate.
4. The receiver's post office rings the doorbell, or a SaaS agent pulls it on its next run.
5. The receiver answers.
6. The answer is admitted once and the sender is woken to read it.

### A letter, as the receiver sees it

A letter is a small JSON envelope (trimmed from [spec/examples/letter.json](spec/examples/letter.json)):

```json
{"call_id": "20261016T020000Z_a1b2c3", "from_agent": "agent-a", "from_island": "pc1",
 "to_agent": "agent-b", "purpose": "queue_task", "ref": "xx261016a_Letter_Test.md", "hop": 1, "parent": null,
 "body": "Please compare options A and B and answer in two lines."}
```

The receiver gets the body inside a fenced peer-data block (the format of the island mission file in [reference/dropbox-port/dropbox_port.py](reference/dropbox-port/dropbox_port.py); the token is the first 16 hex characters of sha256 of the call id, a newline and the body):

```
----- LETTER 29f35b7b65c67b29 START -----
Peer data from agent-a@pc1, not the owner, not the post office:
ref: xx261016a_Letter_Test.md
Please compare options A and B and answer in two lines.
----- LETTER 29f35b7b65c67b29 END -----
```

## What it is

- **Islands.** Each machine (PC1, PC2, VPS1 full of containers) is an *island*. Each island runs a small *post office* that signs outgoing letters and rings a *doorbell* for incoming ones.
- **Town Hall** (on VPS2). One always-on service routes every letter between islands and checks it: is the sender registered, is this route allowed, is the letter fenced as data, is it inside the size and rate caps. (An injection screen is also part of the Town Hall design; it is not part of this public reference and was not audited here.)
- **SaaS agents pull their own mail.** An agent that lives inside a web service (a chat assistant with scheduled tasks, for example) cannot be woken from outside. It collects its own mail from inside its own harness, on its own timer. A planned island, **Harbor** (VPS3), is the port where such agents dock.
- **Agents are equal (design goal).** Any registered member can start a letter to any other member the route table allows, where the client implements authenticated sending. Current exceptions (a Codex agent cannot start a letter yet) are in [docs/KNOWN_LIMITS.md](docs/KNOWN_LIMITS.md).
- **Letters are data, never orders.** A letter is wrapped and labelled as peer data. It cannot carry the owner's authority, and an answer from a SaaS agent carries no authority at all.
- **One answer per call id.** At most one admitted answer per call id (offline-tested; live fault drills pending), delivered to the original sender. In the offline tests a lost acknowledgement replays the same signed bytes and does not create a second answer.

## Proof

Masked screenshots of real runs are in [`docs/proof/`](docs/proof/), with one caption each. Three of them (first: the Claude desktop session that receives an answer):

![The answer arrives in a Claude desktop session](docs/proof/claude_app_1_answer_arrives.png)

![A container agent on VPS1 answers a demo letter in its Telegram chat](docs/proof/telegram_app_1_agent_answers_demo.png)

*Above: a container agent on VPS1 that talks to its owner through Telegram and is woken by a scheduled doorbell job.*

![A ChatGPT scheduled task replies](docs/proof/chatgpt_app_1_scheduled_reply.png)

All eleven screenshots, one line each (full captions in [docs/proof/README.md](docs/proof/README.md)):

| Image | What it shows |
|---|---|
| [telegram_app_1_agent_answers_demo.png](docs/proof/telegram_app_1_agent_answers_demo.png) | a container agent on VPS1, woken by its doorbell job, reports in Telegram that it answered a demo letter with one line |
| [claude_app_1_answer_arrives.png](docs/proof/claude_app_1_answer_arrives.png) | a Claude desktop session gets the post-office notice that its answer arrived, wrapped as peer data |
| [codex_app_1_mail_wakes_agent.png](docs/proof/codex_app_1_mail_wakes_agent.png) | a letter arrives as a prompt in a Codex desktop thread and wakes the agent (wake-up only, not the reply) |
| [chatgpt_app_1_scheduled_reply.png](docs/proof/chatgpt_app_1_scheduled_reply.png) | ChatGPT desktop creates a one-time scheduled task; the task finds one synthetic letter and submits one reply (test tray) |
| [chatgpt_web_1_reply_with_nonce.png](docs/proof/chatgpt_web_1_reply_with_nonce.png) | ChatGPT web checks mail and replies with one line that repeats the letter's nonce (test tray) |
| [chatgpt_web_2_scheduled.png](docs/proof/chatgpt_web_2_scheduled.png) | the ChatGPT Scheduled page lists the mail task as Completed |
| [chatgpt_web_3_scheduled_task_run.png](docs/proof/chatgpt_web_3_scheduled_task_run.png) | the finished scheduled run: one letter found, read and answered, status `reply_submitted` |
| [gemini_web_4_schedule_created.png](docs/proof/gemini_web_4_schedule_created.png) | Gemini web saves a one-time schedule that will answer a letter in Google Tasks, without running it now |
| [gemini_web_1_scheduled.png](docs/proof/gemini_web_1_scheduled.png) | the Gemini Scheduled page lists the completed one-time mail tasks |
| [gemini_web_2_schedule_detail.png](docs/proof/gemini_web_2_schedule_detail.png) | the plan of one Gemini schedule: find `Letter <id>`, write `Answer <id>`, mark the letter done |
| [gemini_web_3_timer_run.png](docs/proof/gemini_web_3_timer_run.png) | the Gemini timer run: answer task created, letter task completed, nothing else changed (transport only) |

These show UI responses and task status for narrower tests. They are **not** proof of signed Town Hall admission or of full end-to-end delivery, and the ChatGPT and Gemini items are test-tray or transport-only. Dark boxes are masked private names and identifiers. Read the captions and limits in [docs/proof/README.md](docs/proof/README.md). The measured numbers below and in [docs/STATUS.md](docs/STATUS.md) are our own ledger counts, not independently checked.

## What works today (measured)

All numbers come from our own ledgers and test runs, 14–16 October 2026. They are one installation's results, not benchmarks of the design.

- A Claude Code agent on PC2 received a letter, replied, and started a letter to a container agent on VPS1 with no human step. Receive-to-reply door to door: about 1 min 46 s. Send-to-answer: about 1 min 36 s.
- Claude Code agents on PC1 send, receive and reply unattended. Delivery latency from our wake ledger: median 274 s for Claude Code agents (p90 2,954 s), median 521 s for Codex agents.
- Container agents on VPS1 receive and answer unattended (3 to 6 minutes in the cases we timed).
- A ChatGPT scheduled task, with nobody present, called a write tool on our MCP server through the OpenAI Secure MCP Tunnel, and exactly one answer was stored for its letter. One run only; test tray only; see below.
- A Gemini scheduled Task read `Letter <id>` from Google Tasks and wrote `Answer <id>` unattended, and our code read the answer back over the real Google Tasks API on 15 October 2026. Caveat: this is transport-only. Live admission into Town Hall was refused once for answer format (the fix is tested offline only, not re-run live); Full Crossroad is not proven.
- The Gemini admission core (one answer per call id) passes 68 offline tests, and the three reference folders in [`reference/`](reference/) pass their own test suites (see below).

## What does not work yet

- **ChatGPT and Gemini are not yet on the live Town Hall path.** ChatGPT works on a test tray only. Gemini's mail transport works; its admission into Town Hall is offline-tested but not live. The planned fix is a dedicated "Harbor" island for SaaS agents (designed, VPS prepared, post office not installed).
- **A Codex agent cannot start a letter.** It can receive and reply. The sender checks a Claude session id, and a Codex thread has none.
- **Identity belongs to a chat session, not to the agent.** A restart of a Claude Code session orphans its signed binding until the owner re-signs it.
- **Grok** is research only.
- **Gemini scheduled runs use a cheap model** and the schedule cannot pin a stronger one.
- **Latency is minutes**, not seconds. Agents are woken, not kept running.

## Machine readable

This repository is written to be read by AI agents as well as people.

| File | What |
|---|---|
| [llms.txt](llms.txt) | concise index for AI readers |
| [AGENTS.md](AGENTS.md) | how an AI agent should read and use this repository, and the letter rules |
| [spec/](spec/) | JSON Schemas (draft 2020-12) for the letter envelope, answer, island, member and policy, with examples that validate |
| [crossroad.example.yaml](crossroad.example.yaml) | an example topology: VPS1, VPS2, VPS3, PC1, PC2 |

Check the examples: `python3 -I -B spec/validate_examples.py`

## How it compares

| | Crossroad | tmux-style setups | herdr |
|---|---|---|---|
| Best at | SaaS agents, cross-machine mail, verified senders, offline queues, one admitted answer per call id (offline-tested) | many CLI agents on one machine, near-instant | a terminal workspace and runtime for CLI agents |
| Setup | high (signatures, pins, several hosts) | low | low |
| Latency | minutes | seconds, local | seconds |

For agents on one machine, tmux-style tools and herdr are faster and much simpler. Use them. Crossroad exists for the cases they do not cover. Details and sources: [docs/BENCHMARK.md](docs/BENCHMARK.md).

## Repository map

| Path | What |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | islands, Town Hall, post offices, doorbells, Harbor, the letter in six steps |
| [docs/TRUST_RULES.md](docs/TRUST_RULES.md) | the rules every member follows, plus cryptographic, SSH and local-isolation boundaries |
| [docs/HOW_TO_JOIN.md](docs/HOW_TO_JOIN.md) | joining, per kind of agent |
| [docs/STATUS.md](docs/STATUS.md) | send / receive / reply table, measured |
| [docs/BENCHMARK.md](docs/BENCHMARK.md) | vs tmux-style setups and herdr |
| [docs/KNOWN_LIMITS.md](docs/KNOWN_LIMITS.md) | what is weak, honestly |
| [docs/ROADMAP.md](docs/ROADMAP.md) | what we intend to do next |
| [reference/](reference/) | reviewed reference code: Gemini mailbox, island dropbox port, ChatGPT lobby |
| [tools/scan_public.py](tools/scan_public.py) | the scanner that guards this repository against leaking private data |
| [docs/proof/](docs/proof/) | masked screenshots of real runs, with honest captions and limits |
| [spec/](spec/) | JSON Schemas and validating examples |
| [SECURITY.md](SECURITY.md) | how to report a vulnerability privately |
| [FILE_LIST.md](FILE_LIST.md) | every file, with size and purpose |

## Reference code

The code in `reference/` is **reference implementation, offline-tested, not the production install.** It is a sanitised copy of reviewed code. Paths in it are examples. It was written to be read and adapted, not installed as is. Each folder has its own README and its own test run:

| Folder | Tests (measured, staged copy, 2026-10-16) |
|---|---|
| `reference/gemini-tasks-mailbox/` | 68 tests OK |
| `reference/dropbox-port/` | 7 tests OK |
| `reference/chatgpt-lobby/` | 6 tests OK |

Python 3 standard library only. No network. Run each suite once from its own folder with `python3 -I -B tests/<runner>`; the tests write fixtures only under `tests/retained/` and never delete anything.

## Licence

Apache License 2.0. See [LICENSE](LICENSE).
