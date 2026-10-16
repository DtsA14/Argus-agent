# Pengukuran B: berapa banyak file yang muat dalam satu attempt (tanpa model sungguhan)

2026-10-16. Biaya model nol. Alat ukurnya `scripts/measure_context.py`. Tujuannya menjawab "berapa besar repo yang
mungkin muat dengan konfigurasi sekarang", **bukan** "apakah agen mampu menavigasinya": model palsu mengikuti pola baca
yang ditentukan, ia tidak memilih file sendiri.

## 1. Kalibrasi token (dari run live yang sebenarnya)

Percakapan setiap panggilan model di live #2–#6 (20 panggilan) dibangun ulang dari memo. Rekonstruksinya **terbukti
tepat**: key langkah LLM yang dihitung ulang ditemukan di memo untuk setiap langkah. Karakternya lalu dihitung dengan
cara yang sama seperti harness (`harness.llm._text` ditambah skema tool), dan dibandingkan dengan token input yang
ditagih Anthropic.

Rasio karakter per token **naik** seiring percakapan memanjang (2,30 → 3,08). Itu tanda ada biaya tetap per panggilan.
Model linear yang cocok:

**token input ≈ 407 + 0,3186 × karakter** (sekitar 3,14 karakter per token di atas biaya tetap 407 token).
Galat rata-rata 88 token, galat terburuk 9,4%. Semua angka di bawah adalah **estimasi ±10%** berdasarkan kalibrasi ini,
bukan hitungan tokenizer provider.

## 2. Simulasi (jalur harness yang sama)

Yang dipakai: loop agen asli (`codetask.agent`), `LLMCaller` asli (reservasi, penolakan sebelum mengirim), tool asli
(path jail), memo, dan ledger. Yang diganti hanya dua: model palsu yang menjalankan pola tertentu (`ListFiles` →
`ReadFile` per batch → `WriteFile` satu file → `RunValidation` → `Finish`), dan penghitung token yang memakai model
kalibrasi di atas. Batas sama dengan run live: `attempt_tokens` 30.000 (jumlah input + output **semua** panggilan dalam
satu attempt) dan `max_steps` 12.

File sintetis berisi kode Python yang wajar, ukuran 1.000 karakter (setara fixture sekarang, sekitar 1 KB per modul)
dan 3.000 karakter (modul ukuran biasa). Pola baca: 1 file per langkah, 5 per langkah, atau semua sekaligus (pola yang
dipakai agen di live #4–#6).

### Jumlah file terbesar yang masih selesai (attempt berakhir `finished`)

| Ukuran file | 1 per langkah | 5 per langkah | Semua sekaligus |
|---|---|---|---|
| ~1 KB | **5** | **10** | **20** (total 29.361, nyaris batas) |
| ~3 KB | **3** | **5** | **5** |

Di atas angka itu, attempt berakhir `reservation_exhausted`: harness menolak panggilan berikutnya sebelum mengirim,
karena input yang diperlukan tidak lagi muat di sisa reservasi.

### Contoh pertumbuhan (estimasi)

- 1 KB, semua sekaligus, 20 file: input per panggilan 2.171 → … → 8.757; total 29.361 dalam 5 panggilan.
- 1 KB, 1 per langkah, 10 file: setelah 9 file terbaca dan 10 panggilan (total 26.954), panggilan berikutnya butuh
  input sekitar 4.519 dan ditolak.
- 3 KB, semua sekaligus, 30 file: membaca semuanya membuat panggilan **berikutnya** butuh input sekitar 30.916. Itu
  sendiri sudah melebihi seluruh reservasi, jadi ditolak tepat setelah membaca.

## 3. Yang ditunjukkan data

1. **Pengikatnya adalah pengiriman ulang yang kumulatif, bukan ukuran satu panggilan.** Setiap langkah mengirim ulang
   seluruh percakapan, termasuk isi file yang sudah dibaca, dan semuanya dihitung lagi ke batas 30.000. Membaca
   sedikit-sedikit justru paling mahal: dengan 1 file per langkah, isi file pertama ditagih ulang di setiap langkah
   berikutnya.
2. **Kapasitas efektif konfigurasi sekarang kecil:** sekitar 15–20 KB isi file kalau dibaca sekaligus, dan jauh lebih
   kecil kalau dibaca bertahap. Repo sungguhan biasanya jauh lebih besar, jadi task B (repo besar) dengan konfigurasi
   ini hampir pasti berakhir `reservation_exhausted`. Ini sesuai perkiraan sebelumnya, sekarang dengan angka.
3. **Task sejauh ini aman:** semua fixture berukuran 3–7 KB, dan agen membacanya sekaligus, cocok dengan pemakaian yang
   terukur di live (10.679–20.225 token).

## 4. Batas pengukuran ini

- Pola baca ditentukan oleh naskah, jadi tidak mencerminkan pilihan model sungguhan. Agen sungguhan bisa membaca lebih
  sedikit (live #6: 5 dari 7 modul), atau lebih banyak.
- Output model disederhanakan (argumen tool ditambah 20 token). Model sungguhan bisa menulis lebih panjang.
- Hitungan token adalah estimasi dari kalibrasi pada 20 panggilan (galat ≤ 9,4%).

## 5. Pilihan yang bisa didukung data ini (belum diputuskan, tidak dikerjakan)

- **Tool pencarian** (grep dalam path jail), supaya agen tidak perlu membaca file untuk menemukan tempat yang relevan.
- **Strategi konteks:** membuang isi file lama dari percakapan, atau meringkasnya. Ini menyentuh memo dan crash-resume,
  karena key langkah bergantung pada isi percakapan.
- **Batas yang dihitung berbeda**, misalnya biaya berbasis USD dengan prompt caching. Isi yang dikirim ulang ditagih
  jauh lebih murah sebagai cache read, sedangkan batas token yang sekarang menghitung semuanya penuh.
- **Menaikkan `attempt_tokens`.** Karena pertumbuhannya kumulatif, kenaikan linear hanya menambah sedikit file.
