# Pilot dependency upgrade v0 #1: hasil

2026-10-29, 23:02–23:04 UTC (30 Oct 06:02–06:04 WIB). Harness `main` 0adb014 (#246 + PLAN #247). Satu "go live" Atha
untuk seluruh `PLAN.md` (U4, pertama kali). Tanpa model. **Semua 6 langkah sesuai harapan; tidak ada penghentian.**

| # | langkah | hasil | waktu |
|---|---|---|---|
| 0 | `stage status` | live 013 (`…-804e13a33c44`) di `ledger_staging` | — |
| 1 | `stage check 013 --env ledger_py312_up1` | PASS, 124 tests, image `59288cff2053` | 44 s |
| 2 | `stage deploy 013 --runtime ledger_staging_up1` | live `….up1`, smoke pass, Image `4edca09d1842`; layar menyebut check langkah 1 | 2,8 s |
| 3 | `stage rollback` | live 013 di `ledger_staging`, smoke pass, Image `4ab2ff53a34f` (v0) | 3,1 s |
| 4 | `stage deploy 013 --runtime ledger_staging_up1` | rilis `.up1` dipakai lagi (tidak dibangun ulang: 3 rekaman `built` total), smoke pass, Image `4edca09d1842` | 2,9 s |
| 5 | `stage status` | live `….up1` di `ledger_staging_up1`; rollback → 013 di `ledger_staging` | — |

Setiap container live: `NetworkMode=none`, `ReadonlyRootfs=true`, `CapDrop=[ALL]`, tanpa `CapAdd`, user `1001:1001`,
`no-new-privileges`, tidak privileged; tepat satu container staging; port 8000 (athena-api) tetap menjawab. Log per
langkah di folder ini (`step*_*.log`, `step*_inspect.log`).

## Temuan

1. **Rollback antar image bekerja di data nyata:** rilis 013 dari staging v0 (rekaman tanpa `image`) kembali di
   `V0_IMAGE`, bukan di image default baru; rilis `.up1` di image up1. Ini yang tidak bisa dilakukan staging v0.
2. **Gate check terlihat oleh operator:** layar deploy menyebut check yang dipakai (waktu, 124 tes).
3. **Supervisi turun:** 1 keputusan Atha ("go live") untuk 4 perintah yang mengubah staging, dibanding 4 di pilot
   staging #1. ~2 menit waktu terminal; check 44 s yang terlama.
4. Staging sekarang berakhir di argus-ledger 013 di stack up1 (fastapi 0.143.2, httpx2 2.13.1).

## Berikutnya

- PR "staging hardening" (temuan /code-review di kode staging v0, keputusan Atha 2026-10-29).
- `up2` (starlette 1.10.0, fastapi 0.162.0) mulai 2026-11-07, dengan PLAN.md yang sama bentuknya.
