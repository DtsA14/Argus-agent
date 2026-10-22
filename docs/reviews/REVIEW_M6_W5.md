# M6 W5: profil budget per task

Status: **implementasi untuk review.** 2026-10-17. Rencana: `docs/reviews/M6_PLAN.md` W5. Tanpa run live, dan default
$0.50 tidak berubah.

## 1. Yang dibangun

| Bagian | Isi |
|---|---|
| **Profil di config** | `code_task.profiles`: `default` (30.000 / 4.096, sama persis dengan nilai tanpa profil; dikunci tes) dan `large` (45.000 / 8.192). |
| **Dipilih eksplisit oleh kontrak** | Field opsional `budget_profile` (nama huruf kecil). Kontrak tanpa field ini berjalan persis seperti sebelumnya. |
| **Profil tidak pernah menaikkan cap** | `apply_profile` hanya mengubah `attempt_tokens` dan `max_output_tokens` coder. Cap tetap `min(budget.max_usd, limits.max_usd kontrak)`. Cap di atas $0.50 berarti config per run yang disetujui di preflight, bukan efek profil. |
| **Gagal tertutup** | Nama profil yang tidak ada di config menjadi `BLOCKED invalid_contract` di setup, sebelum panggilan model. Kontrak yang cap-nya tidak cukup untuk satu attempt profilnya berakhir `FAILED_BUDGET` di setup, dengan 0 panggilan model, lewat admission yang sudah ada. Status baru tidak diperlukan. |
| **Konsisten dengan kontrak beku** | Profil diterapkan sebelum graph dibangun (caller dan attempt bergantung padanya): dari file kontrak pada run baru, dari kontrak beku pada resume. Setup dan node agen memeriksa bahwa kontrak beku menyebut profil yang sama. Kalau tidak, hasilnya `BLOCKED contract_changed` sebelum panggilan model. Di setup, run bahkan tidak pernah masuk RUNNING, jadi admission tidak dihitung dengan profil yang salah. |
| **Tercatat** | `budget_profile` (nama, attempt_tokens, max_output_tokens) ada di event log, state, dan `result.json`. |

## 2. Angka admission (dengan `admission` asli, harga Sonnet 5.5 $10/M output)

| Cap | Profil `large` ($0.45 per attempt) |
|---|---|
| $0.50 (default) | Attempt kedua hanya kalau yang pertama ≤ $0.05, jadi praktis **satu attempt**. |
| $1.00 (hanya lewat preflight) | Setiap attempt berikutnya masuk selama belanja sejauh ini ≤ **$0.55**. Contoh: $0.30 + $0.25 masuk, $0.30 + $0.26 tidak. |

**Koreksi rencana:** `M6_PLAN.md` W5 sebelumnya menulis bahwa attempt ketiga di $1.00 hanya masuk kalau dua yang
pertama ≤ $0.10. Itu salah. Aturannya belanja + satu reservasi ≤ cap, jadi batasnya $0.55. Kesalahan itu ditemukan
oleh tes W5 sendiri. Rencananya sudah dikoreksi, dan angka yang benar sekarang dikunci tes.

## 3. Bukti

- **Tes** (`tests/test_codetask.py`, bagian M6 W5):
  - `default` sama dengan nilai tanpa profil;
  - profil hanya mengubah dua nilai;
  - `max_usd` tidak berubah untuk cap kontrak $0.50, $1.00, dan $5.00;
  - angka admission di atas;
  - profil sampai ke panggilan model (`max_tokens` 8.192 dan 4.096) dan ke `result.json`;
  - profil tidak dikenal diblok;
  - cap yang tidak cukup untuk satu attempt `large` berhenti tanpa panggilan, sementara cap yang sama cukup untuk `default`;
  - ketidakcocokan profil diblok di setup dan saat resume;
  - validasi nama profil.
- **Mutan: 10/10 tertangkap.** Yang diuji:
  - profil menaikkan cap;
  - profil tidak mengatur output cap;
  - profil tidak pernah diterapkan;
  - profil tidak dikenal diterima;
  - setup tidak membandingkan profil;
  - node agen tidak membandingkan profil;
  - nama tidak divalidasi;
  - `budget_profile` hilang dari hasil;
  - nilai `large` di config berubah;
  - `default` bergeser dari nilai tanpa profil.

  Satu mutan sempat lolos di putaran pertama: setup tidak membandingkan profil. Penyebabnya, node agen tetap memblok
  dengan hasil akhir yang sama. Tesnya diperketat (run tidak pernah masuk RUNNING), dan mutan itu sekarang tertangkap.
  Log: `verification/mutants-w5-*.log`.
- `tests/test_budget_experiment.py`: `code_task.profiles` (ditambahkan setelah eksperimen budget) dikecualikan dari
  perbandingan dengan config lengan eksperimen, sama seperti `sandbox.environments` di W1.
