# Proof

Masked screenshots from real runs, 15-16 October 2026 (UTC), on one installation (PC1, PC2, VPS1; VPS2 hosts Town Hall; VPS3 Harbor is planned, not installed).

## How to read these

- **Dark boxes** are masked private names, addresses and identifiers. Nothing under a dark box is hidden for effect; it is private.
- **The visible nonces and task titles are synthetic test identifiers** made for these runs.
- **These screenshots show UI responses and task status for narrower tests.** They are **not** proof of signed Town Hall admission, and **not** proof of full end-to-end delivery on the live path. The ChatGPT and Gemini items are test-tray or transport-only tests; see [../STATUS.md](../STATUS.md) and the NOT-proven sections of the reference READMEs.
- A screenshot can be staged or edited by a person. The measured counts in [../STATUS.md](../STATUS.md) are our own ledgers, not independently checked.
- **Grok: not connected yet. No screenshot, by design.**

## Container agent on VPS1, in Telegram

![A container agent on VPS1 answers a demo letter in its Telegram chat](telegram_app_1_agent_answers_demo.png)

**telegram_app_1_agent_answers_demo.png.** This is a container agent on VPS1 (member kind: container agent) that talks to its owner through Telegram and is woken by a scheduled doorbell job. It reports in its chat that it answered a short demo letter with exactly one reply line, and quotes that line. Shows the agent's own report of what it did. It does not show the signature, the route check or the ledger.

## Claude desktop

![The answer arrives in a Claude desktop session](claude_app_1_answer_arrives.png)

**claude_app_1_answer_arrives.png.** A Claude desktop session receives a post-office notice that the answer to its call has arrived. The notice wraps the answer text between peer-data marker lines, and the session then summarises it. Shows the receive side and the peer-data wrapping. The answer text is the same demo line as in the Telegram image.

## Codex desktop

![Mail wakes a Codex agent](codex_app_1_mail_wakes_agent.png)

**codex_app_1_mail_wakes_agent.png.** A letter arrives as a prompt in a Codex desktop thread and the agent starts working on it (the run is still in progress, "Thinking"). Shows the **wake-up only**, not the final reply. A Codex agent can receive and reply; it cannot start a letter yet ([../KNOWN_LIMITS.md](../KNOWN_LIMITS.md)).

## ChatGPT desktop and web

All three web images and the desktop image are from the **test tray** (a loopback lobby behind the vendor tunnel), not the live Town Hall path.

![A ChatGPT desktop chat creates the scheduled task and the task replies](chatgpt_app_1_scheduled_reply.png)

**chatgpt_app_1_scheduled_reply.png.** In the desktop app, the plugin is asked to create a one-time scheduled task. The chat then shows the task's result: one unanswered synthetic letter found, read and answered, status `reply_submitted`, with the nonce and reply masked. Shows one scheduled run's reported outcome.

![ChatGPT web: a reply that repeats the nonce](chatgpt_web_1_reply_with_nonce.png)

**chatgpt_web_1_reply_with_nonce.png.** In the web app, a chat-driven call checks mail, reads one synthetic letter and replies with a line that repeats its nonce (masked). Took 11 seconds. This is a person-prompted chat, not a scheduled run.

![ChatGPT web: the Scheduled page](chatgpt_web_2_scheduled.png)

**chatgpt_web_2_scheduled.png.** The Scheduled page lists one task as Completed with a last-run day. It **only shows that a schedule completed**; it does not show what the task did.

![ChatGPT web: the scheduled task result in its chat](chatgpt_web_3_scheduled_task_run.png)

**chatgpt_web_3_scheduled_task_run.png.** The same task in the web chat: created for 10 minutes ahead, then reported as completed with one letter answered (status `reply_submitted`). One run only; recurring schedules over days are not proven.

## Gemini web

All four Gemini images are **transport-only tests** through Google Tasks, not the live Town Hall path. **The Gemini scheduled run is on the Flash model:** the run view's model selector reads Flash. That selector does not independently attest which model executed the timer run, and the schedule cannot pin a stronger one. Nothing here is evidence of work by a stronger model.

![Gemini: the Scheduled list](gemini_web_1_scheduled.png)

**gemini_web_1_scheduled.png.** The Scheduled page lists four completed one-time tasks, each last run "1d ago", with synthetic test titles. Shows that schedules exist and completed.

![Gemini: a schedule's detail](gemini_web_2_schedule_detail.png)

**gemini_web_2_schedule_detail.png.** The detail panel of one control schedule: its plan text (read the open `Letter` task, create the matching `Answer` task, complete the letter), repeat Once, a fixed date and time. Shows what the schedule was told to do.

![Gemini: the timer run result](gemini_web_3_timer_run.png)

**gemini_web_3_timer_run.png.** The result of that scheduled run: the response itself reports that it created an `Answer` task in the default list and completed the `Letter` task, and that the one-time schedule has run to completion. This is the response's own report, not an independent view of task state. The model selector in this view shows **Flash**. This is the timer-run evidence for the Google Tasks transport only.

![Gemini: a one-time schedule being created](gemini_web_4_schedule_created.png)

**gemini_web_4_schedule_created.png.** A chat creates one one-time schedule without running it, and confirms title, time (partly masked) and plan. Shows how a schedule is created; the model selector again shows **Flash**.
