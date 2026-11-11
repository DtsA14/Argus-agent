# Langkah (2026-11-11, Claude, "go live" Atha)

| # | hasil |
|---|---|
| 0 | live Stage 16 `j20261111_071510_9c2c-9bac6ededa97.up2`, monitor pass 13:00:32Z; satu container `d867fda9a340` |
| 1 | `stage check PASS: commit f2852daab505 in ledger_py312_up2 sha256:3e48cd98c8de, 166 tests` |
| 2 | exit 0; live `j20261111_114930_18a2-f2852daab505.up2`, smoke pass 13:08:44Z; rollback → Stage 16. Container: net none, ReadonlyRootfs true, CapDrop ALL, user 1001:1001, no-new-privileges, `/data` read-only |
| 3 | `viewer-smoke` exit 0, semua ok (listen 127.0.0.1:8710 saja) |
| 4 | `monitor` exit 0, `ok: true`, release Stage 17, 149 job |
| 5 | `/api/jobs` 200: 149 job, 149 dengan `max_usd` (float: 0.25, 0.5, 1.0, 1.3) tepat sesudah `cost_usd`; sumber snapshot: 149 dari 149 `job.json` punya `max_usd` angka (belum teruji di staging: kasus tanpa `max_usd`, hanya di tes); `/api/jobs/j20261111_114930_18a2` 200, kunci `job, state, created_at, title, stages, decisions, cost_nano, cost_usd, max_usd, running, stages_detail` |
| 6 | live Stage 17, rollback → Stage 16 `j20261111_071510_9c2c-9bac6ededa97.up2`; satu container `5853928e827c` |

Semua sesuai harapan. Berikutnya: T2, issue viewer dari bentuk `max_usd` di patch T1 yang ter-apply.
