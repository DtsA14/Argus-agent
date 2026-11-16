# Deploy argus-ledger Stage 20 (`GET /budget/jobs`, issues of the PRD pilot 2) to staging

**"Go live" Atha 2026-11-16 ("Push sekalian deploy")**, given in chat before the steps; this file was written right after the run, from the commands and outputs in `steps.md` (the procedure is that of `pilots/staging_stage19/PLAN.md`: one step = one command, stop at the first step that does not match, staging only, no model, port 8000 untouched, proxy and monitor units not changed).

Deployed job: `j20261116_113812_a8a8` (issue 2 of `pilots/prd_writer_v0/pilot2`, ledger commit `e008f982721f`, with issue 1 `0780f1e` under it, on top of Stage 19 `88c31e1`). Release `j20261116_113812_a8a8-e008f982721f.up2` on runtime `ledger_staging_up2`. Viewer unchanged.

**Push:** not done, and not possible: `~/argus-ledger` has no remote (`git remote -v` is empty, no upstream). The repository is local only.

**Known hidden dependency (not part of this plan):** the viewer proxy forwards only the paths of its `API` regex (`router/stage_viewer.py:76`), so `/api/budget/jobs` is 404 through port 8710 (the same class as `/api/scoreboard/models` at Stage 19). The PRD named it (`via_proxy: false`).

Rollback (needs its own "go live"): `$A stage rollback --yes` (ledger -> Stage 19 `j20261115_181548_0bc4-88c31e13e60f.up2`).
