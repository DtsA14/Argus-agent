# Deploy argus-ledger Stage 17 (issue 019: `max_usd` di GET /jobs dan GET /jobs/<id>) ke staging

Langkah S dari `docs/reviews/SPEC_CHAIN_PROBE.md`. **Menunggu "go live" Atha** (satu "go live" per PLAN.md yang ter-commit).
Claude menjalankan langkah berurutan dari `~/pilot3a_live` (`main`), **satu langkah = satu perintah**, mencatat output di
`steps.md` di folder ini, dan berhenti di langkah pertama yang tidak sesuai harapan, tanpa menambah atau mengulang langkah.
Hanya staging; tanpa model; port 8000 tidak disentuh; unit proxy tidak diubah dan tidak di-restart.

`A = .venv-verify/bin/python scripts/argus.py`. Job 019 = `j20261111_114930_18a2` (APPLIED, argus-ledger `f2852da` di atas
Stage 16 `9bac6ed`; job ketiga untuk issue ini: dua sebelumnya `j20261111_112252_11b3` dan `j20261111_113723_c4be` tidak
di-apply, lihat `pilots/chain_probe_v0/RESULT.md`). Rilis = `j20261111_114930_18a2-f2852da….up2` di runtime
`ledger_staging_up2`. Viewer tidak berubah (rilis 043; `readJob` membuang kunci yang tidak dikenalnya). Snapshot sudah
menyertakan `max_usd` di `job.json`.

Setelah langkah 2: `docker inspect` (`NetworkMode=none`, `ReadonlyRootfs=true`, `CapDrop=[ALL]`, user `1001:1001`,
`no-new-privileges`, `/data` = `~/argus-staging/data/pub` read-only), tepat satu container `argus-staging-ledger-*`.

| # | perintah | harapan |
|---|---|---|
| 0 | `$A stage status`; `docker ps` | ledger live `j20261111_071510_9c2c-9bac6ededa97.up2`, `last monitor: pass`; satu container `d867fda9a340` |
| 1 | `$A stage check j20261111_114930_18a2 --env ledger_py312_up2` | exit 0, `stage check PASS` (seluruh tes ledger) |
| 2 | `$A stage deploy j20261111_114930_18a2 --runtime ledger_staging_up2 --yes` | exit 0; live rilis Stage 17, smoke pass; rollback → Stage 16 `.up2` |
| 3 | `$A stage viewer-smoke` | exit 0, semua pass (lewat proxy 8710) |
| 4 | `$A stage monitor` | exit 0, `ok: true`, ledger Stage 17, viewer rilis 043 |
| 5 | `curl` `127.0.0.1:8710/api/jobs` dan `/api/jobs/j20261111_114930_18a2` | 200 JSON; setiap job dengan `max_usd` angka di `job.json` punya `max_usd` tepat sesudah `cost_usd`; job tanpa `max_usd` tidak; urutan kunci lain tak berubah |
| 6 | `$A stage status`; `docker ps` | ledger live Stage 17, rollback → Stage 16; satu container |

Rollback (bukan bagian rencana ini, butuh "go live" sendiri): `$A stage rollback --yes` (ledger → Stage 16 `.up2`).

Sesudahnya: T2, issue viewer yang ditulis dari bentuk `max_usd` di patch T1 yang ter-apply (jalur cepat).
