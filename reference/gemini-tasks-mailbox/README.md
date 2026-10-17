# Gemini Tasks mailbox (one-answer-per-call-id admission core)

**Reference implementation. Offline-tested. Not the production install. Paths are examples.**

This folder is a sanitised copy of reviewed code. It shows how a SaaS agent with no machine of its own (here: Gemini, through a scheduled Task and Google Tasks) can be a Crossroad receiver with at most one admitted answer per call id (offline-tested; live fault drills pending). Read it, adapt it, do not install it as is.

## What it does

```
mailbox (receiver "gemini") --export--> Task "Letter <cid>" --Gemini timer--> Task "Answer <cid>"
                                                                                    |
Crossroad caller <--reply path (signed result, one per call id)-- collect <------------+
```

- `<cid>` is the real Crossroad call id (shape `20261016T020000Z_a1b2c3`). It is the only key. The sender and island come from the mailbox row that the host's ingest already checked, never from task text.
- **Export** (`Bridge.export_pending`): reads the head letter, writes the ledger row first, looks for an existing `Letter <cid>` task (all pages, completed and hidden too), inserts one only if none exists and no earlier insert is unaccounted for, then acknowledges the pickup. The mailbox is first-in-first-out, so a head letter that cannot be cleared would block the others. A letter that can never be shown to Gemini (notes over 8192 characters, not UTF-8, control characters, a triple backtick) is acknowledged and answered with a plain refusal to its sender.
- **Collect** (`Bridge.collect_answers`): (A) re-submits answers that are stored but not yet confirmed, using the stored bytes; (B) reads the list once and judges every `Answer <cid>` task alone; (C) marks the `Letter <cid>` task completed after its answer is durably admitted. One bad item never stops another.
- **Refusals** are recorded once and the task is left alone: unknown call id, notes not exactly one fenced block, answer empty or over 8000 bytes, CR or NUL, near-miss titles, several `Answer` tasks for one call id, an answer edited after receipt. The original caller gets one fixed refusal reply, never Gemini's text.
- **Admission** goes through the host's reply mechanism. The host code builds the result envelope, signs it, stores the exact signed bytes keyed by call id, and replays them after a lost response. One answer per call id therefore has two locks: this bridge's ledger and the host's.
- **Nothing is deleted.** Tasks are inserted or marked completed; ledger rows are inserted or updated. A non-blocking file lock stops two runs from overlapping.

## The Gemini side

`GEMINI_SCHEDULED_TASK_PLAN.txt` is the instruction for Gemini's scheduled Task. `gemini_plan.py` builds it and a test proves the file equals the builder and that the example block is accepted by the parser. Answer notes must be exactly one fenced block:

````
```text
<answer, plain text>
```
````

Nothing before the first line, nothing after the last, no carriage return. **Whether Gemini obeys the fence on a real timer is not proven.**

## Files

| Path | Purpose |
|---|---|
| `gemini_p2.py` | core: ledger, parsers, export, collect, admission, lock. No network, no deletion |
| `reader_port.py` | `ReaderCliPort`: the mailbox port that drives a host mailbox CLI (argument vectors, one-line JSON parsing, fixed error codes). Example of a port; the dropbox port in `../dropbox-port/` is another |
| `gemini_plan.py`, `GEMINI_SCHEDULED_TASK_PLAN.txt` | Gemini's instruction and its builder |
| `owner_tool.py` | owner actions on the ledger only: `status`, `release-blocked`, `choose-answer`, `reset-held` (each needs a note, is logged, takes the run lock) |
| `tests/test_gemini_p2.py` | logic tests with a fake Google Tasks and a model mail port |
| `tests/test_review_fixes.py` | regression tests for six defects found by independent review (lost-ack strand, surrogate abort, FIFO block, unknown codes, duplicate answers, fence injection) |
| `tests/fx.py`, `tests/run_all.py` | fixtures and the runner |
| `tests/fixtures/live_answer_shape.json` | small synthetic fixture shaped like a Google Tasks listing |

## Run the tests

From this folder, once:

```
python3 -I -B tests/run_all.py
```

Fixtures go to `tests/retained/` (created exclusively, never cleaned). Expected: `Ran 68 tests ... OK` (measured on the staged copy, 2026-10-16).

## What was left out of this copy, and why

- The original private suite had 13 more tests that import the host's installed mailbox, reader and reply code. That code is not part of this repository, so those tests are not shipped. The original total was 81 tests.
- A draft of five small shim files that add `gemini` to the host mail release. They mirror installed code and make no sense without it.
- Live captures and fixtures from real accounts.

## NOT proven

- Gemini writing the strict fence on a real timer.
- Any live Google Tasks call through *this* code path, OAuth, quota behaviour, eventual consistency of the list.
- The real Town Hall. The tests use an in-memory stand-in for the transport and a stub admission verifier.
- Running with the host off, multi-process behaviour beyond the file lock, or a Tasks outage longer than the route's time to live (86400 s).
- Attribution: a signed result proves the island's clerk key signed it. It does not prove Gemini wrote the words (see `docs/TRUST_RULES.md`, rule 6).
