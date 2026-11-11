# Pilot: drafter memperbaiki kesalahan formulir (SPEC_DRAFTER_FORM_FIXES, PENDING 3a-2)

**Go live tetap** (Atha 2026-11-11 "ambil semuanya": deploy yang hanya menarik kode tanpa restart service, tanpa staging,
uang atau key). Claude menjalankan langkah berurutan, mencatat di `steps.md` di PR ini, berhenti di penyimpangan pertama.

| # | perintah / cek | harapan |
|---|---|---|
| 0 | `git -C ~/pilot3a_live log -1`, `status --short`; tidak ada job `DRAFTING` | HEAD `0e98eee` (#429) atau sesudahnya tanpa PR ini; bersih; tidak ada drafter berjalan (versi alat SubmitDraft 4 → 5) |
| 1 | `git -C ~/pilot3a_live pull --ff-only` | fast-forward ke merge PR ini |

Ukuran (sesudahnya, job viewer berikutnya): submit yang ditolak karena formulir (id, tes baru protected, glob tidak cocok,
nama tes lama) = 0; dibanding d1 4, d2 3 (`j20261111_073447_cc5a`).
Rollback: `git -C ~/pilot3a_live checkout <HEAD langkah 0>`.
