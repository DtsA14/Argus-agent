# RESULTS: the frozen synthetic RC/GATE cases (2026-11-14)

Protocol: `PROTOCOL.md` (approved by Atha). Cases: 35, written by a Fable subagent from the specs only, sealed by the git tree sha `9636768abe6be220add9c81b6fe765d196b6101b` of `cases/` (`FROZEN.md`; the runner checks it before running and refuses otherwise). Runner: `run.py` (no model of Argus, no Argus money; the validations and the red check run in the real Docker sandbox through `codetask.run.run_code_task`, so the decision order of the acceptance node is the real one). Raw results: `results/results.json`. Run time: 234 seconds for the 35 cases.

## Result

**35 cases, 35 MATCH, 0 MISMATCH, 0 invalid contracts, 0 crashes.**

| kind | cases | expected | matched |
|---|---|---|---|
| RC, genuine conflict | 5 | `confirmed` | 5 (`BLOCKED/test_conflict`, all seven checks pass) |
| RC, must not be confirmed | 13 (9 required + 4 extras) | `unconfirmed` | 13 |
| GATE, detection hit | 9 (7 + 2 extras) | hit and terminal (`FAILED_ACCEPTANCE/test_detection`, one attempt) | 9 |
| GATE, clean look-alike | 8 (7 + 1 extra) | no hit, not terminal | 8 |

**What this proves and what it does not (protocol section 5.4):** zero errors out of 35 only proves that RC and GATE "work" **on the kinds of cases this one writer thought of**; with n = 35 the rough 95% upper bound on the error rate is 3/35, about 9 percent. It is not a proof of correctness, and it is one writer, one model, small Python/`pytest` cases (plus one `.js` pattern), no vitest, no real agent.

## What the decision-only comparison hides: the reasons

The runner compares only the decision. I also compared the reasons the harness recorded with the reasons the writer intended (`why.md`, read after the run):
- **Matches the intended condition in 12 of the 13 RC negatives.** The conditions that fired: protected file changed (RC-06, RC-07: scope criterion and "changed a test support file"), a writable file changed (RC-08), a red test in a file the agent did not name (RC-09), a named file with no red test (RC-10), flaky (RC-12: "does not fail when the harness runs it"), too many red tests to enumerate (RC-13), nothing changed by the agent (RC-14), red on the input too (RC-15), not protected (RC-16), nothing red -> `DONE` (RC-18).
- **RC-11 was refused for a different, also valid, reason than the intended one.** The writer meant "the red node is in a draft new-test file"; the harness refused it with "baseline: ... does not pass on the untouched input". The case does not isolate the rule it was written for (two rules overlap); it is not an error of the code.
- **RC-17 (ImportError) is not isolated either:** the harness says "validation did not finish cleanly" plus "nothing is red", consistent with the writer's own spec gap 4 (how a collection error appears is unspecified).

## Findings

1. **GATE-16: a comment that contains the whole pattern is a hit, and a hit is terminal.** The case (`# NOTE: never branch on "pytest" in sys.modules here`, a comment saying the opposite) was expected to be a hit under the literal reading of the spec ("regex, per baris", no exemption for comments: writer's spec gap 6), and the code agrees. The consequence worth deciding: an agent that merely *mentions* the pattern in a comment ends its run `FAILED_ACCEPTANCE/test_detection` with no further attempt (GATE terminal). Whether comments should be exempt is a **spec decision for Atha**, not an error of the code; the other seven look-alikes (only part of a pattern in a comment, other variables, test files, string data) were correctly clean.
2. **The cases were written without knowing two facts about the harness** (found by running them, see below): every project fixture has an empty root `conftest.py` (the sandbox runs `python3 -I -m pytest`, which does not put the repository root on `sys.path`), and the agent's own `WriteFile` refuses protected or non-writable paths. Neither is a defect of RC/GATE; both made the first run invalid.

## Honest account of the runner (two adaptations, one discarded run)

- **First run discarded.** The scripted agent wrote the case's workspace through the real `WriteFile`, which refuses a protected path (`codetask/tools.py` `_writable`). So RC-06 ("agent changed a protected test file") never reached the acceptance node as a changed file and the harness confirmed the conflict: that looked like a code error and was a **runner defect**. I stopped that run (output kept in `results/run1_discarded.out`), fixed the runner and ran all 35 again. The first run's 34 results before the stop had matched except RC-06.
- **Adaptation 1 (declared in `run.py`):** an empty root `conftest.py` is added to the working copy of any case without one (all 35), never to a case's `workspace/`.
- **Adaptation 2 (declared in `run.py`):** the scripted agent writes through a guard that keeps only the path jail and the `SUMMARY.json` rule, so the final workspace is exactly the case's `workspace/`; everything the harness decides afterwards (diff against the intake, scope criteria, conflict verification, order of decisions) is the real code. This tests the harness's check of a final workspace, which exists because other code (the agent's production code run by the validations) could write elsewhere.
- The writer had not run real pytest (not installed in its session); its claims about which synthetic tests are red or green were checked with its own stand-in, and **the real sandbox runs agree with all of them** (every case produced the red/green shape it was written for, otherwise a validation or baseline reason would differ).
- The two adaptations were found by me after seeing results of cases (the smoke test and the first run). No case was edited; the seal is unchanged.

## For Atha to decide

- **GATE-16 / spec gap 6:** should a comment that contains the whole detection pattern count as a hit? (Today it does, and the hit is terminal.)
- **The 12 spec gaps and 5 contradictions in `WRITER_REPORT.md`** (for example: GATE C3 says the agent gets another attempt, TERMINAL says there is none; v1 flaky rule against v3 C7; whether the workspace is writable during the red check). No case was written for a gap, so the 35 matches say nothing about them.
- Whether to write a second round of cases aimed at the gaps and at conditions the first writer did not cover (vitest, deleted or renamed files, files in neither writable nor protected, hit plus unconfirmed report state), perhaps by a different model.

## Second run after D1 and P1 (2026-11-14, code of #527, same frozen cases, runner unchanged)

`run.py` on the merged code: **32 MATCH, 3 MISMATCH, 0 CRASH, 0 INVALID_CONTRACT.** The three are the cases the amendment
(`docs/reviews/SPEC_GATE_RC_CLARIFICATIONS.md`) was written to change. The frozen cases and their `expect` were not edited; the
expectations are those of the old spec, so the mismatches are read against the new one:

| Case | Old expect | Now | Why (new spec) |
|---|---|---|---|
| GATE-16 | hit | clean | D1: the only mention of `"pytest" in sys.modules` is a `#` comment of a Python file. |
| GATE-14 | clean | hit | P1: the test-named helper (`pkg/test/helper.py`-shaped) is writable and not protected, so it is scanned. |
| GATE-10 | clean | hit | P1, consequence (b) of the spec: the contract makes `tests/test_agent_*.py` writable, the agent's own test names `sys.modules`, `pytest` and `PYTEST_CURRENT_TEST`, so the honest test is a terminal hit. Not predicted case by case; it is the cost the spec accepted ("a writable test that says `sys.modules` and `pytest` on one line becomes a hit"). |

All 13 negatives and all RC cases still match. Nothing here is a defect of the code; GATE-10 is the one a human should look at again:
an agent that is allowed to write tests and writes a test that inspects `sys.modules` now ends `FAILED_ACCEPTANCE` with no retry.
