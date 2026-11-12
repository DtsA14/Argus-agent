# Deploy argus-ledger Stage 18 (issue 020: `GET /scoreboard`) ke staging

Irisan S2 dari probe PRD-lite (`pilots/prd_probe_v0/PRD.md`). **Menunggu "go live" Atha** (satu "go live" per PLAN.md yang ter-commit).
Claude menjalankan langkah berurutan dari `~/pilot3a_live` (`main`), **satu langkah = satu perintah**, mencatat output di `steps.md` di folder ini, dan berhenti di langkah pertama yang tidak sesuai
harapan, tanpa menambah atau mengulang langkah. Hanya staging; tanpa model; port 8000 tidak disentuh; unit proxy tidak diubah dan tidak di-restart.

`A = .venv-verify/bin/python scripts/argus.py`. Job 020 = `j20261112_053107_1929` (APPLIED, argus-ledger `1aeb82d` di atas Stage 17 `f2852da`; issue ditulis Claude dari kontrak PRD, draf `a220bee8f3b4` dibaca dan
di-approve Claude, agen 1 percobaan 24 langkah, $0,0375 total). Rilis = `j20261112_053107_1929-1aeb82d….up2` di runtime `ledger_staging_up2`. Viewer: rilis 045 (`bc558cc`) tidak berubah oleh langkah ini; halaman
`/scoreboard` di viewer (job `j20261112_053656_8a3e`) dirilis **sesudah** langkah ini, sebagai langkah terpisah.

Setelah langkah 2: `docker inspect` (`NetworkMode=none`, `ReadonlyRootfs=true`, `CapDrop=[ALL]`, user `1001:1001`, `no-new-privileges`, `/data` read-only), tepat satu container `argus-staging-ledger-*`.

| # | perintah | harapan |
|---|---|---|
| 0 | `$A stage status`; `docker ps` | ledger live `j20261111_114930_18a2-f2852daab505.up2`, `last monitor: pass`; satu container |
| 1 | `$A stage check j20261112_053107_1929 --env ledger_py312_up2` | exit 0, `stage check PASS` (seluruh tes ledger) |
| 2 | `$A stage deploy j20261112_053107_1929 --runtime ledger_staging_up2 --yes` | exit 0; live rilis Stage 18, smoke pass; rollback → Stage 17 `.up2` |
| 3 | `$A stage viewer-smoke` | exit 0, semua pass (lewat proxy 8710) |
| 4 | `$A stage monitor` | exit 0, `ok: true`, ledger Stage 18, viewer rilis 045 |
| 5 | `curl` `127.0.0.1:8710/api/scoreboard` | 200 JSON; kunci `jobs`, `kinds`, `cost_per_applied` berurutan; `kinds` berurutan code, research, issue (lalu `other` bila ada); jumlah `jobs` sama dengan `/api/summary`; jumlah hasil tiap jenis = `jobs` jenis itu |
| 6 | `$A stage status`; `docker ps` | ledger live Stage 18, rollback → Stage 17; satu container |

Rollback (bukan bagian rencana ini, butuh "go live" sendiri): `$A stage rollback --yes` (ledger → Stage 17 `.up2`).

Sesudahnya: rilis viewer untuk halaman `/scoreboard` (S3), lalu S4.
