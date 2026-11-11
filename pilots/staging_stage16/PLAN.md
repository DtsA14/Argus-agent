# Deploy argus-ledger Stage 16 (issue 018: judul job di GET /jobs dan GET /jobs/<id>) ke staging

**Menunggu "go live" Atha.** Claude menjalankan langkah berurutan dari `~/pilot3a_live` (`main`), **satu langkah = satu
perintah**, mencatat output di folder ini, dan berhenti di langkah pertama yang tidak sesuai harapan, tanpa menambah atau
mengulang langkah. Hanya staging; tanpa model; port 8000 tidak disentuh; unit proxy tidak diubah dan tidak di-restart.

`A = .venv-verify/bin/python scripts/argus.py`. Job 018 = `j20261111_071510_9c2c` (APPLIED, argus-ledger `9bac6ed` di atas
Stage 15 `b712363`; issue ditulis Haiku dari HP `j20261111_054721_cebd`, draf `047242771aa6` dibaca dan di-approve Claude,
agen 1 percobaan 13 langkah, $0,038 total). Rilis = `j20261111_071510_9c2c-9bac6ed….up2` di runtime `ledger_staging_up2`.
Viewer tidak berubah (rilis 041; `readJob` membuang kunci yang tidak dikenalnya). Snapshot sudah menerbitkan `title`
(#421/#422).

Setelah langkah 2: `docker inspect` (`NetworkMode=none`, `ReadonlyRootfs=true`, `CapDrop=[ALL]`, user `1001:1001`,
`no-new-privileges`, `/data` = `~/argus-staging/data/pub` read-only), tepat satu container `argus-staging-ledger-*`.

| # | perintah | harapan |
|---|---|---|
| 0 | `$A stage status`; `docker ps` | ledger live `j20261110_170837_da17-b712363c860b.up2`, `last monitor: pass`; satu container `240860d8cdcf` |
| 1 | `$A stage check j20261111_071510_9c2c --env ledger_py312_up2` | exit 0, `stage check PASS` (seluruh tes ledger) |
| 2 | `$A stage deploy j20261111_071510_9c2c --runtime ledger_staging_up2 --yes` | exit 0; live rilis Stage 16, smoke pass; rollback → Stage 15 `.up2` |
| 3 | `$A stage viewer-smoke` | exit 0, semua pass (lewat proxy 8710) |
| 4 | `$A stage monitor` | exit 0, `ok: true`, ledger Stage 16, viewer rilis 041 |
| 5 | `curl` `127.0.0.1:8710/api/jobs` dan `/api/jobs/j20261111_071510_9c2c` | 200 JSON; job code/riset punya `title` sesudah `created_at`; job `issue` tanpa `title` |
| 6 | `$A stage status`; `docker ps` | ledger live Stage 16, rollback → Stage 15; satu container |

Rollback (bukan bagian rencana ini, butuh "go live" sendiri): `$A stage rollback --yes` (ledger → Stage 15 `.up2`).

Sesudahnya: Atha membalas job issue viewer `j20261111_043029_53f7` dari HP (judul dari `title` di GET /jobs); Claude
membaca draf, approve, applied, rilis viewer 042 (jalur cepat).
