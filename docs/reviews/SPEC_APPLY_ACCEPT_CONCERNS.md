# SPEC_APPLY_ACCEPT_CONCERNS (rev 1, 2026-11-21)

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
1. Where: ONE branch at `router/apply.py:141`, `pr.require_concerns_pair(...)` instead of `pr.require_ok(...)` when the flag is
   given. Never `try: require_ok / except Refused: pass` (that would accept `none`, `stale`, `error`, `one`). Every check after
   :141 stays as it is and runs with the flag: protected globs, empty patch, the example gate, .git and checkout checks, HEAD and
   `_recovered`, the domain chain, identity, clean tree, branch, worktree, HEAD, byte compare, modes.
2. `require_concerns_pair` (new, `router/patch_read.py`) takes the raw record, after `load`'s own validation, and requires:
   the record is for these exact bytes (not `stale`), a `second` reading exists, `_second_ok(second)` and not `_model_stale(second)`,
   both reader ids present and different (read from the raw first and second reading, not from the merged dict `load` returns,
   which overwrites `reader` with the second's), the `--reader` filter of `require_ok` (patch_read.py:240) applied too, and at
   least one of the two verdicts is `concerns`. Both `ok` is refused with "nothing to accept". A `concerns` from a
   `reader.kind` of `claude` is accepted like any other (the human's reason is what the flag records). A first reading of
   `concerns` is accepted only when `second` exists (`patch-read-run` always asks the second reader).
3. REASON: `t = ex.clean(reason, 10_000)`; refused (never truncated) when the raw text has a control character, when
   `len(t) < 10` or `> 500`, or when `stage_data.KEY` matches (a key must not reach git history: `job.save` scrubs, the commit
   message does not). It is validated in `apply()` BEFORE `open_job` and the lock, so a bad reason touches nothing. `ex.clean`
   alone (what `examples-accept` calls) is NOT the scrub: it cuts with "..." and has no minimum and no key check.
4. Record: no separate `job.note`. The acceptance goes in `extra` (`accepted_concerns` = reason, `accepted_findings` =
   `findings(rec)` of the check, `accepted_sha`), so `apply_started`, the APPLIED state entry (`_record_applied **extra`) and
   `_recovered` all carry it and a healed crash keeps it. `by` and `at` are already in the state entry. No reserved key
   names (job.py:1630). The findings are captured from the same `load` used for the check, never re-read later.
5. Commit message: the third `-m` argument gets `+ (f"\nAccepted-concerns: {reason}" if accept else "")`. A plain apply stays
   byte for byte as today (a test pins the exact message). The cleaned reason is one line and the `TRAILER` regex only matches
   `Argus-...` lines, so a reason cannot fake `Argus-Job`.
6. `argus status JOB` prints "applied with accepted concerns: REASON" from `_why(job)` only for a job that has it, through `clean`.
7. After a crash, a rerun without the flag is refused at :141 before `_recovered`; the rerun needs the flag and the same reason.
8. `--allow-failed-examples` and the domain reader's `examples-accept` are independent gates: both may be combined with the new
   flag and are recorded separately. The flag does not widen either.
9. CLI only: no chat route, no card button (a later, separate decision). `--help` says the reason is the human's words, quoted by
   the operator; a model never writes it.

## 4. Tests
`tests/test_apply_cmd.py`: concerns + reason applies and commits with the trailer and the log line; the same without the flag
refuses as today; empty, 9-character, 501-character and key-like reasons refuse and change nothing; `one`, `none`, `stale`,
`error` refuse with the flag; first `concerns` with a damaged or stale second refuses; first `ok` + second `concerns` with the
same reader id refuses; first `concerns` + valid second applies; both `ok` refuses "nothing to accept"; a reason with a control
character refuses; the flag on an APPLIED job refuses; the plain commit message is pinned byte for byte; a crash rerun needs the
flag; the flag with `--allow-failed-examples` records both; a sha of another patch refuses; protected files, a
failed example, a dirty tree, a moved HEAD and a missing domain reader's ok each still refuse WITH the flag; the log holds the
findings; status prints the line; the flag on a job already applied refuses. New helper in `tests/patch_read_util.py` that writes both readings (the existing `read_ok(verdict="concerns")` writes one). Mutants: the reviewer's 20, in `verification/accept_concerns_mutants.py`, run once after the build.

## 5. Not here
Per-finding severity (`blocker` / `nit`) in the reader, the card button, and any change to the readers' templates.
