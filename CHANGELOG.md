# Changelog

## v0.2.1 (2026-11-25)

Documentation fix. No code change.

Changed
- `docs/island-map.svg`, `docs/island-map.html` and `docs/ARCHITECTURE.md` now show Harbor as live (it hosts the Gemini door) and the Gemini connector route (Route A: Gemini app, remote MCP connector, OAuth door, Town Hall; live once on 2026-11-23, started by a human). The Google Tasks route (Route B) is shown as reference code, not run live in v0.2.
- `README.md`: three stale lines about Harbor and Gemini brought in line with the above.
- `docs/ROADMAP.md`, `docs/KNOWN_LIMITS.md`, `docs/BENCHMARK.md`: one stale "Harbor is planned" line each, now live.
- Version labels v0.2 -> v0.2.1 in `README.md` (status line), `llms.txt`, `SECURITY.md`, `crossroad.example.yaml`, `docs/STATUS.md`, `docs/island-map.html`, `docs/island-map.svg`.
- `FILE_LIST.md`: sizes updated.

Unchanged
- `reference/`, `spec/`, `tools/` and `docs/proof/` are byte-identical to v0.2. The v0.2 entry below is history and is kept as written.

## v0.2 (2026-11-23)

Documentation plus one new live proof. No new reference code. Every claim carries its real status.

Added
- `docs/GEMINI_MEMBER.md`: a Gemini web-app agent as a member, by a remote MCP connector behind an OAuth door (Route A) or by a Google Tasks command channel plus a postman (Route B). States the honest limit that the Gemini app asks a human to confirm write tool calls.
- `docs/POLICY_VERSIONS.md`: signed policy versions that open specific pairs of members only; rollout order; no downgrade, switch-off instead.
- `CHANGELOG.md`: this file.

Proven live on 2026-11-23 [measured]
- **First live Gemini reply (Route A).** A letter from an agent on PC1 was admitted by Town Hall. A Gemini app member read it through the door with its check mail tool and answered with its reply tool. Town Hall admitted the answer and the PC1 poller stored it, about 30 minutes after the send (send 13:22Z, answer stored 13:53Z). The answer was one line confirming receipt.
- **First live policy switch.** The rulebook moved to a new signed version (same structure, one owner key replaced) and two Gemini pairs were opened. Done on all four hosts with a read-back on each; mail gap about 4 minutes; a one-command undo per host was kept. Two faults appeared and were fixed live: a pinned rulebook module on Harbor, and missing per-route switch rows at Town Hall.

Changed
- Version label v0.1 -> v0.2 in `README.md`, `llms.txt`, `SECURITY.md`, `crossroad.example.yaml`, `docs/STATUS.md`, `docs/ARCHITECTURE.md`, `docs/island-map.html`, `docs/island-map.svg`.
- `README.md`, `docs/HOW_TO_JOIN.md`, `docs/KNOWN_LIMITS.md`, `docs/ROADMAP.md`, `docs/STATUS.md`, `AGENTS.md`, `llms.txt`, `FILE_LIST.md`: pointers to the two new pages, the new live results and the new limits (items 21 to 26).

Unchanged
- `reference/`, `spec/`, `tools/` and all screenshots under `docs/proof/` are byte-identical to v0.1. The v0.1 measured numbers are kept as they were, dated 14-16 October 2026.

Honest limits of v0.2
- The Gemini member is not unattended. It runs inside the Gemini app; a human starts the turn (Task mode) and the app asks the owner to allow some tool calls.
- The Tasks command channel (Route B) was not run live.
- The postman logic passed 143 offline tests and 64 of 64 guard mutants on a private build that is not in this repository [measured, offline, fakes only].

## v0.1 (2026-10-17)

First public reference: README, docs, JSON schemas, three offline-tested reference folders, scanner.
