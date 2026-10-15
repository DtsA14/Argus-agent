# Catatan desain: provider kelebihan beban (HTTP 503) tanpa melonggarkan aturan budget

Status: **draf untuk review**, belum diimplementasikan (permintaan GPT, 2026-10-15). Dasar: run kalibrasi live #2
(`docs/reviews/REVIEW_3D.md`).

## Masalah
- Run #2 jatuh di jam sibuk DeepSeek: 24× HTTP 503 "Service is too busy", ditolak dalam 0,1–0,2 detik.
- Wrapper (`harness/llm.py`) menganggap 503 sebagai error sementara: diulang sampai `llm.attempts` = 3, dengan backoff
  eksponensial dari `llm.base_delay` = 1 detik dan `Retry-After` dihormati kalau ada.
- Setiap percobaan yang gagal **ditagih worst case** (`llm.failed_attempt_charge: worst_case`, aturan 2a): input + batas
  output = ±9.400 token di reservasi penilaian yang 20.000. Dua 503 sudah menghabiskannya, dan percobaan ketiga ditolak
  sebelum dikirim. Hasilnya aman (fail closed, tanpa biaya berlebih), tapi kalibrasinya tidak selesai dengan andal.

Dua hal harus dipisah: **kebijakan retry** (kapan dan seberapa sering mencoba lagi) dan **kebijakan reservasi** (berapa
yang ditagih untuk percobaan yang gagal). Usulan di bawah hanya menyentuh yang pertama. Aturan 2a tidak dilonggarkan
tanpa bukti penagihan dari provider.

## Opsi, diurutkan dari yang paling murah dan aman

### 1. Kalibrasi tidak dijalankan di jam sibuk (operasional + guard kecil)
- Runner kalibrasi menolak mulai di jam sibuk provider judge (`peak_windows` di config sudah ada), kecuali dengan
  `--allow-peak` yang eksplisit.
- Run #1 di luar jam sibuk: 0 error 503. Run #2 di jam sibuk: 24.
- **Tidak menyentuh budget**, hanya menunda. Tes: penolakan di jam sibuk, lolos di luar jam sibuk, dan `--allow-peak`.
- `--allow-peak` **hanya** melewati pemeriksaan jadwal (catatan GPT). Batas biaya $1.00, gate per penilaian, dan circuit
  breaker (opsi 2) tetap berlaku. Tes: dengan `--allow-peak`, batas biaya dan breaker tetap menghentikan run.

### 2. Circuit breaker di runner kalibrasi
- Kalau K error sementara berturut-turut terjadi lintas penilaian (usul K = 4), runner **berhenti** dengan status
  `incomplete: provider unavailable`, bukan terus mengubah gangguan provider menjadi verdict tidak valid satu per satu.
- Run yang tidak lengkap tetap **tidak lulus** (aturan 3.4), jadi standarnya tidak turun. Yang berubah: uang tidak
  terbuang, dan hasilnya jujur menyebut penyebabnya.
- **Tidak menyentuh budget.** Tes: berhenti tepat setelah K berturut-turut, hitungan di-reset oleh panggilan yang
  berhasil, dan status `incomplete`.

### 3. Backoff lebih panjang khusus untuk 503 / 429
- Misalnya mulai 5 detik dan maksimum 60 detik untuk 503/429 tanpa `Retry-After`, tetap dengan jitter.
- Jumlah percobaan tidak bertambah, jadi worst case per penilaian **tidak berubah**. Yang bertambah hanya waktu tunggu,
  sehingga peluang provider sudah pulih lebih besar.
- Perlu dicek apakah jeda panjang aman terhadap `max_seconds` (soft limit) dan timeout per role.
- Tes: jeda yang dipakai untuk 503 tanpa `Retry-After`, dan `Retry-After` tetap menang kalau ada.

### 4. Bukti penagihan sebelum membahas aturan 2a (bukan perubahan kode)
- Cocokkan dasbor penggunaan DeepSeek untuk jendela run #2 (01:23–01:31 UTC, 2026-10-15) dengan ledger: apakah 503
  ditagih?
- Ledger tetap konservatif (**$0.336615**). Angka "$0.090646 untuk penilaian yang berhasil" adalah **perkiraan**, bukan
  tagihan yang terkonfirmasi (koreksi GPT).
- Hanya kalau dokumentasi atau tagihan provider menunjukkan 503 tidak ditagih, perubahan aturan 2a untuk "ditolak sebelum
  diproses" boleh dibahas, sebagai review terpisah dan dengan tesnya sendiri.

### Yang tidak diusulkan
- **Menaikkan estimasi token per penilaian** (misalnya 40.000) hanya demi retry. Itu tidak memperbaiki ketersediaan
  provider, menaikkan worst case per penilaian, dan bisa membuat gate $1.00 menolak lebih banyak penilaian (catatan GPT).
- **Menganggap 503 gratis** tanpa bukti penagihan.

## Usul urutan
1 dan 2 lebih dulu: kecil, tidak menyentuh budget, dan langsung membuat kalibrasi lebih andal. 3 kalau 503 masih muncul di
luar jam sibuk. 4 jalan paralel sebagai pengecekan data, tanpa kode.

## Data yang sebaiknya ikut dicatat mulai sekarang
- Header `Retry-After` dan header terkait beban pada respons 503 (sekarang hanya pesan error yang tersimpan).
- Jam UTC tiap run kalibrasi dan apakah jatuh di jam sibuk (sudah bisa dibaca dari `ts`, tapi belum diringkas).
