# FROZEN: the synthetic RC/GATE cases (2026-11-14)

The cases in `cases/` are frozen. **Git tree sha of `pilots/synthetic_rc_gate/cases`: `9636768abe6be220add9c81b6fe765d196b6101b`.** The runner must check that `git rev-parse HEAD:pilots/synthetic_rc_gate/cases` still gives this sha before it runs, and refuses to run otherwise. A case that turns out invalid is recorded as a spec gap in the results, never edited (PROTOCOL.md section 5).

35 cases: RC 18, GATE 17, written by a subagent (Fable) from the specs only; Claude checked only their form (`check_form.py`: 0 problems) and has not read their contents. Not yet run. The writer's own report, with 12 spec gaps and 5 contradictions between the specs, is in WRITER_REPORT.md.
