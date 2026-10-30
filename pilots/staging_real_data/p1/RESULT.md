# Pilot staging data asli #1: hasil

2026-10-30, 05:46–06:00 UTC (12:46–13:00 WIB). Harness `main` 518c18f (#251 + PLAN #252). Satu "go live" Atha untuk
seluruh `PLAN.md`; lingering `systemd --user` dinyalakan atas permintaan Atha sebelumnya (`sudo loginctl enable-linger
ubuntu`). Tanpa model, tanpa jaringan. **Semua 9 langkah sesuai harapan; tidak ada penghentian.**

| # | langkah | hasil |
|---|---|---|
| 0 | `stage status` | live 013 `.up1` (kode lama, data fixture); `data snapshot: none` |
| 1 | `stage refresh` | 54 job (= direktori `jobs/`), 0 excluded, 4.176.849.024 nano = Σ `router.job.spent_nano` (dicek terpisah) |
| 2 | `stage rollback` | 013 di `ledger_staging` (image v0 `4ab2ff53a34f`); smoke pass dengan angka asli: `{"jobs":54,"cost_nano":4176849024}` |
| 3 | `stage deploy 013 --runtime ledger_staging_up1` | `.up1` (image `4edca09d1842`), smoke pass dengan angka asli |
| 4 | `stage monitor` | `ok: true`, refresh ok (54), 4/4 cek |
| 5 | `stage report` | `reports/20261030T054717Z/` 0700, `report.html` + `summary.txt` 0600; dikirim ke Atha |
| 6 | pasang timer | `argus-stage-monitor.timer` aktif, run berikutnya 06:00 |
| 7 | run pertama dari timer (06:00:31Z) | `ok: true`, `status=0/SUCCESS`, 1,5 s CPU |
| 8 | `stage status` | live `.up1`; `data snapshot: 2026-10-30T06:00:32Z, 54 jobs, 0 excluded`; `last monitor: pass` |

Setiap container live: tanpa jaringan, root read-only, `CapDrop=[ALL]`, tanpa `CapAdd`, user `1001:1001`,
`no-new-privileges`, tidak privileged; **`/data` = `~/argus-staging/data/pub` read-only**, dari dalam container hanya
`jobs` dan `snap-*` terlihat (tanpa lock, tanpa build); tepat satu container staging; port 8000 tetap menjawab.

## Temuan

1. **Dashboard Argus berjalan di data Argus sendiri:** 54 job, $4,1768, dengan angka yang dicek otomatis terhadap
   perhitungan harness setiap 15 menit. Gap M9 "data staging sintetis" dan "tidak ada monitoring sesudah deploy" tertutup.
2. **Pergantian data tanpa restart bekerja di produksi-kecil ini:** snapshot berganti di 06:00:32 (refresh dari timer)
   dan container yang sama langsung melayaninya.
3. **Supervisi:** 1 keputusan ("go live") untuk 3 perintah yang mengubah staging + pemasangan timer; lingering 1
   keputusan terpisah.
4. Cek pengecekan peer (`SO_PEERCRED` = pid utama container) lolos pada uvicorn sungguhan di kedua image.

## Berikutnya

Issue 014 (keputusan manusia per job, `~/argus-ledger-issues/014-human-decisions.txt`) sebagai job Argus jalur cepat,
"go live" sendiri; sesudah `applied`, deploy lewat PLAN.md berikutnya. `up2` mulai 2026-11-07.
