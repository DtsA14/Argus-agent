# Pilot router #2: DeepSeek thinking dibanding non-thinking, task yang sama

2026-10-23. Task yang sama dengan pilot #1 (`pilots/router_v0/p1/issue.txt`, `argus list`), commit dasar yang sama
(`26befdc`), model yang sama (DeepSeek V4.1 Flash). Satu-satunya perbedaan: `config_thinking.yaml`, yaitu `config.yaml`
dengan `thinking: enabled` untuk `coder` dan `drafter` (didukung PR #168: `reasoning_content` dikirim balik dan disimpan
di memo). Atas permintaan Atha ("sekarang cobain pake thinking"; "catat juga waktunya, bandingin sama non-thinking").

## Hasil

| | Non-thinking (`j20261023_031205_d0f8`, pilot #1) | **Thinking** (`j20261023_062122_c7a4`) |
|---|---|---|
| Run drafter sampai lolos | 3 (d1 `context_limit`, d2 `reservation_exhausted`, d3 lolos)¹ | **1** |
| Waktu run drafter | 15 + 17 + 53 = 85 detik | 148 detik |
| Panggilan model drafter | 39 | 13 |
| Output drafter (di antaranya thinking) | 5.797 (0) | 24.282 (19.246) |
| Biaya drafter | $0,0560 | $0,0482 |
| Agen | `DONE`, 2 attempt, 67 detik, 19 panggilan | `DONE`, 2 attempt, 74 detik, 17 panggilan |
| Output agen (di antaranya thinking) | 2.143 (0) | 4.982 (2.466) |
| Biaya agen | $0,0090 | $0,0215 |
| **Biaya job** | **$0,0650**¹ ($0,0792 dengan d4) | **$0,0696** |
| **Waktu mesin** (run drafter + agen) | 152 detik | 222 detik |
| Waktu dinding, job dibuat sampai `REVIEW_READY` | ±2 jam 42 menit (termasuk 4 PR perbaikan harness di sela-selanya) | **8 menit 18 detik** (termasuk ±4 menit menunggu approve) |
| Perintah live dari Atha | 5 (`code`, `redraft` ×3, satu tidak sengaja, `approve`) | **2** (`code`, `approve`) |
| Paket review | valid | valid |

¹ Tanpa d4, yaitu `redraft` yang dijalankan tidak sengaja ($0,0143, 44 detik).

Catatan perbandingan yang adil: run non-thinking d1 dan d2 berjalan **sebelum** perbaikan harness PR #166 dan #167
(batas input, pengingat langkah, hanya tool submit di 3 langkah terakhir), sedangkan run thinking sudah memakainya. Jadi
sebagian keunggulan "1 run" bisa datang dari perbaikan itu, bukan dari thinking. Pembanding yang setara adalah d3
(non-thinking, sudah dengan perbaikan): lolos dalam 2 submit dan 53 detik, sementara thinking lolos dalam 2 submit dan
148 detik.

## Kualitas

- **Draf thinking lebih teliti.** Selain 6 tes wajib, ada tes penjaga
  `test_status_reports_the_same_spend_the_ledgers_record` yang mengunci cara `status` menghitung biaya. Ini persis
  celah yang di versi non-thinking membuat agen mengubah `spent_nano`. Catatan `unverifiable`-nya juga jujur dan
  relevan (tidak ada regresi yang bisa jalan di sandbox, `--jobs-dir` bawaan tidak dites, dan seterusnya).
- **Patch agen thinking lebih bersih.** Penghitung biaya dipecah menjadi `runs_spent_nano(runs, stages)`, lalu dipakai
  bersama oleh `spent_nano` (status) dan `list`. **Cara menghitung biaya tidak berubah.** Patch non-thinking (yang sudah
  di `main`) membuat `spent_nano` ikut menjumlahkan run yang tidak tercatat (hanya bisa menambah).
- Agen thinking juga berakhir attempt 0 dengan `context_limit` (input > 40.000 per panggilan, profil `large_usd`)
  setelah kodenya sudah benar; attempt 1 hanya `Finish`. Sama seperti non-thinking yang habis langkah di attempt 0.

## Status

Patch thinking **tidak diterapkan**: fitur `argus list` sudah ada di `main` dari pilot #1 (non-thinking), dan dua patch
untuk fitur yang sama tidak bisa sama-sama masuk. Versi thinking disimpan di `live/review/changes.patch` sebagai
pembanding.

## Usulan (keputusan Atha)

1. **Nyalakan thinking untuk `drafter`** sebagai bawaan. Biayanya setara, perintahmu lebih sedikit, dan drafnya lebih
   teliti. Satu sampel saja, tapi arahnya konsisten dengan pilot-pilot Sonnet (thinking bawaan).
2. **`coder`: thinking juga, atau tetap non-thinking.** Agen non-thinking lebih murah ($0,009 vs $0,022) dan sama-sama
   `DONE`, tapi patch thinking lebih bersih. Sampelnya terlalu kecil untuk memutuskan dari angka saja.
3. Opsional: ganti `spent_nano` di `main` ke versi thinking (`runs_spent_nano`), supaya `status` dan `list` pasti
   menghitung hal yang sama. Itu perubahan manual kecil, bukan hasil agen.
