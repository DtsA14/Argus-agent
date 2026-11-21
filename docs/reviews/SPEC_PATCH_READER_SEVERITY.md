# SPEC_PATCH_READER_SEVERITY (rev 0, 2026-11-21)

Strict lane: it changes what lets `argus apply` through (`router/patch_read.py`, the template of the model reader, `router/apply.py` by way of `require_ok`).

## 1. Problem
The patch reader closes a patch on ANY `concerns`. Reader 2 (DeepSeek 1017) said `concerns` in 6 of 16 patches of the ledger-cli and
ledger-browser pilots, mostly on a corner the issue never mentioned (a "strict" date format the code accepts, quotes in a CSV, year 0-99);
hidden tests passed 22 of 22. Each re-read round costs 10-15 minutes, and a wrong finding goes to the next drafter, which wrote a test
for the wrong thing and dropped two right ones. `--accept-concerns` (#650) is the manual way past; this is the automatic one for the
harmless kind.

## 2. Decision
A. The model reader gives every `concerns` reading a severity: `blocker` (the patch is wrong against the issue, or breaks or writes something it should not: the
   defects of rules 2 (a)-(f) of the template) or `nit` (a corner the issue neither states nor implies, where the behaviour is defensible).
   One severity per reading: if ANY finding of the reading is a blocker, the reading is `blocker`.
B. A patch is closed (as today) unless every `concerns` reading of a complete pair is an explicit `nit`. Then the pair is `nit`: `apply` goes
   ahead like for `ok`, and the nits are recorded (log entry fields, status, card). A `concerns` without a severity, an unknown severity, a
   note written by a Claude session or an old note is a `blocker` (the safe default).
C. The nits do not go to a drafter: `queue retry` still needs a `concerns` (blocker) note.
D. Template: its rule 2 is anchored to the text of the issue ("judge against what the issue says; a behaviour the issue is silent on is a nit
   unless it breaks something that works"), and the reply format gains `severity`. `TEMPLATE_SHA256` changes: every earlier model reading is
   `stale` and is read again (about $0.007 a patch).
E. Guard before it ships: the planted-defect trial (`argus patch-trial`, 16 sets, both readers, cap $0.50 total) is run once with the new
   template; the template ships only if NO planted defect ends as `nit` (every defect set must still be `concerns` with a blocker by at least one reader).
   The result is written to `pilots/patch_reader_severity_v0/RESULT.md`. If one is missed the template is revised or this is not built.

## 3. Rules
1. Reply format: `{"verdict": ..., "note": ..., "severity": "blocker"|"nit"}`; `severity` is read only when `verdict` is `concerns` (a `severity` on
   an `ok` is ignored and not stored). `patch_trial.parse` (the one parser) accepts the key; two answers in a reply that disagree on verdict OR
   on severity are not an answer (as today for verdict).
2. Record: a reading (`record`, first and `second`) stores `severity` only for `concerns`; `load` validates it (`blocker`/`nit`, else the record is
   `error`); an absent value reads as `blocker`. `patch-read` (CLI, Claude readings) takes no `--severity`: a Claude note is a blocker.
3. `load` returns a new kind `nit` when both readings exist and are valid, by two different reader ids (the `ok` rule), at least one is `concerns`,
   and every `concerns` among them has `severity == "nit"` and `reader.kind == "argus"`. Everything else with a `concerns` stays `concerns`.
   The merge of a second `concerns` into the note (`load` today) must keep the blocker if either is a blocker; findings() lists nits and
   blockers with their labels.
4. Every caller of `load`: `require_ok` (apply) accepts `nit` like `ok`, with the `--reader` filter; the log of `apply_started` and the APPLIED entry carry
   `accepted_nits` (the findings); the commit message does NOT change; `approve_code` check (f) is ok for `nit` and its text says "ada catatan kecil (nit)" and
   shows them; `status` prints "patch read: nit ...: <notes>"; `patch_read_run` treats `nit` as final like `ok` (nothing is read again); `queue.retry` treats `nit` as "not rejected on
   concerns" (refused). The card shows the nits for Atha.
5. `--accept-concerns` on a `nit` patch: refused with "nothing to accept" (plain apply works), as for two `ok`.
6. The planted-defect fixtures and `verification/reader_tests.json` are bound to the template hash (`patch_trial`, `t3b`): the trial of 2E is the new record; tests that pin the old hash are updated.

## 4. Tests
`tests/test_patch_read.py`: record/load with severity (blocker, nit, absent, unknown -> error, severity on an ok ignored); `nit` only for a complete pair of two
argus readers with every concern a nit; one blocker among two concerns -> `concerns`; a Claude `concerns` -> `concerns`; first `nit` + second `ok` -> `nit`;
first `ok` + second `nit` -> `nit`. `tests/test_apply_cmd.py`: apply goes through on `nit`, records `accepted_nits`, the commit message is the plain one; a `blocker` refuses;
`--accept-concerns` on a `nit` refuses. `tests/test_patch_read_run.py`: scripted replies with severity, parse rejects disagreeing severity, `nit` ends the run. `queue retry` refuses on a nit note;
approve card f and status lines. Mutants in `verification/patch_reader_severity_mutants.py` once after the build.

## 5. Not here
Per-finding severity inside one reading (one note, one severity); the domain reader (numbers) has no severity; a chat button; any change of the second reader's model.
