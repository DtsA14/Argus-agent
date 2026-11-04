# Deploy Stage 13 / issue 015 ke staging (argus-ledger 4e947a0, job j20261104_152512_b93a)

Satu "go live" Atha untuk seluruh rencana ini (U4). Berhenti di langkah pertama yang tidak sesuai harapan; tidak ada
langkah tambahan atau ulangan. Hanya staging, tanpa model, tanpa jaringan; port 8000 tidak disentuh. Timer monitor
tetap berjalan (lock bersama: deploy menunggu ≤ 60 s bila monitor sedang jalan). `A = .venv-verify/bin/python scripts/argus.py`.
Alasan sekarang: up2 (2026-11-07) jangan membawa fitur dan upgrade dependensi sekaligus; tes CSV-tanpa-gzip jadi
pembanding perilaku `GZipMiddleware` sebelum starlette 1.10.0.

Setelah langkah yang menjalankan container: `docker inspect` (tanpa jaringan, root read-only, `CapDrop=[ALL]`, user
`1001:1001`, `no-new-privileges`, `/data` = `~/argus-staging/data/pub` read-only), tepat satu container staging.

| # | perintah | harapan |
|---|---|---|
| 0 | `$A stage status` | live `j20261030_060939_8433-1f31e34c1ff2.up1`, `last monitor: pass` |
| 1 | `$A stage check j20261104_152512_b93a --env ledger_py312_up1` | exit 0, PASS, 137 tests (133 + 4 tes draf) |
| 2 | `$A stage deploy j20261104_152512_b93a --runtime ledger_staging_up1 --yes` | exit 0; live `j20261104_152512_b93a-4e947a0….up1`; smoke pass dengan angka snapshot asli; rollback → 014 `.up1` |
| 3 | lewat socket (Claude, `stage._connect` dengan peer = pid container, header `Accept-Encoding: gzip`): `GET /jobs.csv`, `GET /jobs` | `/jobs.csv` 200, `text/csv`, tanpa `Content-Encoding`; `/jobs` 200, `Content-Encoding: gzip` |
| 4 | `$A stage monitor` | `ok: true` |
| 5 | `$A stage status` | live rilis Stage 13; `last monitor: pass` |

Rollback (bukan bagian rencana ini, butuh "go live" sendiri): `$A stage rollback --yes` → 014 `.up1`.
