# Pilot staging data asli #1: snapshot, rilis di data asli, monitor, report, timer

Spek: `docs/reviews/SPEC_STAGING_REAL_DATA.md` (merged #251, 3a877b7). **Satu "go live" Atha untuk seluruh rencana ini**
(U4). Claude menjalankan langkah berurutan dari `~/pilot3a_live` (`main`), mencatat output tiap langkah di folder ini,
dan berhenti di langkah pertama yang tidak sesuai harapan, tanpa menambah atau mengulang langkah. Hanya staging; tanpa
model; tanpa jaringan; athena-api (port 8000) tidak disentuh.

`A = .venv-verify/bin/python scripts/argus.py`; job 013 = `j20261029_115742_bffd`. Container live sekarang (013 `.up1`)
dijalankan kode lama dengan data fixture; `deploy` rilis yang sama ditolak ("already live"), jadi rilis berganti lewat
rollback lalu deploy.

Setelah setiap langkah yang menjalankan container: `docker inspect` (tanpa jaringan, root read-only, `CapDrop=[ALL]`,
user `1001:1001`, `no-new-privileges`, **`/data` = `~/argus-staging/data/pub` read-only**), tepat satu container
staging, dan dari dalam container `/data` hanya berisi `jobs` dan `snap-*`; port 8000 tetap menjawab.

| # | perintah | harapan |
|---|---|---|
| 0 | `$A stage status` | live `…-804e13a33c44.up1`; `data snapshot: none` |
| 1 | `$A stage refresh` | exit 0; jumlah job = direktori job di `jobs/`, 0 excluded, total = Σ harness (`router.job` per job, dicek Claude terpisah) |
| 2 | `$A stage rollback --yes` | exit 0; live `…-804e13a33c44` (runtime `ledger_staging`, image v0 `4ab2ff53a34f`); smoke pass **dengan angka data asli** |
| 3 | `$A stage deploy j20261029_115742_bffd --runtime ledger_staging_up1 --yes` | exit 0; live `….up1` (image `4edca09d1842`), smoke pass dengan angka asli |
| 4 | `$A stage monitor` | exit 0; `ok: true`, refresh ok, smoke pass |
| 5 | `$A stage report` | exit 0; `~/argus-staging/reports/<UTC>/report.html` + `summary.txt` (0700/0600); Claude mengirim `report.html` ke Atha |
| 6 | pasang timer: `ln -s ~/pilot3a_live/deploy/systemd/argus-stage-monitor.{service,timer} ~/.config/systemd/user/`, `systemctl --user daemon-reload`, `systemctl --user enable --now argus-stage-monitor.timer` | `list-timers` menunjukkan run berikutnya ≤ 15 menit |
| 7 | tunggu run pertama dari timer | rekaman baru di `monitor.jsonl` dengan `ok: true`; `systemctl --user status argus-stage-monitor.service` sukses |
| 8 | `$A stage status` | live `….up1`; `data snapshot: <UTC>, N jobs, 0 excluded`; `last monitor: pass` |

Di luar rencana (keputusan Atha, bukan langkah Claude): **lingering** (`Linger=no` sekarang): tanpa itu timer hanya
berjalan selama Atha punya sesi; menyalakannya butuh sudo: `sudo loginctl enable-linger ubuntu`.

Sesudahnya: `RESULT.md`, PENDING.md, lalu job issue 014 (jalur cepat, "go live" sendiri).
