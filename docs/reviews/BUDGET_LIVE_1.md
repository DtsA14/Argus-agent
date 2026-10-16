# Eksperimen budget 30k vs 45k: hasil

Seri yang disetujui dijalankan 2026-10-17 di VM, persis sesuai `BUDGET_LIVE_1_PREFLIGHT.md`:
- agen `99b7dd8` (main, tree bersih), urutan berpasangan dengan seed 20261017;
- cap $1.00 per run dan $5.00 per seri.

**18 dari 18 run berjalan. 9 dari 9 pasangan `complete`. Tidak ada henti, rerun, attempt yang ditolak cap, maupun
balasan terpotong. Total $1.7525.** Bukti: `verification/budget-live-1/`, yang berisi per run report, events/ledger,
result, verdict, kontrak beku, diff, SUMMARY, dan audit, ditambah `series.json`, `analysis.jsonl` (validasi ulang
independen dan diagnostik), serta `failure_trace.txt` (teks model per langkah).

## Integritas

- **Audit prompt: 18 dari 18 run, setiap `prompt_hash` cocok (0 mismatch).** Prompt sistem efektif sesuai varian: A/B
  `9f9e718c…`, C `ee7af58d…`.
- **Biaya dari ledger:** guard dan laporan memakai `usd_billed` dari ledger setiap run, dan `usd_complete` true di
  18/18.
- **Setiap DONE divalidasi ulang secara independen** di sandbox: unit dan target lulus di 12/12.
  - Keduabelasnya adalah perbaikan satu baris di akar masalah: `merge_options(base, plan)` di `src/steps/prepare.py`.
  - Klaim (`file_changed`, `tests_pass`, `issue_fixed`) cocok dengan bukti.
  - Tidak ada klaim palsu.
- Semua kegagalan tanpa klaim, karena tidak ada `SUMMARY.json`.

## Metrik utama

| | 30k | 45k |
|---|---|---|
| **Tingkat sukses task** | 3/9 | **9/9** |
| per varian A / B / C | 0/3, 1/3, 2/3 | 3/3, 3/3, 3/3 |
| **Biaya total** (ledger) | $0.9029 | $0.8496 |
| **Biaya per task sukses** | $0.3010 | **$0.0944** |
| **Tingkat kegagalan jujur** | 6/6 | – (tidak ada kegagalan) |
| Total token | 390.111 | 353.761 |

**Berpasangan:** 45k lebih baik di 6 pasangan, seri di 3 (keduanya DONE), dan 30k lebih baik di 0.

Sebagai pembanding dari luar desain: seri #2 (30k, PR #62) mencapai 4/9. Lengan 30k di sini 3/9, konsisten.

## Bukti pendukung (deskriptif, bukan klasifikasi otomatis)

| Pasangan | 30k | 45k |
|---|---|---|
| c1, b2 | fix di panggilan ke-5 (sekitar 23,9 ribu dan 24,7 ribu token), `Finish` ditolak, selesai di attempt 2 lewat umpan balik → DONE | fix di titik yang sama (sekitar 23,9 ribu dan 24,7 ribu), `Finish` di attempt yang sama (total sekitar 34 ribu) → DONE |
| c2, b1 | ditolak sebelum menulis fix di kedua attempt → gagal | fix sekitar 24,0 ribu dan 24,7 ribu, `Finish` di attempt yang sama (sekitar 34 ribu) → DONE |
| a2, b3 | ditolak sebelum menulis di kedua attempt → gagal | fix sekitar 29,9 ribu dan 31,6 ribu, `Finish` di attempt yang sama (sekitar 41 ribu) → DONE |
| c3 | fix sekitar 24,2 ribu, selesai di attempt 2 → DONE | fix sekitar 30,4 ribu, `Finish` sekitar 40 ribu → DONE |
| a1 | ditolak sebelum menulis → gagal | fix sekitar 29,8 ribu, `Finish` ditolak (input 11,8 ribu, sisa 4,5 ribu), selesai di attempt 2 lewat umpan balik → DONE |
| a3 | ditolak sebelum menulis → gagal | fix sekitar 41,2 ribu (panggilan ke-7), `Finish` ditolak, selesai di attempt 2 lewat umpan balik → DONE |

**Yang terlihat:**
- Di pasangan yang di kedua lengan menulis fix (c1, b2), **token sampai fix praktis sama**: sekitar 23,9 ribu dan
  24,7 ribu. Budget tambahan tidak dipakai untuk membaca lebih banyak **sebelum** fix. Ia dipakai untuk **menyelesaikan**
  dalam attempt yang sama.
- **Tidak ada sukses 45k yang total attempt-nya muat di 30.000.** Semua di antara 33,9 ribu dan 41,6 ribu. Empat menulis
  fix di atas 29,8 ribu, yaitu titik yang di 30k sudah ditolak.
- Dua sukses 45k (a1, a3) tetap butuh attempt kedua. Di sana **umpan balik berbasis verdict (M3) menyelesaikannya**.
  Kedua mekanisme saling melengkapi.
- Kegagalan 30k sama dengan pola M3: agen sudah membaca file bug dan kontraknya, lalu ditolak tepat sebelum menulis.

**Yang tidak terlihat:** tidak ada tanda budget tambahan "dihabiskan".
- Lengan 45k memakai **lebih sedikit** token total (353.761 vs 390.111) dan lebih murah per run, karena kegagalan 30k
  menghabiskan dua attempt penuh.
- Satu-satunya fix yang jauh lebih mahal adalah a3 (41,2 ribu, satu langkah baca tambahan), dan itu tetap selesai.

## Kesimpulan dan batasnya

**Fakta, untuk fixture dan model ini:**
- Dengan 45.000 token per attempt, tingkat sukses naik dari 3/9 ke 9/9.
- Biaya per task sukses turun dari $0.30 ke $0.09, dan biaya total turun.
- Tidak ada klaim palsu.
- Pada fixture ini, 30.000 token per attempt **kurang**: jalur diagnosis dan perbaikannya sama, tapi menyelesaikannya
  dalam satu attempt butuh 34–42 ribu token.

**Batas:**
- Satu fixture (`ledger`, 48 modul), satu model (Sonnet 5.5), 9 pasangan.
- Ini sinyal diagnostik yang kuat dan konsisten (6–0–3 secara berpasangan), bukan estimasi kemampuan Argus secara
  umum.
- Ia juga tidak membuktikan bahwa 45k tepat untuk repo lain. Repo yang lebih kecil (Eval Set v1) selesai jauh di
  bawah 30k.

**Yang tidak diputuskan di sini:** apakah default `attempt_tokens` dinaikkan, atau apakah efisiensi konteks dikerjakan.
Itu keputusan terpisah setelah review. Datanya menunjukkan **harga** budget tambahan pada fixture ini negatif, karena
lebih murah per sukses. Pertanyaan yang tersisa adalah bagaimana memilih budget per task tanpa menebak.
