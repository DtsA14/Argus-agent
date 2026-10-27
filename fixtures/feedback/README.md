Real `evidence.output_tail` values of a failing validation (`validation:inspectors`), copied unchanged from the verdicts of the
M6 pilot 3a live runs, for the tests of the error excerpt in the feedback between attempts (`tests/test_feedback_excerpt.py`).

- `pilot3a_verdict_0_inspectors_tail.txt`: `runs/pilot3a/verdict_0.json` (also in `pilots/m6_pilot3/3a/evidence/live/`).
- `pilot3a2_verdict_1_inspectors_tail.txt`: `runs/pilot3a2/verdict_1.json`. Its first lines are the end of a block cut by the
  2,000-character tail: the case that broke "take the first `E ` block".
- `swe_21379_verdict_0_target_tail.txt`: `validation:target` of SWE batch 3 `sympy__sympy-21379`, job `j20261027_151552_7cdd`
  stage `a1`, `verdict_0.json` (`pilots/swe_v0/batch3/`). The fix is at `sympy/core/mod.py:169`, a caller frame without `E `
  lines: the case for the call path in the excerpt (`tests/test_locate_from_traceback.py`, SPEC_LOCATE_FROM_TRACEBACK).
- `swe_21379_rerun_d1_baseline.json` and `swe_21379_batch3_d1_baseline.json`: the draft scope and the failing baseline (status,
  red check, output tail) of the drafter checks of `21379`'s re-run (job `j20261027_175610_34ba`, draft rejected) and of batch 3
  (job `j20261027_151552_7cdd`). The first keeps the exception and loses its traceback; the second chains it, and its call path
  outside writable starts at `sympy/core/mod.py:169` (`tests/test_draft_call_path.py`, SPEC_DRAFT_CALL_PATH).
