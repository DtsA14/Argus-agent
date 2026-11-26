# SPEC_CHAT_MANAGER_P4: the next steps of a session, from the harness

Status: rev 0, 2026-11-26. Parent: `SPEC_CHAT_MANAGER.md` rev 1 section 3 item 3 and 13 items 12, 13; `SPEC_CHAT_MANAGER_P1..P3`. Atha 2026-11-26: "Ok p4". Strict lane (a new read of the audit file and a new field of a read route).

## 1. What it is

`GET /api/manager/<job>` gets `next_steps`: what the jobs this session started are doing and where the person goes next. The page shows it as a box "Next steps (from the harness, not the foreman)" above the conversation. Everything in it is the harness's: the sentence is one of four fixed ones in code, the state is read from the job's `job.json`, the money is the stages' recorded cost. No model text, no report text.

## 2. Which jobs

The jobs the chat's own audit says were confirmed from a proposal of this session: lines with `ok: "confirm"`, `action` in `research_new` / `prd_new`, `source_job` equal to the session, a job id of the UI shape. Read from the audit's last 1 MB, newest first, each job once, at most 10 (`NEXT_MAX`). A broken line, a missing job, a job of another kind, a missing audit are skipped, never an error. A typed form (no `source_job`), a prepare line and another session's job are not steps.

## 3. The four sentences (the hint is a code, not an action)

research `REPORT_READY`: hint `research`, "The research is done. Read the report in the Research view." PRD `AWAITING_HUMAN`: hint `queue`, "The PRD is written and waits in the Queue tab. Accepting its plan and running the queue are two separate confirmations of yours; nothing runs by itself." (13.12: PRD and queue steps are pointers only.) A state matching FAILED, ABANDONED, REJECTED, INVALID, BLOCKED or STOPPED: hint `none`, "This <kind> job ended: <STATE>." Any other: hint `wait`, "This <kind> job is still going: <STATE>." A state that is not `[A-Z][A-Z_]{0,39}` is shown as UNKNOWN. Each item is exactly `{job, kind, state, usd, hint, text}`.

Differences from the parent, stated: 13.12 says a PRD step is a terminal hint (`argus prd check <folder>`); the folder is not in what the chat reads, so the hint points to the Queue tab, where the plan card is. Queue `WAITING` / `STOPPED` (3.3) are not covered: the steps are the research and PRD jobs this session started, and a queue is not one of them. A negative or non-finite recorded cost shows no figure. One job.json that cannot be read (a number too large, bad JSON) costs its own item only.

## 4. The page

Each item: a bold line "Research/PRD · STATE · $cost:" and its sentence as text. `research`: a button "Open the report" (`setMode("research")`, then `showResearch(job)`); `queue`: "Open the Queue tab" (`setMode("cards")`). The buttons only move the person: the box posts and prepares nothing. The 30 s poll of the foreman view refreshes it.

## 5. What P4 does not do (a narrowing of 3.3, stated)

3.3 also says the foreman's next turn receives this summary and may propose a follow-up route. That is not built: the link from a started job to its session exists only in the chat's audit, not in the job directory, and the foreman's turn runs as `argus manager turn` with a fixed argv and a context made by the CLI from the session alone (P1 section 10). Giving the model the summary needs either a source marker written into the started job (a change to `research new` / `prd new`) or an extra input of the turn route; both reopen P1's rules and are left as P4b, to be decided with Atha. `plan_model` (13.13) is not needed by P4 and is not added.

## 6. Tests and mutants

`tests/test_chat_manager_next.py` (server), the node smoke and static tests of `test_chat_manager_ui.py`. Mutants (written, run once after review): M1 any `ok` accepted (a prepare line counts); M2 another session's job counts; M3 a typed form counts; M4 an action other than research/prd counts; M5 a job of another kind counts; M6 no limit of 10; M7 a job listed twice; M8 oldest first; M9 a state not checked against the shape; M10 REPORT_READY maps to `wait`; M11 AWAITING_HUMAN maps to `wait`; M12 an ended state maps to `wait`; M13 the model's or the report's text in the item; M14 an item has an extra key; M15 a bad audit line raises; M16 the box posts or prepares; M17 the report button does not move to research; M18 the queue button does not move to cards; M19 the money shown as a number when it is not finite; M20 the box shown with no items; M21 `next_steps` missing from the read route.
