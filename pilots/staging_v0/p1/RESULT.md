# Pilot staging v0 #1: argus-ledger, deploy → deploy → rollback → deploy

2026-10-29, 13:43–13:49 UTC (20:43–20:49 WIB). Harness `main` cc7f63e (PR #244, SPEC_STAGING_V0). Image runtime
`ledger_staging` sha256:4ab2ff53a34f. Tanpa model, tanpa tool agen, data sintetis. Satu "go live" Atha per langkah (4).

| # | perintah | release live sesudahnya | smoke | waktu |
|---|---|---|---|---|
| 1 | `stage deploy j20261029_054325_6606` | 6606 @ argus-ledger `324012a` (stage 10) | pass 13:43:08Z | 2,7 s |
| 2 | `stage deploy j20261029_115742_bffd` | 013 @ `804e13a` (issue 013) | pass 13:47:43Z | 2,9 s |
| 3 | `stage rollback` | 6606 @ `324012a` | pass 13:48:44Z | 2,9 s |
| 4 | `stage deploy j20261029_115742_bffd` | 013 @ `804e13a` (akhir pilot) | pass 13:49:14Z | 2,9 s |

Semua keluar 0. Log per langkah di folder ini (`deploy1_6606.log`, `deploy2_013.log`, `rollback_to_6606.log`,
`status_after_rollback.log`, `deploy3_013_again.log`).

## Dicek Claude sesudah tiap langkah

- `docker inspect` container live: `NetworkMode=none`, `ReadonlyRootfs=true`, `CapDrop=[ALL]`, user `1001:1001`,
  `SecurityOpt=[no-new-privileges]`, keempat kalinya.
- Hanya satu container staging yang jalan sesudah tiap langkah; yang lama berhenti setelah yang baru lolos smoke.
- athena-api (port 8000) tidak disentuh dan tetap menjawab.

## Temuan

1. **Siklus lengkap jalan di data nyata pertama kali:** release dari commit job APPLIED, ganti release tanpa celah,
   rollback ke release sebelumnya dan smoke-nya, deploy ulang. Tiap langkah < 3 s karena image release sudah dibangun
   (dibangun sekali, dicek tiap kali).
2. **Rollback hanya mundur:** sesudah rollback ke 6606, `rollback would start: nothing (no earlier release)`. Kembali ke
   013 adalah deploy baru (butuh "go live" lagi), bukan "roll forward". Sesuai spek; dicatat agar tidak mengejutkan.
3. **Supervisi:** 4 keputusan Atha (satu "go live" per langkah), ~6 menit waktu terminal. Tidak ada keputusan Claude yang
   perlu di luar menjalankan perintah dan mengecek hasilnya.

## Langkah berikutnya (dari rencana, belum dimulai)

Tugas upgrade dependency dua lengan lewat staging (butuh spek sendiri dan image env baru).
