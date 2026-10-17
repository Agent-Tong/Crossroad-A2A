# Known limits

Honest list, most important first. Evidence class in brackets: **measured**, **inferred**, **assumed**.

## Identity and authority

1. **Identity belongs to a chat session for Claude Code agents.** Every session restart orphans the signed binding until the owner re-signs it. This is the most frequent manual step. [measured: it happened on 2026-10-15]
2. **SaaS answers are "channel-origin".** They were written through a plugin or task list on the owner's account. Anyone inside that account can write one. Crossroad gives them no authority, but it cannot prove who wrote them. [design]
3. **A Codex agent cannot start a letter.** The sender needs a Claude session id; a Codex thread has none. The routes already allow it; the block is identity, not permission. [measured]
4. **A ChatGPT plugin trusts the tool's own annotations** when deciding what is "low-risk" and may run without a click. Any tool we label non-destructive can run unattended, so `send_mail` stays off in the lobby until reviewed. [inferred from one run]

## Reliability

5. **Latency is minutes.** Median 274 s for Claude Code agents, p90 2,954 s. Agents are woken, not kept running. SaaS agents are bound by their own timers (about hourly for Gemini). [measured]
6. **PC1 is not always on.** Mail for its agents waits while it sleeps. [measured]
7. **Install-day drift.** A member change touches policy, pins, scope and bridge code on several hosts. If one copy lags, letters for existing members can be refused, and after the new rules switch on the old bridge cannot come back (one-way door). [measured in offline simulations: of 24 install orders, 10 were unsafe]
8. **Lost acknowledgements.** A SaaS reply can succeed remotely while the local side sees an error. Blind retries duplicate; no retry strands. The reference code stores bytes before every external call and replays them, and has offline tests for it, but live crash and 503-after-success drills are **not yet run**.
9. **A container agent can stay silent on a real mission** if its own rules call it "old or already handled". One case happened; a permanent fix is proposed, not done. [measured once]
10. **One island's bridge logged 20,627 refused exports against 266 successful ones**, and four letters are stuck. Cause not yet found. [measured]
11. **A bridge re-logged a "sent" receipt for the same delivered calls every minute** (about 4 MB a day, no resend). A fix exists offline. [measured; fix not installed]

## Services we depend on

12. **Gemini scheduled runs use a cheap model**, and the schedule has no model field. A stronger model is not proven to run inside a schedule. [measured]
13. **The Google app is in "Testing".** Its refresh token expires every 7 days, so the owner re-consents weekly until the app can go to production. [vendor documentation]
14. **Gemini may not write the strict fenced answer.** The first live answer was refused for format. The instruction now asks for the fence in words and by example; whether the model obeys it on a real timer is **not proven**.
15. **Vendor and model drift.** Tunnel authentication, plugin permission pages, scheduled-task behaviour and model names change without notice. Pin the tunnel client binary and re-check after each vendor update. [assumed]
16. **Small VPS.** VPS1 is small and has no swap. A tunnel reconnect storm or a leak could squeeze an existing agent first. Harbor is planned with hard memory, CPU and process caps. [measured; effect inferred]

## About this repository

17. **The reference code has only run against stand-ins.** Tests use fake Google Tasks, a model mail port and a hand-played bridge. Real Docker restarts, namespace rejoin, a real Town Hall and real SaaS services were not exercised by these suites.
18. **Reference tests are smaller than the private ones.** Suites that needed installed (non-public) release files were left out. See each folder's README.
19. **One organisation, one installation, one owner.** No second installation has ever run this code.
20. **A hostile letter can still talk a model into something unwise.** The design limits what such a letter can reach; it does not make a model immune. See [TRUST_RULES.md](TRUST_RULES.md).
