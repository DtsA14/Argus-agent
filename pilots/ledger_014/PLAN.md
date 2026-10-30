# Deploy issue 014 ke staging (argus-ledger 1f31e34, job j20261030_060939_8433)

Satu "go live" Atha untuk seluruh rencana ini (U4). Berhenti di langkah pertama yang tidak sesuai harapan. Hanya
staging, tanpa model, tanpa jaringan; port 8000 tidak disentuh. Timer monitor tetap berjalan (lock bersama: deploy
menunggu ≤ 60 s bila monitor sedang jalan). `A = .venv-verify/bin/python scripts/argus.py`.

Setelah langkah yang menjalankan container: `docker inspect` (tanpa jaringan, root read-only, `CapDrop=[ALL]`, user
`1001:1001`, `no-new-privileges`, `/data` = `~/argus-staging/data/pub` read-only), tepat satu container staging.

| # | perintah | harapan |
|---|---|---|
| 0 | `$A stage status` | live `j20261029_115742_bffd-804e13a33c44.up1`, `last monitor: pass` |
| 1 | `$A stage check j20261030_060939_8433 --env ledger_py312_up1` | exit 0, PASS, 133 tests |
| 2 | `$A stage deploy j20261030_060939_8433 --runtime ledger_staging_up1 --yes` | exit 0; live `j20261030_060939_8433-1f31e34c1ff2.up1`; smoke pass dengan angka snapshot asli; rollback → 013 `.up1` |
| 3 | `GET /jobs` lewat socket (Claude, `sg._get` dengan peer = pid container) | setiap job punya `decisions` (angka); `GET /jobs/j20261029_115742_bffd` punya daftar `decisions` |
| 4 | `$A stage monitor` | `ok: true` |
| 5 | `$A stage status` | live rilis 014; `last monitor: pass` |
