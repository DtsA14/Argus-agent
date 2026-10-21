# M6 pilot 5 (usulan): `is_peak` gagal tertutup untuk jendela puncak yang tidak valid

Status 2026-10-21: **spesifikasi untuk review. Belum ada tes, tes pembeda, patch referensi, simulasi, atau coder.** Sesuai arahan reviewer: acceptance dibekukan, tes pembeda
dan patch referensi disiapkan dulu, baru coder dijalankan. Task ini diajukan karena Pilot 4 (2 dari 2 `DONE`, patch byte-identik) memperlihatkan celah: jendela tanpa kunci
`utc_hours` diam-diam menjadi "bukan puncak" (`False`) alih-alih error. Basis: `main` (`88a4a91`), yang sudah berisi `is_peak` hasil Pilot 4.

Pertanyaan eksperimen: bisakah Argus menangani aturan yang lebih ketat, yaitu **menolak input tidak valid secara eksplisit** alih-alih menghasilkan nilai bawaan yang tampak sukses?
Task ini tidak otomatis "lebih baik" karena lebih sulit; nilainya ada pada acceptance yang dibekukan sebelum coder jalan.

## 1. Mengapa aman memakai exception di `is_peak` (diperiksa di kode)

`is_peak` dipakai lewat `multiplier()`/`cost_usd()` di `harness/llm.py` dan langsung di `scripts/calibrate_judge.py`. Jendela berasal dari `config.yaml` dan statis selama run.
- `LLMCaller._output_cap` (dipanggil **sebelum** permintaan dikirim) memanggil `multiplier(...)` dan `_usd(...)`, sehingga jendela yang tidak valid menghasilkan error **sebelum ada uang keluar**;
  panggilan `_usd` sesudah respons memakai jendela yang sama yang sudah lolos sekali. Hasil: gagal tertutup tanpa menyentuh jaminan buku besar (`llm_call_started` sebelum kirim, biaya dibebankan).
- `calibrate_judge.py` memanggil `is_peak` sebelum run dimulai: gagal sebelum biaya.
- Tidak ada perubahan di `harness/**`: validasi tinggal di `models/pricing.py`. Mengubah tempat validasi (mis. saat load config) di luar scope.

## 2. Perilaku yang ditetapkan (butuh persetujuan reviewer)

Error: kelas baru `WindowError(ValueError)` di `models/pricing.py` (tidak memakai `ConfigError` dari `models/registry.py` karena `registry` mengimpor `pricing`: siklus). Pesan menyebut masalah
dan nilai yang salah.

Jendela yang **falsy** (`None`, `{}`) tetap berarti "provider ini tidak punya jendela puncak": `False`, bukan error (provider tanpa jendela adalah konfigurasi yang sah).

Untuk jendela tidak-falsy, `is_peak` menolak (raise `WindowError`) bila:

| # | Kasus | Contoh |
|---|---|---|
| V1 | jendela bukan dict | `[[22, 4]]`, `"1-4"` |
| V2 | tidak ada kunci `utc_hours` (kasus yang ditemukan Pilot 4) | `{"weekdays_only": true}` |
| V3 | `utc_hours` bukan list/tuple | `"1-4"`, `5`, `None` |
| V4 | elemen bukan pasangan `[start, end]` dua bilangan bulat (bool ditolak) | `[1]`, `[1, 2, 3]`, `["1", 4]`, `[1.5, 4]`, `[true, 4]` |
| V5 | di luar rentang: `start` harus 0..23, `end` harus 0..24 | `[24, 4]`, `[-1, 4]`, `[1, 25]` |
| V6 | `weekdays_only` ada tetapi bukan bool (string `"false"` dianggap benar secara diam-diam) | `"false"`, `1` |

Tetap sah dan **tidak berubah**: `utc_hours: []` (jendela kosong: tidak pernah puncak), `start == end` (jendela kosong), `end == 24`, jendela yang melewati tengah malam, beberapa jendela,
`weekdays_only` pada tanggal UTC dari `now`, konversi zona, kunci tambahan yang tidak dikenal (diabaikan). Jendela puncak di `config.yaml` tetap valid (tes penjaga memuat config sungguhan).

## 3. Keputusan untuk reviewer

1. **D1.** Jenis error (`WindowError(ValueError)`) dan pesan yang menyebut nilai salah: setuju?
2. **D2.** `utc_hours: []` sah (tidak pernah puncak), bukan error?
3. **D3.** Apakah `now` tanpa zona waktu (naive) ikut ditolak? Sekarang `astimezone` memperlakukannya sebagai waktu lokal mesin (diam-diam salah). Menolaknya menambah satu kasus (V7) dan berisiko
   bila ada pemanggil yang memberi `now` naive (saya cek: pemanggil produksi memakai `datetime.now(timezone.utc)`; tes yang ada memakai `utc(...)`). Usulan saya: **masukkan** sebagai V7, karena inti task ini
   adalah tidak menerima input yang tampak sukses; tetapi ini menambah risiko di kode harga, jadi keputusan reviewer.
4. **D4.** Batas rentang V5 (`start` 0..23, `end` 0..24) dan penolakan bool/float: setuju?
5. **D5.** Profil: `large` + cap pilot $0,75 seperti Pilot 3a/4, atau `default` (task ini lebih besar dari Pilot 4: tes strict ±6 KB)? Putusan setelah simulasi token (termasuk skenario "agen membaca semua tes").

## 4. Batas perubahan

- **Writable:** `models/pricing.py` saja. **Protected:** semuanya yang lain, termasuk `tests/**` (tes lama `tests/test_peak_window.py` harus tetap lulus), `config.yaml`, `harness/**`, `scripts/**`.
- Menyentuh kode harga: patch referensi manusia, tes pembeda, mutan, `verify.sh` penuh, patch agen dibaca manusia.

## 5. Acceptance (rancangan, belum ditulis)

Berkas baru `tests/test_peak_window_strict.py` (target ≤ 7 KB, tanpa modul data):
- **Wajib (merah di baseline karena assertion):** satu tes per kelas V1..V6 (+V7 bila D3), masing-masing `pytest.raises(WindowError)` dengan beberapa nilai salah dan memeriksa bahwa pesan menyebut nilainya;
  satu tes bahwa error muncul dari `is_peak`, `multiplier` dan `cost_usd` (jalur harga) bukan hanya dari fungsi tertentu; satu tes bahwa jendela salah di tengah daftar jendela benar tetap ditolak.
- **Pembeda (menjaga perilaku sah tetap sama):** pada seluruh grid jendela valid (`start` 0..23, `end` 0..24, `weekdays_only` hidup/mati, 7 hari x 24 jam, 3 zona) hasil `is_peak` sama dengan fungsi
  acuan yang ditanam di tes; pada grid nilai tidak valid (di luar rentang, tipe salah) semuanya raise. Jendela `config.yaml` sungguhan tetap valid dan hasilnya tidak berubah.
- **Penjaga (lulus di baseline):** semua kasus sah di atas; tes lama tetap lulus (validasi regresi).

Setelah D1..D5 diputuskan: tes, patch referensi, mutan, simulasi token (dengan skenario "baca semua tes"), draft check, `verify.sh`; baru lalu preflight dan keputusan live. Tidak ada coder sebelum itu.

## 6. Keputusan reviewer (2026-10-21) dan rumusan yang dikunci

- **D1** setuju: `WindowError(ValueError)` di `models/pricing.py`, pesan menyebut masalah dan nilai yang salah; bukan `ConfigError` (siklus impor).
- **D2** setuju: `utc_hours: []` sah dan berarti tidak ada jam puncak; tidak diubah menjadi error.
- **D3** setuju: `now` tanpa zona waktu ditolak (V7, `WindowError`), kewajiban zona waktu didokumentasikan di docstring; waktu UTC dan zona eksplisit tetap benar. Temuan pemeriksaan kontrak: docstring
  `is_peak` sekarang tidak menyebut zona waktu; semua pemanggil produksi dan tes sudah memberi `now` berzona; `astimezone` pada waktu naive memakai zona waktu mesin (di mesin UTC+7,
  `23:00` naive menjadi `16:00 UTC`), jadi hasil bergantung pada mesin tanpa error.
- **D4** setuju: `start` bilangan bulat 0..23, `end` bilangan bulat 0..24; bool dan float ditolak. Perilaku valid yang ada dipertahankan: lintas tengah malam, beberapa jendela, `end == 24`, `start == end` kosong.
- **D5** belum diputuskan; menunggu simulasi token. Profil tidak dinaikkan otomatis; bila reservasi mengurangi jumlah attempt efektif, itu dilaporkan.

Rumusan tambahan yang saya pakai (tinggal dibantah reviewer bila tidak sesuai):
1. Jendela falsy (`None`, `{}`) tetap `False` tanpa memeriksa `now` (perilaku yang ada; tidak diperluas). `now` hanya diperiksa untuk jendela tidak-falsy.
2. **Semua** elemen `utc_hours` dan `weekdays_only` divalidasi sebelum dievaluasi: jendela salah di belakang jendela yang sudah cocok tetap ditolak (tanpa hubung singkat), supaya konfigurasi salah tidak lolos hanya karena jamnya kebetulan cocok.
3. `weekdays_only` yang ada tetapi bukan bool (termasuk `None`) ditolak; tidak ada kunci berarti `False` seperti sekarang.
4. Kunci tambahan yang tidak dikenal tetap diabaikan.
