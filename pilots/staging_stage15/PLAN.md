# Deploy argus-ledger Stage 15 (issue 017: waktu stage di GET /jobs/<id>) ke staging

**"Go live" Atha 2026-11-10 ("Izin go live diberikan", untuk deploy ledger yang dibutuhkan durasi stage di viewer).**
Claude menjalankan langkah berurutan dari `~/pilot3a_live` (`main`), **satu langkah = satu perintah**, mencatat output di
folder ini, dan berhenti di langkah pertama yang tidak sesuai harapan, tanpa menambah atau mengulang langkah. Hanya
staging; tanpa model; port 8000 tidak disentuh; unit proxy tidak diubah dan tidak di-restart (rute `/api/jobs/<id>` sudah
ada).

`A = .venv-verify/bin/python scripts/argus.py`. Job 017 = `j20261110_170837_da17` (APPLIED, argus-ledger `b712363` di atas
Stage 14 `1d3a8ea`; draf pertama `d628996b2722`, agen 2 percobaan, $0,036). Rilis = `j20261110_170837_da17-b712363….up2`
di runtime `ledger_staging_up2`. Viewer tidak berubah (rilis 040).

Setelah langkah 2: `docker inspect` (`NetworkMode=none`, `ReadonlyRootfs=true`, `CapDrop=[ALL]`, user `1001:1001`,
`no-new-privileges`, `/data` = `~/argus-staging/data/pub` read-only), tepat satu container `argus-staging-ledger-*`.

| # | perintah | harapan |
|---|---|---|
| 0 | `$A stage status`; `docker ps` | ledger live `j20261107_171214_be81-1d3a8ea82356.up2`, `last monitor: pass`; satu container `1a3c52e4173c` |
| 1 | `$A stage check j20261110_170837_da17 --env ledger_py312_up2` | exit 0, `stage check PASS` (seluruh tes ledger) |
| 2 | `$A stage deploy j20261110_170837_da17 --runtime ledger_staging_up2 --yes` | exit 0; live rilis Stage 15, smoke pass; rollback → Stage 14 `.up2` |
| 3 | `$A stage viewer-smoke` | exit 0, semua pass (lewat proxy 8710) |
| 4 | `$A stage monitor` | exit 0, `ok: true`, ledger Stage 15, viewer rilis 040 |
| 5 | `curl` `127.0.0.1:8710/api/jobs/j20261110_170837_da17` | 200 JSON; `stages_detail[0]` punya `started_at` dan `ended_at` berbentuk `YYYY-MM-DDTHH:MM:SSZ`, sesudah `cost_usd` |
| 6 | `$A stage status`; `docker ps` | ledger live Stage 15, rollback → Stage 14; satu container |

Rollback (bukan bagian rencana ini, butuh "go live" sendiri): `$A stage rollback --yes` (ledger → Stage 14 `.up2`).

Sesudahnya: Atha menekan Start pada job issue j20261110_165623_7672 (durasi di sel status, issue `5ecf8a413020`) dari HP;
Claude membaca draf, approve, applied, rilis viewer 041 (jalur cepat). Lalu `RESULT.md`, PENDING, memori.
