# M6 pilot 5: simulasi token tanpa biaya (termasuk "agen membaca semua berkas yang terkait")

Status 2026-10-21. Tanpa panggilan model, tanpa biaya. Simulasi terkalibrasi (`scripts/measure_context.py`, token ≈ 407 + 0,3186 × karakter) yang menjalankan loop
agen harness sungguhan dengan model terskrip atas snapshot task (basis `716d1dd`). Skrip: `sim_tokens.py`; keluaran mentah: `sim_raw.txt`. Perkiraan, bukan hasil model nyata.

Task: satu fungsi di `models/pricing.py` (1,3 KB), tetapi lebih berat dari Pilot 4: tes baru `tests/test_peak_window_strict.py` 8,3 KB (±3,1k token) dan penulisan balik
fungsi yang jauh lebih panjang (keluaran ±1k token yang terkirim ulang di tiap langkah berikutnya). Issue 1.596 karakter.

## Hasil attempt pertama

| Skenario (bacaan agen) | `default` 30k | `large` 45k (token terpakai) |
|---|---|---|
| `search_first`: cari `def is_peak`, baca `pricing.py`, sunting, validasi, Finish | selesai (±17k) | selesai (±17k) |
| `minimal`: baca `pricing.py` + tes strict, sunting, validasi, Finish | selesai (±23k) | selesai (±23k) |
| `typical`: `ListFiles` + `pricing.py` + tes strict + `tests/test_peak_window.py` (5 KB) | **ditolak di Finish** (±27k) | selesai (±38k) |
| `typical_plus_models`: seperti typical + `tests/test_models.py` (7 KB) | **ditolak** (langkah 4) | selesai, **hampir habis** (±44,2k dari 45k) |
| `minimal_one_fix`: satu penyuntingan salah, validasi gagal, perbaikan | **ditolak** (±24k, langkah 5) | selesai (±43k) |
| `read_all`: mengejar semua pemakai dan tes (`harness/llm.py`, `test_models`, `test_llm_wrapper`, `test_calibration`, `test_judge`, `calibrate_judge`) | **ditolak** | **ditolak** (±44k, sebelum menyunting selesai) |
| `read_all_batched`: sama, semua bacaan dalam satu langkah | **ditolak** di langkah 3 (permintaan ±37,7k) | **ditolak** setelah menyunting, sebelum validasi |

## Bacaan

- Jalur yang mengikuti issue (baca `pricing.py` dan tes strict) muat dengan lega di kedua profil. Satu bacaan ekstra yang masuk akal (`tests/test_peak_window.py`, tes Pilot 4 yang
  harus tetap lulus) sudah menolak attempt di `default`; di `large` muat.
- `minimal_one_fix` (satu siklus perbaikan) tidak muat di `default` dan muat di `large` dengan sisa sempit (±2,4k). `typical_plus_models` muat di `large` dengan sisa ±0,8k: **ruangnya tipis**.
- Agen yang mengejar semua pemakai tidak muat di profil mana pun; dicatat sebagai risiko, tidak dihilangkan.
- Biaya per attempt (perkiraan simulasi): ±$0,05–0,11 pada jalur yang selesai. Reservasi `large` $0,45.

## Admisi (attempt diterima bila terpakai + reservasi ≤ cap; paling banyak `max_iterations` 3)

| Profil / cap | Attempt |
|---|---|
| `default` 30k ($0,30) pada $0,50 (config global) | sampai 3, tetapi attempt pertama sering ditolak sebelum Finish (typical, one_fix) |
| `large` 45k ($0,45) pada $0,50 | **1 attempt**: tidak ada attempt kedua |
| `large` 45k pada cap pilot $0,75 | 2 attempt bila attempt pertama menghabiskan ≤ $0,30 (jalur yang selesai: ya); ke-3 bila dua attempt ≤ $0,30 total |

## Untuk D5 (keputusan reviewer)

Rekomendasi saya, tanpa menaikkan apa pun secara otomatis: `large` dengan cap pilot $0,75 (`config_pilot5.yaml`, satu nilai berbeda dari `config.yaml`). Alasan: pada `default`
dua dari lima skenario wajar (membaca satu tes yang sudah ada; satu siklus perbaikan) sudah ditolak, sedangkan pada `large` muat meski dengan sisa tipis untuk skenario terberat.
`large` pada $0,50 hanya memberi satu attempt, jadi tidak disarankan. Reservasi `large` mengurangi attempt efektif yang bisa diterima di bawah cap global; itu alasan cap pilot dipakai, dan
dilaporkan. Skenario "baca semua pemakai" tetap risiko yang jujur: bila run berakhir `reservation_exhausted`, itu dicatat sebagai kegagalan, tanpa menaikkan budget.
