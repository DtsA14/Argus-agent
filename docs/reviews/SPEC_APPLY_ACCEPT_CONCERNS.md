# SPEC_APPLY_ACCEPT_CONCERNS (rev 0, 2026-11-21)

Strict lane: it touches the apply gate (`router/apply.py`, `router/patch_read.py`).

## 1. Problem
`argus apply` needs an `ok` of two readers for the patch's exact bytes. Reader 2 (DeepSeek 1017) answers `concerns` in 6 of 16
patches of the ledger-cli and ledger-browser pilots, mostly on a corner or on a detail that is not a defect (the last one:
tests in a new file instead of the file the issue named; the code was right and 32 tests passed). The only way past it today
is `git apply` by hand and `argus applied JOB --commit SHA --note`, which skips every check apply makes (sandbox result,
protected files, clean tree, HEAD, the domain reader) and leaves no record that the readers objected.

## 2. Decision
`argus apply JOB --read-sha SHA --accept-concerns "REASON"` applies a patch whose readings hold a concern, through the SAME
checks as a plain apply, and records the acceptance. Nothing else about apply changes.

## 3. Rules
1. Allowed only when the patch-read record is fresh for these exact bytes, BOTH readers gave a usable reading (reader 1 and
   reader 2 ran), and at least one verdict is `concerns`. Other kinds (`none`, `stale`, `error`, `one`) keep their refusals:
   a missing or half reading is not a concern to accept. When reader 1 said `concerns`, reader 2 never ran: refused with the
   hint to run the second reading or to retry.
2. REASON is the human's, 10 to 500 characters after normalisation, with no key-like string or control character (the same
   scrub `examples-accept` uses). It is required; an empty or missing one is refused before anything is touched.
3. Every other check of `_apply` runs unchanged and before the commit: review package valid and sha, the protected globs,
   the example gate, the domain reader (it has its own `examples-accept`, not widened here), clean tree, HEAD, the lock.
4. The record: `job.log` gets `accepted_concerns` with the reason, the findings text of each reader (as `findings(rec)`
   gives them), the patch sha, the time and `$USER`. The commit message gets one trailer line, `Accepted-concerns: REASON`.
   `argus status JOB` prints "applied with accepted concerns: REASON".
5. The flag changes nothing when the readings are both `ok`: then it is refused with "nothing to accept" (as `examples-accept`
   does), so the trailer never claims a concern that was not there.
6. CLI only. No chat route and no card button in this PR (a phone button is a later, separate decision).
7. A model never supplies REASON: the operator quotes the human's words. The `--help` text says so.

## 4. Tests
`tests/test_apply_cmd.py`: concerns + reason applies and commits with the trailer and the log line; the same without the flag
refuses as today; empty, 9-character, 501-character and key-like reasons refuse and change nothing; `one`, `none`, `stale`,
`error` refuse with the flag; both `ok` refuses "nothing to accept"; a sha of another patch refuses; protected files, a
failed example, a dirty tree, a moved HEAD and a missing domain reader's ok each still refuse WITH the flag; the log holds the
findings; status prints the line; the flag on a job already applied refuses. Mutants list in `verification/` written, run once after review.

## 5. Not here
Per-finding severity (`blocker` / `nit`) in the reader, the card button, and any change to the readers' templates.
