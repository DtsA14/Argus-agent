# SPEC_QUEUE_MONEY (rev 1, 2026-11-21)

Strict lane: the rule of a queue's money (`router/queue.py`, its mirror in `router/cards.py`) and the STOPPED card.

## 1. Problem (pilot ledger-browser, 2026-11-20)
A queue made from a PRD gets `max_usd` = issues x code cap (`router/prd_job.py:63-65`): the pilot's 3-issue queue had $3.00
(`q20261120T163639Z-6783`, `job_cap_usd` 1.0). It stopped at issue 3: "leaves $0.9769, one job needs $1.00". Held: 2 applied jobs
at their cap ($2.00) + two retired attempts at what they spent ($0.0117 + $0.0114). Real cost of everything: about $0.10. So with
the old rule EVERY PRD queue stops at its last item after one retry. Second problem: the STOPPED card tells the human nothing to
do (the steps are terminal commands the chat does not show).

## 2. Decision
A. The STOPPED card shows a next-step line per cause (section 3.A), built by the card's own `_derive` (the chat never calls
   `rq.derive`, which runs git, and `derive` gives no action for a money or HEAD stop anyway). No button.
B. `APPLIED` joins `SPENT_ONLY`: an applied job holds what it spent, as a retired REJECTED attempt does. It is terminal
   (`job.py:81`); a later `argus judge` on it spends under its own cap (`min(judge_max_usd, left_usd(job))`, `job.py:1289`).
   The judge's spend is COUNTED once it has happened (`spent_nano` adds every stage, judges included; the card's `_spent` too):
   no filter by stage kind is added. So `max_usd` bounds what the queue's own steps can start; a human's judge can add up to
   $0.30 per applied job on top (already true today for retired REJECTED jobs). The comment at the top of `queue.py` (lines 12-13,
   which promises "the total never passes max_usd" because of the judge) is rewritten to say exactly this.
C. (the "continue remaining issues" button) NOT built here. After B the pilot at item 3 holds $0.0231 + $0.0116 + $0.0088 = $0.0435
   of $3.00; a money stop needs more than $2.00 of finished spend, i.e. over about $0.22 per job across at most 9 jobs (3 items x 3
   attempts), and the pilot never came near that. The stops that remain need the terminal anyway. Revisit after a real one.

## 3. Rules
A. The next-step line, one fixed text per cause, ids and paths scrubbed and cut like the card's other lines:
   - money: no command raises a queue's money (`max_usd` is part of `list_sha`); close the queue and make a new one for the remaining issues, in the terminal;
   - REJECTED with retries left: `argus queue retry <q> --item n`, in the terminal, useful when the readers' concerns caused it;
   - REJECTED with none left: redo the issue from the PRD;
   - BLOCKED before the first stage, and every other state the card shows STOPPED for (DRAFT_FAILED, AGENT_FAILED, REVIEW_INVALID,
     ABANDONED, an unbound job, an APPLIED job whose commit was not recorded as the patch, an unreadable job): `argus status <job>`;
   - HEAD moved: the chat cannot see it; the card keeps saying HEAD is not checked.
B. `SPENT_ONLY = (ABANDONED, BLOCKED, REVIEW_INVALID, APPLIED)`; `committed_nano` (queue.py) and `_committed` (cards.py) both follow
   it. The queue reads the ledger (a missing `events.jsonl` counts 0, a cut-off call its worst case); the card reads `job.json`
   (a stage with no `usd` counts the whole cap, as today, and an APPLIED job with unknown spend counts its cap). Both sources are named
   in the comments. `QUEUE_MAX_USD` ($5.00), the per-job cap and `_next`'s refusal when one job does not fit stay.
   Comments and docstrings that say otherwise are fixed: `queue.py:1-13`, the `SPENT_ONLY` comment (line 43), `cards.py` `_committed`
   docstring and its line near 514, the `tests/test_queue.py` docstring.
C. Chat exposure (`chat_actions.exposure`) counts only issue and research jobs started from the UI at their caps; queue code jobs
   are made by `step` in the terminal and never enter it: B cannot make the two disagree.

## 4. Tests
`tests/test_queue.py`: line ~282-289 `(rj.APPLIED, True)` becomes `False`; `test_the_started_jobs_at_their_caps_never_pass_the_queue_money`
becomes "two APPLIED jobs hold what they spent and the third issue steps", plus a case where real spend fills the money so the stop
still exists; `test_the_money_fits_exactly` rewritten with a known spend; the pilot scenario with `max_usd` 3.0 (not 5.0) steps to
issue 3 after two applied and two retired; a judge stage on an APPLIED job raises the count once it exists.
`tests/test_chat_cards.py` (the card tests; there is no test_cards.py): line ~456 rewritten with stage `usd` set (WAITING) and a case
with no `usd` that counts the cap and stops; the card's count and `queue.py`'s count agree within 1,000 nano per stage on fixtures
(the card rounds `usd` to 6 decimals), exactly on fixtures whose `usd` matches the ledger; one STOPPED line test per cause above,
including the default line, scrubbed. `scripts/t3a_fixtures.py:116` (APPLIED fixtures) checked. Mutants: the reviewer's 18, in
`verification/queue_money_mutants.py`, run once after the build.
