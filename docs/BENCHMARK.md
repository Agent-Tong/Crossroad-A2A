# Crossroad compared with tmux-style setups and herdr

Written 2026-10-16. Crossroad's numbers are **measured** on one installation. The other columns come from the other projects' own documentation and pages, read on the same day and **not re-tested by us**. Where a cell says "inferred" we did not find a documented number. "Not documented" means we did not find it in the project's pages; it does not mean the feature is absent, and "not tested" means we did not test it.

## What is being compared

- **tmux-style.** Plain tmux scripts and other pane-driven tools: one agent talks to another by typing into its pane (`send-keys`, `capture-pane`). Example: claude-squad. **Claude Code agent teams are not in this column.** Anthropic documents them as named teammates with JSON mailbox files and local task state, which is a different mechanism from raw keystrokes ([architecture](https://code.claude.com/docs/en/agent-teams#architecture)). We did not evaluate agent teams, or any other harness's own messaging, against Crossroad. Other harness semantics were not evaluated. Leaving them out does not claim they lack sender identity or delivery guarantees; it only says we did not compare them.
- **herdr.** A terminal workspace and runtime for CLI agents (project `herdrdev/herdr`, v0.9.5 released 14 October 2026, Apache-2.0).
- **Crossroad.** Signed letters between islands through Town Hall, SaaS agents pull their own mail.

## Table

| Benchmark | Crossroad | tmux-style | herdr |
|---|---|---|---|
| Reaches SaaS agents (ChatGPT, Gemini web) | **partial** (test tray for ChatGPT; transport-only for Gemini — live admission refused once for format, fix tested offline only) | no, CLI in a pane only | no, CLI terminals only |
| Cross-machine | **yes** (PC1, PC2, VPS1, VPS2) | no, local | yes, over SSH |
| Sender identity | signed bindings, checked at Town Hall | none in a plain tmux pane (the keystrokes carry no sender) | not documented |
| Delivery guarantee | persistent ledger, at most one admitted answer per call id (offline-tested; live fault drills pending) | best effort when typing into a pane (inferred: a keystroke gives no delivery receipt) | queue admission only; subscription history is documented as not durable ([socket API](https://herdr.dev/docs/socket-api/)) |
| Works with no human and no open terminal | yes, doorbell + timers | needs a live session | yes, background server |
| Delivery latency | median 274 s, p90 2,954 s (Claude Code agents); median 521 s (Codex agents); answer wake-up median 140 s; SaaS bound by timers (about hourly) | not documented (seconds, local; inferred) | not documented (seconds; inferred) |
| Prompt-injection exposure | letters fenced as data; SaaS answers have no authority; neither prevents a receiver from acting on a hostile letter (see [TRUST_RULES.md](TRUST_RULES.md)) | anyone who can type into a pane | socket auth not documented |
| Offline queue (target asleep) | yes, letters wait | none in a plain pane (inferred: tmux itself holds no queue) | not documented as durable; processes do not survive a restart |
| Audit trail | ledgers and reports | transcripts | optional history log |
| Setup effort | **high** (signatures, pins, several hosts) | low, one install line | low |
| Upkeep | **high** (re-bind on restart; weekly Google consent while in Testing) | low | low |
| Maturity | one organisation, beta | claude-squad about 8.6k stars (AGPL-3.0) | about 44k stars; first release March 2026 |
| Cost | $0 software; each wake costs one agent turn | free (plain tmux); claude-squad is AGPL-3.0 | free (Apache-2.0) |

Star counts, licences and release dates were read from the project pages on 2026-10-16 and re-checked independently the next day.

## Verdict

For agents on one machine, tmux-style tools and herdr are **faster and far simpler**. Use them. Crossroad wins only where they cannot go: SaaS agents, cross-machine mail with verified senders, offline queues and one admitted answer per call id (offline-tested).

Our weakest points are setup and upkeep. The planned Harbor island and agent-owned identity (see [ROADMAP.md](ROADMAP.md)) attack them directly. Our latency is minutes, not seconds, because agents are woken rather than kept running.

## Sources

- herdr: https://github.com/herdrdev/herdr and https://herdr.dev/docs/socket-api
- claude-squad: https://github.com/smtg-ai/claude-squad
- Claude Code agent teams (documented separately, not compared here): https://code.claude.com/docs/en/agent-teams#architecture
- herdr socket API (non-durable subscription history, queue admission): https://herdr.dev/docs/socket-api/
- Crossroad numbers: our own wake ledger, outbox, results store and bridge logs, read-only, 2026-10-16.
