# Eksperimen live search-value #1: hasil

Seri yang disetujui dijalankan 2026-10-16 di VM, persis sesuai `SEARCH_LIVE_1_PREFLIGHT.md`:
- agen `6de48d5` (main, tree bersih), model `anthropic:claude-sonnet-5-5`;
- urutan c2, b3, a1, a2, b1, c3, b2, c1, a3;
- `attempt_tokens` 30.000, `max_iterations` 3, cap $0.50 per run.

**9 dari 9 run berjalan. Tidak ada `BLOCKED`, `FAILED_BUDGET`, maupun anomali harness. Total $1.0044 dari maksimum
$4.50.** Bukti per run ada di `verification/search-live-1/<urutan>_<run>/`: report, events (ledger per panggilan),
result, verdict per attempt, kontrak beku, diff, `audit.txt`. Ditambah `series.json` dan `analysis.jsonl` (validasi
ulang independen).

## Integritas

- Audit prompt: **109 dari 109 panggilan** cocok dengan prompt sistem efektif kondisinya (A/B `9f9e718c…`, C
  `ee7af58d…`). Tool efektif: A/B lima tool, C empat tool.
- Ledger: setiap panggilan yang dikirim punya `llm_call_started` dan `llm_call`. Penolakan reservasi (2 per run)
  tercatat sebagai `refused` tanpa dikirim. Contoh, a1 attempt 0: sisa 9.942 token dan input 9.905 menyisakan output
  37 token, di bawah `min_output_tokens` 64, jadi ditolak sesuai aturan.
- Benchmark `815a9976…`, kontrak dan fixture tidak berubah selama seri.

## Metrik utama

| | A: search | B: search + kalimat | C: tanpa search |
|---|---|---|---|
| Tingkat sukses task (lolos validasi independen dan acceptance) | **0/3** | **0/3** | **0/3** |
| Biaya per task sukses | tidak terdefinisi (0 sukses) | tidak terdefinisi | tidak terdefinisi |
| Biaya total | $0.3275 | $0.3269 | $0.3500 |
| Tingkat kegagalan jujur | 3/3 | 3/3 | 3/3 |

Semua run berakhir `FAILED_ACCEPTANCE`, stagnan setelah 2 attempt. Kedua attempt berakhir `reservation_exhausted`.
Tidak ada run yang menulis `SUMMARY.json`, jadi tidak ada klaim sama sekali, termasuk klaim palsu.

## Diagnostik

| Run | Search (query) | File dibaca (2 attempt) | Fix di workspace | Validasi ulang (target / unit) |
|---|---|---|---|---|
| a1 | `@step(` | 25 | tidak | gagal / lulus |
| a2 | `@step(` (attempt 2) | 26 | ya, alternatif sah: `resolve_terms` memakai `account_terms` | **lulus** / lulus |
| a3 | `@step(` di `src/steps`, lalu `merge_options(plan, base)` | 26 | tidak | gagal / lulus |
| b1 | `eu`, `late_fee`, `"terms"`, `terms_from` | 20 | ya, akar masalah | **lulus** / lulus |
| b2 | `late_fee`, `terms` di `src/steps` (dua kali) | 18 | ya, akar masalah, tapi helper tak terpakai di `prepare.py` ikut terhapus | **lulus** / lulus |
| b3 | `late_fee`, `"terms"` | 21 | tidak | gagal / lulus |
| c1, c2, c3 | — | 27–29 | ya, akar masalah (`merge_options(base, plan)`) | **lulus** / lulus |

Token per run sekitar 47.000 (dua attempt) di ketiga kondisi: A 47.002, B 47.154, C 48.014 rata-rata. Selisihnya sekitar
2%, di bawah galat estimasi.

**Pola yang sama di keenam run yang memperbaiki bug:**
- Di attempt pertama, agen membaca 3–5 file per langkah, lalu di panggilan ke-5 menulis perbaikan. Di 5 dari 6 run,
  validasinya dijalankan di langkah yang sama; b2 hanya menulis.
- Panggilan berikutnya, untuk membaca hasil validasi dan memanggil `Finish`, butuh input sekitar 9–11 ribu token dan
  ditolak sebelum dikirim.
- Verdict attempt pertama (contoh c2) hanya gagal pada `SUMMARY.json is missing` dan `claims`. Validasinya sendiri lulus.
- Attempt kedua menerima umpan balik itu, tapi agen memulai diagnosis dari awal (`ListFiles`, membaca ulang) dan
  kehabisan reservasi lagi sebelum `Finish`.

## Pembacaan dengan aturan yang dikunci

- **Search tidak mengubah gagal menjadi sukses** pada 30.000: 0/3 di semua kondisi.
- **Penghematan token karena search: sekitar 2%**, di bawah galat. Belum cukup untuk membenarkan kompleksitas tool
  berdasarkan eksperimen ini.
- **A memakai search** di ketiga run, dengan query yang tepat (`@step(`). B mencari lebih sering (2–4 kali) dengan
  query yang lebih umum, dan membaca lebih sedikit file (18–21 vs 25–29).
- Dengan n = 3, kecenderungan "C lebih sering memperbaiki" (3/3 vs 1/3 dan 2/3) tidak bisa disimpulkan. Itu dicatat
  sebagai observasi saja.
- **Model tidak mengikuti strategi yang diprediksi.** Simulasi mengasumsikan 6 file untuk search. Model sungguhan
  membaca 10–17 file berbeda per run, tiga sampai lima per langkah, dengan atau tanpa search.

## Temuan utama (fakta, lalu hipotesis)

**Fakta:** pada 30.000 token per attempt, pengikat hasil eksperimen ini bukan search, melainkan **langkah terakhir**.
- Enam dari sembilan run memperbaiki bug dengan benar dan validasinya lulus, tapi tidak ada yang sempat memanggil
  `Finish`.
- Attempt berikutnya tidak memanfaatkan pekerjaan yang sudah tervalidasi.

**Hipotesis (belum diuji):**
- Dengan perilaku baca seperti ini, task di repo sebesar ini tidak bisa lulus pada 30.000, apa pun ketersediaan
  search-nya.
- Pertanyaan nilai search tidak bisa dijawab di batas operasional ini. Hasilnya didominasi efek budget, persis jebakan
  yang kita hindari di desain.

**Kemungkinan langkah berikutnya, untuk diputuskan; tidak ada yang dikerjakan di PR ini:**
1. Catat hasil ini dan hentikan eksperimen search untuk sekarang. Nilai tambah search belum terbukti.
2. Eksperimen efisiensi pada 60.000 (pertanyaan berbeda, disebut di review), dengan persetujuan biaya terpisah.
3. Desain harness untuk temuan langkah terakhir. Misalnya, menyisakan ruang untuk `Finish` ketika reservasi menipis,
   atau memberi tahu attempt berikutnya bahwa validasi sudah lulus dan hanya ringkasan yang hilang. Ini perubahan
   harness, jadi perlu desain dan review sendiri.
