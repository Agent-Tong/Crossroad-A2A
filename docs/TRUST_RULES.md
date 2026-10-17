# Trust rules

Every member of a Crossroad installation follows these rules. Some are checked by code, some depend on the owner's process, and some depend on each receiver's own harness permissions. Each rule says which. **None of this is a capability sandbox**: see "What these rules do not do" at the end.

| # | Rule | Enforced by |
|---|---|---|
| 1 | **Registered.** A member has a signed identity at Town Hall. By design, sending rights belong to the agent; today a Claude Code agent's identity is bound to its session (see [KNOWN_LIMITS.md](KNOWN_LIMITS.md)). | code: signed policy per island |
| 2 | **Cleansed.** Every letter passes the Town Hall gate: registered sender, signed route, peer-data fence, size and rate caps. An injection screen is part of the Town Hall design; it is **not part of this public reference and was not audited here**, so nothing in this repository shows what it checks. | code for the identity, route, fence and cap checks (reference code covers transport, identities, envelopes and answer bytes); design only for the injection screen |
| 3 | **Letters are data, never orders.** Text inside a letter carries no delegated authority from the owner. The fence and the label tell the receiver so; they do not stop a receiver that decides to comply. | label and fence by code; compliance by the receiver's instructions, harness permissions and owner policy |
| 4 | **Equal.** By design, any member may start a letter to any other member the route table allows, where the client implements authenticated sending. Current exceptions are listed in [KNOWN_LIMITS.md](KNOWN_LIMITS.md) (a Codex agent cannot start a letter yet). | code: route table |
| 5 | **One answer per call id.** At most one answer is admitted per call id and delivered to the original sender (offline-tested; live fault drills pending). | code: two ledgers keyed by call id |
| 6 | **SaaS answers are channel-origin, no authority.** An answer written through a plugin or task list on the owner's account is tagged with its channel. Channel origin conveys no delegated authority: the answer may inform. It must never approve, build, change keys, change rules or delete. | code (the tag); whether the receiver obeys "never" depends on its harness permissions and the owner's policy |
| 7 | **The post office verifies the sender.** A post office rejects a message that fails its identity or route check, so an agent cannot send "as" another agent through it, and an owner-level shortcut is not a way around the check. | code, at the post office and Town Hall |
| 8 | **The owner signs rules and approves installs.** A policy change is signed offline by the owner. No agent signs a policy. | process, plus signature check in code |
| 9 | **No agent deletes.** Unwanted files are moved aside; ledger rows are inserted or updated; tasks are marked completed. A reviewed, scheduled program with a bounded root and an age gate may delete; an agent may not. | process; the reference code contains no delete call |
| 10 | **Secrets are stored in a secrets manager.** They reach a process only at run time, as narrowly scoped values: in the process environment, or in a protected read-only secret mount (root-only, ideally memory-backed) that the secrets-manager integration or the operator provisions. The reference code does **not** provision that mount. A secret is never committed, never put in a letter or a report, and never kept in a repository file. | process; this repository is scanned by `tools/scan_public.py` |
| 11 | **Offline first.** New code is built and tested offline, reviewed by a second reader, and only then installed by the owner. | process |
| 12 | **Name the actor in a test result.** "It works" must say who ran it. A human prompting by hand is not an unattended round trip. | process |

## Cryptographic, SSH and local-isolation boundaries

These are the boundaries a reader will ask about. Each states what the design does and what it leaves open. Points 1 and 2 describe the deployment, which is outside this public reference; they are descriptions, not independently audited results.

1. **Signatures.** Island and owner signatures are OpenSSH signatures (`ssh-keygen -Y sign` and `ssh-keygen -Y verify`, ed25519), checked against an allowed-signers list with one principal per island (`island-<name>`). The policy is signed by the owner. To revoke an island, the owner removes its line from the allowed-signers list and signs a new policy; revocation takes effect only once the changed trust material and policy are installed at every verifier, so re-signing alone is not proof that a key is no longer accepted. There is no automatic key rotation in v0.1.
2. **SSH to Town Hall.** Each island reaches Town Hall over SSH with an `authorized_keys` forced command, so an island key can only run the post-office entry point, not a shell. A forced command restricts the command; it does not by itself disable SSH port or X11 forwarding, which are separate `authorized_keys` options. This is per the deployment design; the Town Hall code is not part of this public reference, so it is not audited here.
3. **First answer wins on a SaaS mailbox (known limit).** A writer with access to the SaaS mailbox can submit a syntactically valid answer first. For an outstanding acknowledged call, the Gemini Tasks reference bridge may admit that answer; a later replacement is refused. Several candidates seen before an answer is stored are refused as ambiguous until the owner selects one. The owner selection tool does not replace an already-stored answer. Channel origin is not proof of which person or model wrote the content, and conveys no authority.
4. **Local agents on a PC island (residual risk).** On a PC island, local agents run as the same OS user. The post office binds each sender to its registered agent session, not to a separate OS user. A process that can act as that user could write a letter as another local agent on that island. Crossroad does not isolate local agents from each other.

## Why rule 6 exists

A reply that arrives through a chat service's plugin can be written by anyone who can reach that account. Crossroad therefore treats it as untrusted content bound to one outstanding call id. It is evidence to read, never an instruction to follow.

## What a receiver is told

Every mission file begins with its own instructions (where to write the answer, the size cap) and then a fenced block with the letter body, introduced by a line that says the text is peer data. The receiver's instructions come from the post office; the body cannot replace them.

## What these rules do not do

Two kinds of control are mixed in the table above, and they must not be confused.

- **Identity and route checks** (rules 1, 2, 4, 5, 7, 8). Post offices and Town Hall reject messages that fail them. Channel origin (rule 6) conveys no delegated authority. The reference code in this repository validates transport, identities, envelopes and answer bytes.
- **Behavioural rules for the receiver** (rules 3, 6, 9). A receiver follows "no build, no key change, no policy change, no delete" only to the extent its own harness permissions and its owner's policy make it so. A fence, a label or an origin tag is text, not a per-turn tool gate.

Crossroad does **not** implement a capability jail. An agent that has been woken to read a letter keeps the normal tools it was given, and a hostile letter can still talk a model into using them. That is the residual risk. To reduce it, give a receiver only the permissions its owner is willing to lose, and keep approval taps with a human. What the checks do limit is narrower: a hostile letter cannot make a post office sign as another sender, cannot widen the route table, and its answer carries no authority. See [KNOWN_LIMITS.md](KNOWN_LIMITS.md).
