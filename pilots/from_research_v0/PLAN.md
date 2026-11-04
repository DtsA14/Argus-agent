# Pilot from_research v0 (SPEC_FROM_RESEARCH §9.4, replaced): issue 015 on argus-ledger

Atha "Ok gas" (2026-11-04) for this plan, after review notes from another session (answer key checked in the env, a
hidden grader written first, a neutral research question, arm B before arm A). One "go live" covers the steps below.
Stop at the first deviation.

Answer key, checked in `ledger_py312_up1` (starlette 1.8.0): `GZipMiddleware(..., *, exclude_content_types=...)`,
`DEFAULT_EXCLUDED_CONTENT_TYPES` (14 types) importable from `starlette.middleware.gzip`; the response media type is
matched without its parameters (`text/csv; charset=utf-8` matches `text/csv`). Correct: the defaults plus `text/csv`.
Wrong but CSV-passing: `("text/csv",)` alone (drops the defaults), `text/*` (stops gzipping HTML).

Hidden grader (scratchpad `grade015/`, never given to an agent): 18 tests (CSV not gzipped and plain; JSON and HTML
still gzipped; small bodies as before; each of the 14 default types still excluded) plus a static check of the patch
(no Content-Encoding, own middleware, or hand compression). Validated: base fails only the CSV test; the correct patch
passes; `("text/csv",)` fails the 14 default tests; `text/*` fails the HTML test; a Content-Encoding dodge is flagged.

Steps (sequential, each job `--max-usd 1.00`; stop when the batch passes $1.50):
1. Arm B: `argus code --repo ~/argus-ledger --commit 1f31e34 --issue-file 015-csv-not-gzipped.txt --environment
   ledger_py312_up1`. Claude reviews and approves the draft as usual, before seeing anything of arm A.
2. Research: `argus research --profile deepinfra --question-file 015-research-question.txt` (neutral question).
3. Arm A: as step 1 with `--from-research <step 2 job>`.
4. Grade both patches with the hidden grader; apply the better one to argus-ledger (no staging deploy here).

Measured: grader result per arm, redrafts/retries, cost per arm (research counted in A), Claude's decisions. n = 1
per arm: an anecdote, not evidence. The research job also runs with the new e1 output cap (32k); if it fails, its
check.json and e1 events say whether the cause was the output cap or the question.
