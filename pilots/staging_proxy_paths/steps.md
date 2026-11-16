# Go live: the proxy forwards `/api/scoreboard/models` and `/api/budget/jobs` (2026-11-16, way A, "Ok A dulu")

Code: PR #580 (`SPEC_PROXY_LEDGER_PATHS` rev 2, merge `e2ee6c0dead19b730837cd274c669bb9844b5e8c`). "Go live": Atha 2026-11-16 ("Ok go live juga", then "Ok A dulu"). Staging only, no model, no money.

Way A (only the proxy): `~/pilot3a_live` stays at `6061247a2cc21edf2dc9e91a68263d759a68b64b` (36 commits behind `main`); one file taken from the merge commit; `argus-chat` (8711) not touched.

| # | command | result |
|---|---|---|
| 0 | quiet minute (:09, monitor ticks at :00/:15/:30/:45), `git rev-parse HEAD`, `git status`, `ps` | HEAD `6061247`, clean tree, only `stage proxy` (pid 1248) and `chat serve` (pid 2283447) running from the checkout |
| 1 | `git -C ~/pilot3a_live checkout e2ee6c0... -- router/stage_viewer.py` | one staged file, 3 insertions, 3 deletions (the regex and the docstring) |
| 2 | `systemctl --user restart argus-stage-proxy.service`; 3 s; `is-active`; `NRestarts` | `active`, `NRestarts=0`, `running`; `/api/summary` 200 |
| 3 | curl through 127.0.0.1:8710 | `/api/summary` 200, `/api/scoreboard` 200, **`/api/budget/jobs` 200 (0.10 s), `/api/scoreboard/models` 200 (0.09 s)**, `/api/jobs` 200; `?week=2026-W46` 404, `?kind=code` 404, `/api/budget` 404 (as specified) |
| 4 | `stage viewer-smoke` (from `~/pilot3a_live`) | exit 0, all ok |
| 5 | `stage monitor` (from `~/pilot3a_live`) | exit 0, `ok: true`, 157 jobs, ledger release Stage 20 |

State left behind: `~/pilot3a_live` has **one staged file** (`router/stage_viewer.py`, equal to the one in `e2ee6c0`) and is otherwise at `6061247`. A later full update should be `git -C ~/pilot3a_live merge --ff-only <sha>`; because the staged file equals the incoming version it is expected to go through, and if git refuses, `git -C ~/pilot3a_live reset -q -- router/stage_viewer.py && git -C ~/pilot3a_live checkout -- router/stage_viewer.py` first (not tried).

Rollback (proxy only): `git -C ~/pilot3a_live checkout 6061247a2cc21edf2dc9e91a68263d759a68b64b -- router/stage_viewer.py`, `systemctl --user restart argus-stage-proxy.service`, `curl 127.0.0.1:8710/api/summary` 200. Not run.

What the viewer cannot do yet: no page of the viewer uses the two paths (JSON in the browser through the SSH forward), and the proxy forwards no query, so the week filter is not reachable through port 8710.
