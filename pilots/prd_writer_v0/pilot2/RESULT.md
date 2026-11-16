# PRD writer pilot 2 (argus-ledger), 2026-11-16

n = 1, kept apart from the scoreboard figure. First PRD of two ordered issues, from a wish **written by Atha** (`message.txt`, verbatim): per-job cost against the cap, a flag above 80% of the cap, one endpoint listing the jobs from the most expensive, filterable by week.

| Step | Job / queue | Result | Cost |
|---|---|---|---|
| PRD turn w1 (Haiku 5.5) | j20261116_102912_d678 | **WRITE_FAILED**: `context_limit` (input 3.5k -> 39.3k tokens, limit 40k) after 3 submits, all refused by the gate: two for a touch of 81 characters (limit 80, not written in the prompt), one for a full function signature used as a touch where item 1 had created a short name (exact match) | $0.0361 |
| Claude change (strict lane) | PR #577 | the prompt and schema now state the touch/creates limits (built from the gate's constants), and the "not found" refusal hints the string an earlier item creates; mutants 25/25, `verify_at` PASS 5437 | not metered |
| PRD turn w2 (`prd reply`, "Coba lagi dari awal...") | same job | WRITTEN, 2 issues, 2 submits (1 folder check), no clash | $0.0211 |
| Issue 1 (`budget_over_80`, `job_week` in `ledger/summary.py`) | j20261116_113425_efb9 | draft 16 red tests, agent 6 steps, APPLIED 0780f1e | $0.0129 |
| Issue 2 (`GET /budget/jobs`, README) | j20261116_113812_a8a8 | draft 8 red tests, agent 23 steps, APPLIED e008f98 | $0.0280 |

Total $0.0981 (PRD $0.0572, code $0.0409) of $1.50 (PRD) and $2.00 (queue). No retry, no redraft on either issue. Commits are on `argus-ledger` `main`, not pushed, not deployed.

**Evidence after apply:** `apply` ran the validations in the sandbox; Claude also called the new endpoint on the real jobs directory (66 jobs: HTTP 200, ranked by cost, top cost $0.4421 of a $1.0 cap, 0 jobs over 80%, `?week=2026-W46` 48 jobs, `?week=2026-W54` -> 400 `unknown week`). Not a full ledger suite run in the sandbox.

**Claude interventions (honest list, normal rules: Claude read, summarised and advised at every gate)**
1. Diagnosed the failed first turn from the run events and proposed the three options (retry, shrink, stop); Atha chose to raise the limits, Claude proposed the prompt/hint fix first (step 1 of 3) and built it (#577).
2. Typed the retry message `Coba lagi dari awal. Keinginannya masih sama seperti pesan pertama.` (`retry.txt`).
3. Read PRD, issues and drafts, verified their facts against the ledger code (entry keys, `usd_number_text`, ISO-week examples) and flagged: no percentage-used number, sorting by absolute cost not by share of the cap, endpoint not reachable through the viewer proxy, non-finite `max_usd` would raise in `Fraction`. Atha approved as is.
Zero interventions inside the queue itself (no reply, redraft, retry or fix on a job).

**What this pilot showed**
- The ordering rule (`creates` before `touches`) ran for real: issue 2 touches `budget_over_80` and `job_week`, created by issue 1, and the gate accepted it.
- The writer wrote a correct proxy declaration unprompted (`via_proxy: false` for the new path) and said in the PRD that the viewer proxy does not forward it.
- A PRD of this size on this repo did not fit one turn the first time: the context limit (40k, a price guard, not a model limit) was the binding stop, as Fable predicted; the cheap fix worked on the retry, but n = 1, and one more run could fail the same way.

**Not shown**
- Atha's minutes per gate and whether he read each patch to the end (not recorded; he said the full hands-off protocol was too heavy).
- That the endpoint serves what he wanted: two gaps stay (a percentage-used field; ranking by share of the cap) and the viewer cannot show it without a proxy change.
- Anything about three or more issues, about repos larger than ledger, or about the writer without a Claude-built fix in between.
