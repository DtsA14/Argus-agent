# M6 pilot 4: simulasi token tanpa biaya (termasuk "agen membaca semua berkas tes")

Status 2026-10-21. Tanpa panggilan model, tanpa biaya. Simulasi terkalibrasi (`scripts/measure_context.py`, token ≈ 407 + 0,3186 × karakter)
yang menjalankan loop agen harness sungguhan dengan model terskrip atas snapshot task. Skrip: `sim_tokens.py`; keluaran mentah: `sim_30000.txt`,
`sim_45000.txt`. Ini perkiraan; model nyata bisa menempuh jalan lain (3a: bacaan ekstra mengubah hasil).

Task: satu fungsi di `models/pricing.py` (1,3 KB); berkas tes baru 5 KB (`tests/test_peak_window.py`, tanpa modul data). Issue 1.216 karakter.

## Hasil attempt pertama (token terpakai / langkah penutup)

| Skenario (bacaan agen) | Profil `default` 30k | Profil `large` 45k |
|---|---|---|
| `search_first`: cari `def is_peak`, sunting, validasi, Finish | selesai, ±10k | selesai |
| `minimal`: baca `pricing.py` + tes baru, sunting, validasi, Finish | selesai, ±16k | selesai |
| `minimal_one_fix`: seperti minimal, satu penyuntingan salah lalu perbaikan | selesai, ±27k (hampir habis) | selesai |
| `typical`: `ListFiles` + `pricing.py` + tes baru + **`tests/test_models.py`** (7 KB) | **ditolak di Finish** (±23k terpakai, langkah ke-5 butuh >30k) | selesai, ±32k |
| `read_all`: mengejar semua pemakai `is_peak` dan semua tes yang menyebutnya, satu berkas per langkah (`harness/llm.py`, `test_models.py`, `test_llm_wrapper.py`, `test_calibration.py`, `test_judge.py`, `calibrate_judge.py`) | **ditolak** sebelum menyunting (±21k) | **ditolak** sebelum menyunting (±35k) |
| `read_all_batched`: sama, semua bacaan dalam satu langkah | **ditolak** di langkah ke-3 (permintaan ±34,6k) | menyunting, lalu **ditolak** sebelum validasi |

## Bacaan

- Jalur yang mengikuti issue ("hanya `is_peak`; tidak ada berkas lain yang perlu dibaca") muat dengan lega di `default`: 10–27k.
- **Satu bacaan ekstra yang masuk akal (`tests/test_models.py`, 7 KB) sudah cukup untuk menolak attempt di `default`**, karena riwayat dikirim ulang di
  tiap langkah. Itu persis pola 3a. Di `large` muat (±32k).
- Agen yang mengejar semua berkas terkait tidak muat di kedua profil. Ini risiko yang dicatat, bukan dihilangkan; run yang berakhir
  `reservation_exhausted` dilaporkan sebagai kegagalan jujur, tanpa menaikkan budget.
- Biaya per attempt: ±$0,03–0,12 (angka simulasi). Cap uang tidak menjadi pembatas; reservasi token yang menjadi pembatas.

## Pilihan profil (untuk keputusan reviewer)

| Pilihan | Admisi | Catatan |
|---|---|---|
| `default` pada $0,50 (config global) | sampai 3 attempt (tiap attempt dipesan $0,30; kenyataannya ±$0,05–0,12) | tanpa konfigurasi khusus; gagal bila agen membaca satu-dua berkas ekstra |
| `large` pada cap pilot $0,75 (seperti 3a, `config_pilot4.yaml` salinan `config.yaml` dengan satu nilai) | 2–3 attempt | muat untuk bacaan "typical"; tetap gagal untuk "read_all"; butuh konfigurasi khusus dan persetujuan cap |
| `large` pada $0,50 | 1 attempt | tidak disarankan: tidak ada attempt kedua |

Rekomendasi saya: `large` + cap pilot $0,75, karena 3a menunjukkan bahwa agen cenderung membaca lebih dari yang dibutuhkan dan satu bacaan ekstra saja
sudah menolak attempt di `default`. Biaya nyatanya tetap kecil (di bawah $0,15 per run). Ini keputusan reviewer.
