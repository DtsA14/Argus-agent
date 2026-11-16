# Steps (2026-11-16, Claude, "go live" Atha: "Push sekalian deploy")

`A` = `/home/ubuntu/Argus-agent/.venv-verify/bin/python /home/ubuntu/Argus-agent/scripts/argus.py`

| # | command | result |
|---|---|---|
| 0 | `$A stage status`; `docker ps` | live Stage 19 `j20261115_181548_0bc4-88c31e13e60f.up2`, monitor pass, one staging container (plus `argus-test-ledger-*`, not staging) |
| 1 | `$A stage check j20261116_113812_a8a8 --env ledger_py312_up2` | `stage check PASS: commit e008f982721f in ledger_py312_up2 sha256:3e48cd98c8de, 223 tests` (199 before; +16 +8 new) |
| 2 | `$A stage deploy j20261116_113812_a8a8 --runtime ledger_staging_up2 --yes` | exit 0; live `j20261116_113812_a8a8-e008f982721f.up2`, smoke pass 2026-11-16T12:11:19Z; rollback -> Stage 19 |
| 3 | `$A stage viewer-smoke` | exit 0, all ok through 8710 (`/api/summary` 157 jobs, evil host 421, listens 127.0.0.1:8710 only) |
| 4 | `stage monitor` run from `~/pilot3a_live` (lesson of Stage 19) | exit 0, `ok: true`, 157 jobs, release Stage 20 |
| 5 | `python pilots/staging_stage20/probe.py` (read only, through the release socket) | 14 checks ok on the 157 staging jobs: one item per job, costs add up to `/summary` `cost_nano` (8284146297 = 8284146297), sorted by cost then id, key order, `over_80_percent` exact, `?week=2026-W46` 32 jobs in the same order, `2026-W54`, `2026-44`, `2026-W5`, `abc` and empty week all 400 `unknown week`, evil Host 400 |
| 6 | `curl 127.0.0.1:8710/api/budget/jobs` | **404** (expected, regex `API`); `/api/scoreboard` and `/api/summary` 200 |
| 7 | `docker ps` | one staging container for the Stage 20 release |

**Answer to the wish on the staging data (157 jobs, all with a cap of $1.0):** the most expensive job is `j20261029_002951_8b7e` (ABANDONED, $0.3973), then `j20261022_193403_3beb` ($0.3937), `j20261029_002359_b9a1` ($0.3328); **0 jobs over 80% of their cap**.

State: ledger Stage 20 live and healthy. No page of the viewer uses `/budget/jobs`; reaching it through the proxy needs a change of the `API` regex (strict lane, proxy restart, its own "go live").
