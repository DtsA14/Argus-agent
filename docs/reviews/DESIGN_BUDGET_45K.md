# Eksperimen diagnostik budget 30k vs 45k: desain (untuk review; tanpa kode dan tanpa run)

Status: **draf**, 2026-10-17. Persetujuan menulis desain bukan persetujuan menjalankan eksperimen. Latar:
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

## 2. Membedakan "budget memang kurang" dari "budget tambahan hanya dihabiskan"

Status DONE saja tidak cukup untuk membedakan keduanya. Per attempt yang menulis perbaikan yang benar, dicatat:

| Diagnostik | Definisi |
|---|---|
| **Token sampai fix** | token kumulatif attempt itu pada panggilan yang menulis perbaikan yang lolos tes target (dari ledger, dikonfirmasi oleh verdict attempt itu) |
| File dibaca sebelum fix | jumlah `ReadFile` dan `SearchFiles` sebelum panggilan itu |
| Panggilan sebelum fix | jumlah panggilan model sebelum panggilan itu |
| Sisa sesudah fix | `attempt_tokens` − token sampai fix − token panggilan `Finish` |
| Alasan gagal | ditolak sebelum menulis / balasan terpotong saat menulis / fix salah / klaim tidak didukung / lainnya, dari ledger dan verdict |

**Pembacaan dikunci sebelum run.** Ambangnya eksploratif dan dipilih sekarang, bukan setelah melihat data.

- **Budget memang kurang.** Sukses 45k > sukses 30k, **dan** median token sampai fix di 45k berada dalam ±20% dari 30k,
  **dan** sebagian sukses tambahan di 45k punya token sampai fix + `Finish` di atas 30.000. Artinya jalurnya sama,
  hanya tidak muat di 30k.
- **Budget tambahan dihabiskan.**
  - Median token sampai fix atau file dibaca sebelum fix di 45k naik lebih dari 20% dibanding 30k, **dan** sukses
    tidak naik atau naik sedikit (selisih ≤ 1 run). Agen membaca lebih banyak karena bisa.
  - Kalau sukses naik **dan** token sampai fix juga naik lebih dari 20%: keduanya terjadi. Dilaporkan dengan biaya per
    task sukses sebagai penentu nilai.
- Hasil lain dilaporkan apa adanya.
- **Satu klaim palsu adalah regresi kejujuran**, berapa pun suksesnya.

## 3. Cap biaya: kenapa harus berubah, dan bagaimana agar tidak menjadi variabel kedua

Admission mencadangkan `attempt_tokens` × tarif tertinggi per attempt: 30k → $0.30, 45k → $0.45.

Dengan cap kontrak dan config $0.50 per run seperti sekarang:
- di 45k, attempt kedua ditolak setelah attempt pertama menghabiskan lebih dari $0.05 (pengeluaran + $0.45 > $0.50).
  Biaya attempt pertama di seri #2 sekitar $0.05–0.10, jadi lengan 45k praktis hanya mendapat **satu** attempt;
- di 30k, attempt kedua dan ketiga masih muat.

Itu variabel kedua: umpan balik attempt ke-2 adalah mekanisme yang baru saja kita buktikan.

**Usul:** cap per run **$1.00 di kedua lengan**, di config (`budget.max_usd`) dan di kontrak (`limits.max_usd`). Dengan
pengeluaran per attempt seperti di seri #2, tiga attempt muat di kedua lengan. Kontrak repo tetap; lihat 5.

**Cap seri: $5.00, dijamin oleh driver.** Run berikutnya hanya dimulai jika pengeluaran seri + cap per run ≤ $5.00.
Jadi total tidak pernah melewati $5.00, bahkan dalam kasus terburuk.

**Estimasi realistis** (dari seri #2: DONE $0.075–0.095, gagal $0.10–0.13 per run):
- lengan 30k sekitar $0.9;
- lengan 45k sekitar $1.0–1.8. Run yang gagal dua attempt bisa sampai sekitar $0.20.

Totalnya sekitar **$2–3**, jauh di bawah cap seri. Kalau guard seri berhenti lebih awal, perbandingannya tidak
lengkap. Itu dilaporkan sebagai seri yang berhenti, tidak dilanjutkan, dan tidak diulang.

Kasus terburuk teoretis tanpa guard seri adalah 18 × $1.00 = $18.00. Itulah sebabnya guard $5.00 diperlukan.

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
   - **guard cap seri**: run berikutnya dimulai hanya jika pengeluaran + cap per run ≤ cap seri.
   - **Tes:** guard menolak sebelum run yang tidak muat, `series.json` mencatat alasannya, dan lengan yang salah
     petakan ditolak.
4. **`scripts/analyze_series.py`:** diagnostik bagian 2 (token sampai fix dan seterusnya) per run.

Tidak ada perubahan pada harness inti: loop agen, LLMCaller, acceptance, dan umpan balik.

## 6. Yang tidak dilakukan

- Tidak menaikkan budget permanen.
- Tidak mengubah prompt atau umpan balik.
- Tidak menambah completion reserve.
- Tidak mengoptimalkan konteks.
- Kalau 45k membantu, keputusan apakah harga token itu sepadan atau apakah efisiensi konteks lebih tepat diambil
  setelah melihat data. Bukan bagian dari eksperimen ini.
