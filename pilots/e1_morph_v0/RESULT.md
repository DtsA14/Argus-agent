# Pilot e1_morph v0: claim checker e1 di Morph fp8 (2026-11-07)

Atha 2026-11-07 ("go live buat morph"). Pertanyaan: apakah Morph fp8 (DeepSeek V4.1 Flash, harga datar $0,022/$0,40,
tanpa diskon) setara DeepInfra fp8 untuk e1? Sama dengan `pilots/e1_effort_v0`: salinan job laporan A dan B di
`~/morph_jobs` (`build_jobs.py`), config salinan dengan pin `openrouter:deepseek/deepseek-v4.1-flash` = `[morph/fp8]`,
lainnya config.yaml sesudah #351 (effort low, harga list 0,20/0,60 sebagai max_price). Dua run per laporan. Run pertama
ditolak sebelum kirim ($0): stage butuh kunci DeepSeek dan OpenRouter.

## Hasil

| laporan | run | sama dengan rujukan | beda (rujukan → Morph) | reasoning | waktu | tagihan nyata | ledger |
|---|---|---|---|---|---|---|---|
| A (17) | m1 | 16/17 | P16 SUPPORTED → PARTIAL | 8.734 | 63 s | $0,0041 | $0,0079 |
| A | m2 | 15/17 | S, P7 PARTIAL → SUPPORTED | 15.816 (3 panggilan) | 155 s | $0,0084 | $0,0150 |
| B (13) | m1 | 11/13 | P1, P12 PARTIAL → SUPPORTED | 2.382 | 28 s | $0,0021 | $0,0050 |
| B | m2 | 13/13 | - | 3.783 | 25 s | $0,0018 | $0,0028 |

Semua dilayani Morph (`upstream_served`). **55/60.** Tagihan nyata total $0,0165; ledger $0,0307 (batas atas, #351).
Pembanding (`e1_effort_v0`, DeepInfra, n = 1): effort low 30/30 ($0,0071 + $0,0033); default ulang 25/30.

## Bacaan (n kecil)

- Morph tidak terbukti setara: 4 dari 5 beda adalah kelonggaran (PARTIAL yang benar jadi SUPPORTED), jenis kesalahan
  yang paling merugikan untuk checker. Tetapi DeepInfra low baru diukur sekali, dan default DeepInfra sendiri pernah
  25/30, jadi selisih ini bisa variasi antar-run, bukan provider.
- Hemat kecil: output Morph $0,40 vs DeepInfra $0,42 (output yang dominan), jadi tagihan per laporan hanya sekitar 30-40%
  lebih murah, di bawah $0,005 per laporan.
- Usul Claude: pin tidak diubah. Bila ingin cadangan untuk 429 DeepInfra, Morph boleh di belakang DeepInfra (harga config
  tetap). Membedakan provider dari variasi butuh beberapa run DeepInfra low lagi (sekitar $0,02); tidak mendesak.
