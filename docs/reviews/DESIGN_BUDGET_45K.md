# Eksperimen diagnostik budget 30k vs 45k: desain (untuk review; tanpa kode dan tanpa run)

Status: **draf, revisi 1** (review PR #64), 2026-10-17. Persetujuan menulis desain bukan persetujuan menjalankan eksperimen. Latar:
`docs/reviews/M3_CLOSING.md` bagian 4. Kelima kegagalan seri #2 sudah menemukan akar masalah, lalu kehabisan
reservasi pada panggilan untuk menulis fix (di tiga run kurangnya 344–694 token).

## 1. Hipotesis dan variabel

**Hipotesis:** `attempt_tokens` 45.000 meningkatkan peluang agen menyelesaikan diagnosis **dan** menulis fix dalam satu
attempt, dibanding 30.000.

**Variabel tunggal:** `code_task.attempt_tokens` 30.000 vs 45.000. Yang tetap sama di kedua lengan:
- fixture `ledger` dan kontrak (isi tugas, kriteria, scope, validasi);
- prompt sistem dan prompt task, termasuk umpan balik attempt berikutnya (main saat ini);
- model Sonnet 5.5, `max_steps` 12, `stagnation_rounds` 2, `max_iterations` 3;
- acceptance dan validasi independen;
- cap biaya (lihat 3).

Kedua lengan dijalankan di commit yang sama, dalam satu seri yang diselang-seling.

## 2. Sinyal utama dan bukti pendukung (revisi setelah review)

**Sinyal utama:** tingkat sukses task di 45k dibanding 30k, ditambah biaya per task sukses dan tingkat kegagalan jujur.
**Satu klaim palsu adalah regresi kejujuran**, berapa pun suksesnya. Dengan 9 pasangan, ini sinyal diagnostik, bukan
kesimpulan statistik dan bukan estimasi kemampuan Argus secara umum.

**Bukti pendukung** dicatat per run untuk menjelaskan hasil, **bukan untuk mengklasifikasikan penyebab secara otomatis**.
Tidak ada ambang ±20%.

| Dicatat per run | Sumber |
|---|---|
| Apakah agen menemukan akar masalah: membaca `prepare.py` dan `options.py`, dan teks model menyebutnya | ledger, memo (`scripts/failure_trace.py`) |
| Kapan fix pertama ditulis: attempt, panggilan ke berapa, token kumulatif attempt, dan apakah lolos target | ledger, verdict attempt itu |
| Panggilan yang ditolak (input dibutuhkan vs sisa) dan balasan yang terpotong | ledger (`refused`, `reply_truncated`) |
| Attempt yang tidak diterima karena cap (`max_usd`) | event `status` / `stop_reason` |
| Total token dan biaya aktual per attempt dan per run | ledger |

Laporan akhir membandingkan catatan ini secara deskriptif antarlengan. Contohnya:
- apakah sukses tambahan di 45k adalah run yang menulis fix di atas 30.000 token kumulatif;
- apakah agen di 45k membaca lebih banyak sebelum fix.

Itu penjelasan yang mungkin, bukan bukti kausal.

## 3. Cap biaya: semantik reservasi yang sebenarnya, dan simulasinya

**Semantik di harness (dari kode, bukan asumsi).** Sebelum setiap attempt, `admission` (`codetask/run.py`) menghitung
**pengeluaran aktual** run itu dari ledger, lalu menambahkan **reservasi penuh satu attempt**.
- Reservasi itu adalah `attempt_tokens` × tarif tertinggi, yaitu output $10 per juta.
- Panggilan yang terpotong crash dihitung dengan worst case-nya.
- Attempt dimulai hanya jika jumlah itu ≤ cap, yang merupakan nilai terketat dari config dan kontrak.
- Reservasi attempt sebelumnya **tidak** ditumpuk. Yang dihitung hanya biaya yang benar-benar tercatat.
- Batas token juga dicek: `budget.max_tokens` 200.000 ≥ pengeluaran + `attempt_tokens`. Di 45k, tiga attempt penuh
  (135.000) masih muat.

**Simulasi dengan fungsi asli** (`scripts/sim_admission.py`: `settings` dan `admission` dari harness, ledger buatan,
cap $1.00):

| | 30k | 45k |
|---|---|---|
| Reservasi per attempt | $0.30 | $0.45 |
| Attempt berikutnya diterima selama pengeluaran sebelumnya ≤ | $0.70 | $0.55 |
| Biaya tipikal per attempt (dari seri #2, 45k = ×1.5) | $0.060 → attempt 2 dan 3 diterima | $0.090 → attempt 2 dan 3 diterima |
| Maksimum yang masuk akal (semua token terpakai, 5% output) | $0.072 → 2 dan 3 diterima | $0.108 → 2 dan 3 diterima |
| Patologis (semua token ditagih dengan tarif output) | $0.300 → 2 dan 3 diterima | $0.450 → 2 diterima, **3 ditolak** |

Replay biaya aktual per attempt dari kesembilan run seri #2, dikali 1.5 untuk 45k: **attempt ke-3 diterima di 9 dari
9.**

**Kesimpulan yang dikunci:**
- Cap $1.00 memberi kedua lengan kesempatan attempt yang sama **dalam semua kasus kecuali kasus patologis**. Di kasus
  patologis, attempt ke-3 di 45k ditolak.
- Karena itu kita **tidak** mengklaim kesempatan retry yang identik tanpa syarat. Setiap attempt yang ditolak oleh
  cap dicatat per run dan per lengan. Jika itu terjadi, pasangan tersebut ditandai sebagai kesempatan retry yang
  berbeda.
- Kebanyakan run berhenti di attempt ke-2 karena stagnasi (`stagnation_rounds` 2), jadi attempt ke-3 jarang menjadi
  penentu.
- Saat implementasi, ditambahkan tes permanen. Tes itu memakai ledger buatan dan cap $1.00, dan memeriksa ambang
  $0.70 dan $0.55 serta penolakan attempt ke-3 di kasus patologis 45k.

**Cap seri $5.00 adalah batas darurat, bukan jaminan 18 run selesai.**
- Guard dicek **per pasangan**: sebuah pasangan 30k/45k hanya dimulai jika pengeluaran seri + 2 × $1.00 ≤ $5.00. Jadi
  cap tidak pernah memotong sebuah pasangan di tengah.
- Pasangan dimulai selama pengeluaran ≤ $3.00. Estimasi realistis seluruh seri sekitar $2–3 (per run sekitar
  $0.10–0.15), jadi guard hanya terpicu jika biaya jauh di atas perkiraan. Itu sendiri temuan.
- Jika guard terpicu: pasangan sisanya tidak dijalankan, tidak ada cap yang dilewati, dan tidak ada run yang diulang.
- Jika sebuah pasangan tidak lengkap karena aturan henti lain (`BLOCKED`, `FAILED_BUDGET`, anomali), pasangan itu
  ditandai **tidak lengkap** dan **tidak dipakai** dalam perbandingan berpasangan. Ia hanya dilaporkan.
- Saldo provider harus ≥ $5.00 sebelum run.

## 4. Jumlah run, kontrak, dan urutan

**9 run per lengan, 18 total.** Kontrak A/B/C × 3 di setiap lengan, sama dengan seri #1 dan #2.
- Kelima kegagalan seri #2 ada di A dan B. C sukses 3/3 di 30k, dan C memperbaiki di attempt pertama 6/6 di kedua
  seri. Kalau hanya C yang dipakai, kemungkinan besar terjadi efek plafon.
- A/B/C dilaporkan per varian dan total. Pertanyaan utamanya adalah total 9 vs 9.
- Search tetap bukan pertanyaan di sini.

**Urutan diacak dan diseimbangkan.**
- Setiap sel (varian, ulangan) punya pasangan 30k dan 45k yang dijalankan **berdampingan**, dengan urutan acak di
  dalam pasangan. Urutan kesembilan pasangan juga diacak.
- Seed dicatat di preflight. Ini menyeimbangkan pergeseran waktu, misalnya perilaku provider, di antara kedua lengan.

**Seri #2 bukan lengan 30k.** Seri #2 tetap menjadi titik pembanding ketiga, tapi tidak dipakai sebagai lengan 30k,
karena:
1. commit berbeda (setelah seri #2, umpan balik ber-`subTest` diperbaiki);
2. waktu berbeda;
3. cap berbeda.

Menjalankan ulang 30k menambah sekitar $0.9, tapi perbandingannya bersih.

**n = 9 per lengan tetap sampel kecil.** Selisih 1–2 run tidak bisa dibedakan dari variasi model. Hanya pola yang
besar dan konsisten dengan diagnostik bagian 2 yang dibaca sebagai sinyal.

## 5. Perubahan yang diperlukan (diimplementasikan setelah desain disetujui, dengan tes)

1. **Dua config eksperimen** yang dibuat dari `config.yaml`: `attempt_tokens` 30.000 / 45.000, `budget.max_usd` $1.00.
   **Tes:** setelah dimuat, kedua config hanya berbeda di `attempt_tokens`, dan keduanya hanya berbeda dari
   `config.yaml` di dua kunci itu.
2. **Manifest eksperimen** `evals/budget_v1/manifest.json` dengan salinan kontrak `ledger_terms_{a,b,c}`, hanya
   `limits.max_usd` $1.00 dan id kontrak yang berbeda.
   - **Tes:** salinannya identik dengan aslinya kecuali dua field itu.
   - Hash benchmark baru dicatat.
   - Kontrak repo dan benchmark v1 serta search_v1 tidak berubah.
3. **`scripts/run_series.py`:**
   - entri per run membawa lengan (misalnya `a1@45`), dipetakan ke config lengan itu lewat `--config` milik `run_eval`;
   - **guard cap seri per pasangan**: sebuah pasangan dimulai hanya jika pengeluaran + 2 × cap per run ≤ cap
     seri; pasangan yang tidak lengkap ditandai di `series.json`.
   - **Tes:** guard menolak sebelum run yang tidak muat, `series.json` mencatat alasannya, dan lengan yang salah
     petakan ditolak.
4. **`scripts/analyze_series.py`:** catatan bagian 2 per run, termasuk attempt yang ditolak cap.
5. **Tes admission** (bagian 3): ambang $0.70 dan $0.55, dan penolakan attempt ke-3 di kasus patologis 45k.

Tidak ada perubahan pada harness inti: loop agen, LLMCaller, acceptance, dan umpan balik.

## 6. Yang tidak dilakukan

- Tidak menaikkan budget permanen.
- Tidak mengubah prompt atau umpan balik.
- Tidak menambah completion reserve.
- Tidak mengoptimalkan konteks.
- Kalau 45k membantu, keputusan apakah harga token itu sepadan atau apakah efisiensi konteks lebih tepat diambil
  setelah melihat data. Bukan bagian dari eksperimen ini.
