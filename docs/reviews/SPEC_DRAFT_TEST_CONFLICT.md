# SPEC_DRAFT_TEST_CONFLICT: the agent says the draft's own tests cannot pass (2026-11-22)

Found in the nexus-lite pilot (stage 3, `importSnapshot`): a drafted test could never pass (a call counter that was not reset). The agent
reported a conflict after 17 steps. Argus then started a second attempt on the same tests (30 steps, $0.11, about 14 minutes), and
`argus redraft` was refused for an AGENT_FAILED job, so the way out was abandon, close the queue and rewrite the PRD.

## What changes
1. **The run stops.** In `codetask/run.py` acceptance, a `ReportConflict` that is `unconfirmed` and names a test file that (a) the approved
   draft added or changed (the intake record) and (b) has a red node in the validations ends the run: FAILED_ACCEPTANCE, stop reason
   `draft_test_conflict: ...`. The test-detection gate keeps priority. A report on an old test, or on a draft test that is not red,
   goes on as before. Nodes beyond the listed 50 or a suite/import error give no red file and also go on as before.
2. **`argus redraft` is allowed for such a job** (new legal move AGENT_FAILED to DRAFTING). Any other AGENT_FAILED job is still refused (`retry` runs
   the agent again; `abandon` closes). A redraft of a job whose last agent stage stopped that way always carries the facts, also after a
   failed redraft.
3. **The note is built from the harness's record only**: the reported draft-test files, their failing nodes and the failure lines of those files from
   the last verdict. The agent's text is never kept (SPEC_REPORT_CONFLICT). The failure lines are test output and may hold text produced
   by the agent's code, so the drafter prompt calls them data, not instructions, and says the agent's claim was not checked. A human's `--note` follows the
   marker `Reviewer (human):`, is never cut, and marks the job human-steered too; the facts give way (at least 200 characters of the 1000), else the
   redraft is refused. The job is marked `conflict_steered`.
4. **Re-approval** publishes the new approved task as `task2`, `task3`... (an approval never overwrites), numbers the agent stage `a<n+1>`, and refuses
   a draft whose sha is the one already approved and run (it would run the same tests). `protected_changed` reads the record of the current
   approval. A task name is taken if any of its repository, record or contract exists (a cut-off approval).
5. **Status** offers `argus redraft` for this stop, with `retry` ("if you judge the tests right") and `abandon`.

## Not changed
The confirmed-conflict path (old tests, BLOCKED/test_conflict), `retry --not-a-conflict`, the budget caps, the drafter's gates.

## Tests and gates
`tests/test_report_conflict.py` (run level, job level, note facts, sizes, re-approval, task names, protected record, detection priority);
22 mutants (`verification/draft_test_conflict_mutants.py`); Opus review GO WITH CHANGES (findings 1 to 9 applied); precheck; `verify_at`.
