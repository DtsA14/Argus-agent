# Deploy Stage 13 / issue 015 ke staging: hasil (2026-11-04)

Rencana: `PLAN.md`. Dua "go live" Atha: yang pertama berhenti di langkah 1 (revisi 1: job ada di `~/pilot3a_live`, bukan
`~/Argus-agent`; staging tidak berubah, log `r0_*`), yang kedua menjalankan revisi 1 dari `~/pilot3a_live` (main be2c306).

| # | hasil | log |
|---|---|---|
| 0 | live `j20261030_060939_8433-1f31e34c1ff2.up1`, monitor pass | `step0_status.log` |
| 1 | `stage check PASS: commit 4e947a0ffe8b in ledger_py312_up1 sha256:59288cff2053, 137 tests` | `step1_check.log` |
| 2 | deploy rc 0, live `j20261104_152512_b93a-4e947a0ffe8b.up1` (image `ledger_staging_up1` sha256:4edca09d1842), smoke pass 17:58:53Z, rollback → 014 `.up1` | `step2_deploy.log` |
| 2' | `docker inspect`: `net=none`, root read-only, `CapDrop=[ALL]`, user `1001:1001`, `no-new-privileges`, `/data` = `data/pub` read-only; 1 container staging | `step2_inspect.log` |
| 3 | `Accept-Encoding: gzip` lewat socket (peer = pid container): `/jobs.csv` 200 `text/csv; charset=utf-8`, tanpa `Content-Encoding`, 3.553 byte; `/jobs` 200 `application/json`, `Content-Encoding: gzip` | `step3_gzip.log` |
| 4 | monitor `ok: true` (73 job, $4,7035 dari snapshot asli; viewer ok) | `step4_monitor.log` |
| 5 | live rilis Stage 13, `last monitor: pass` 17:59:14Z | `step5_status.log` |

Tanpa model, tanpa biaya; port 8000 tidak disentuh. Keputusan Atha: 2 ("go live" ×2); keputusan Claude: 0. Waktu
deploy < 2 menit.

Pelajaran: rencana staging untuk job pilot menyebut checkout tempat job-nya (`jobs/` per checkout). Pembanding up2:
langkah 3 diulang sesudah starlette 1.10.0 (CSV tetap tanpa gzip, JSON tetap gzip).
