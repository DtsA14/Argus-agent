# ledger-cli pilot: the first repo Argus builds from a scaffold (2026-11-19)

Why: Atha wants T6 (new repos from a prompt) fast and real use instead of more gates (AGENTS.md, "Proportional process and real use first"). This
pilot is the first real task, chosen because its result is objective: a CSV expense analyzer with numbers that can be computed by hand.
This file is the living record of the pilot. Update it as the pilot goes; keep it factual.

## Setup (what was done by hand, and is what `argus env init` / T6 should automate)
| Step | What | Where |
|---|---|---|
| Scaffold | package `src/ledger_cli`, one passing test, `pyproject.toml` with pytest `pythonpath`, README, `.gitignore`; one commit | `~/ledger-cli` (local, not pushed) |
| Registration | one line in `issue_writer.repos` (`ledger-cli`, environment `ledger_py312`, reused image: Python 3.12 + pytest) | `config.yaml`, PR #631 |
| Environment | no new image: the stdlib-only project reuses `ledger_py312` | `.sandbox_image_ledger_py312` pins already in `pilot3a_live` |
| Request | Atha's spec (CSV format, rules, command contract, JSON shape, exit codes) in Indonesian, 2,358 characters | `~/ledger_request.txt` |
| Hidden tests | 12 acceptance tests and 7 CSV fixtures, written from hand-computed numbers BEFORE Argus started, outside the repo; they use only the command contract | `~/ledger_eval/`, hash of fixtures + tests `d1c1d01e20c0901bbfb618b4c39d145fb7968d78d8e6ce2356fdfa64068dc7e8` |

The hidden tests were first run against a small reference implementation of mine (12 passed) to check the tests themselves, then the reference was deleted.
Run them at the end with `LEDGER_REPO=~/ledger-cli pytest ~/ledger_eval/test_ledger_cli_acceptance.py`. They are written by Claude: a smoke test of the
cases Claude thought of, not proof of correctness.

## What is measured (agreed with Atha)
Product verdict (separate from process verdict): hidden tests passed, with a comment on the structure.
Process: issues that reach APPLIED; operator steps typed by Claude (log below); total money; times Atha was confused by a card; Atha tries the tool himself.

## Operator log (every command Claude typed; Atha's gates marked)
Kept in `~/ledger_ops.log` while the pilot runs; summarized here at the end. First 17 lines (2026-11-19):
`prd new`, `prd check`, `prd approve` (Atha), `queue go`, `queue step`, `approve` draft (Atha), `patch-read-run`, `apply` (Atha), `queue step`
(blocked by the example gate), `prd reply --rebase`, `queue close`, `prd reply` again, `prd check`, `prd approve` and `queue go` for the rewritten PRD (Atha), `queue step`.

## Frictions found (each is a candidate for T5/T6, in the order met)
1. **The plan card shows the whole request as one paragraph** (newlines lost, 2,358 characters): Atha: "No.1 nya terlalu panjang". Fix: cut with "selengkapnya", keep line breaks (display only).
2. **Issue 1 of a new repo has no runnable example** (the module does not exist yet; the writer says so). The install card is closed by condition (h) "ada contoh perilaku baru"; (a), (b), (i) do not apply; scope is not compared (no code anchors). `apply` still worked on Atha's word. Needs a clear "no example by design" statement the card accepts.
3. **The PRD writer cannot run the examples of items 2..n** (the code they use does not exist yet), so a malformed example is found only when the job starts: the example gate refused `e2` of item 2 because its setup was not imports of a repo module; no model was called, no money spent. Recovery cost: `prd reply --rebase`, a new folder, a new queue, a new approval.
4. **`prd reply` is refused while the old queue is not closed** ("two queues would race for the same HEAD"); `queue close` first.
5. **The agent stored `Transaction.date` as a `datetime.date`** while the PRD contract said text; the rewritten PRD was adapted to the code. Not harmful here, but a PRD contract that the first issue silently changes is a risk for later issues.
6. About 17 commands for 1 issue and a rewrite; about 3 to 5 minutes of machine time per issue, the rest is waiting for a human step.

## Money so far
PRD writer w1 $0.0287, w2 $0.0236; issue 1: draft $0.0084, agent $0.0025, patch readers $0.007 (Hy4 Flash then DeepSeek 1017: first use of the tested pair on a real job).

## Status
Issue 1 (read and validate CSV): APPLIED at `5e0484c`. Queue 1 closed. Rewritten PRD (4 issues: summarize, build_report, filter_range, report command) approved by Atha;
queue `q20261119T144437Z-2814`. To be updated as the issues finish.
