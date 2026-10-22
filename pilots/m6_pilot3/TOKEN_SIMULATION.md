# M6 pilot 3: simulasi token tanpa biaya (profil 30k vs 45k)

Status 2026-10-21. Tidak ada panggilan model nyata, tidak ada biaya. Keputusan profil dan cap **belum diambil**: menunggu
angka ini dan preflight, lalu persetujuan reviewer.

Metode: `scripts/measure_context.py` (penghitung terkalibrasi, token ≈ 407 + 0,3186 × karakter) menjalankan loop agen harness dengan
model terskrip atas snapshot task, dengan reservasi profil `default` (30.000 token, $0,30) dan `large` (45.000 token, $0,45).
Lima rencana baca-tulis, hasil attempt pertama:

| Rencana | 30k | 45k |
|---|---|---|
| cautious (baca semua berkas terkait dulu) | ditolak di langkah 4 | ditolak di langkah 4 |
| lean_with_tests (baca tes terlindungi, tulis, validasi) | ditolak di langkah 3 | ditolak di langkah 4, setelah dua penulisan |
| lean_no_tests (tidak membaca tes) | tidak dijalankan | semua penulisan selesai dan satu validasi, tetapi belum `Finish` |
| split_3a (pembaca + dua pemeriksa) | tidak dijalankan | sampai validasi pertama |
| split_3b (agregator) | ditolak di langkah 3 | tidak dijalankan |

Catatan: pada 3b model palsu bisa melampaui reservasi lewat token keluaran (`FAILED_BUDGET`), yang tidak terjadi pada model nyata yang
dibatasi `max_tokens`. Itu artefak simulasi.

## Temuan

- Task ini terikat anggaran oleh desain. Berkas tes terlindungi (±18 KB, ±6k token) harus dibaca karena berisi golden dan definisi
  laporan, lalu terkirim ulang di **setiap** langkah (input langkah memuat semua hasil tool sebelumnya).
- Jalur bersih satu attempt butuh kira-kira 50–65k token, lebih bila ada siklus perbaikan. Profil 45k pun menolak di attempt pertama
  pada hampir semua rencana yang membaca tes.
- Aritmetika admission (attempt diterima bila terpakai + reservasi ≤ cap, cap = min(config $0,50, kontrak)):
  - `default` pada $0,50: sampai 3 attempt (tiap attempt dibatasi 30k), tetapi sangat mungkin tiap attempt ditolak sebelum selesai.
  - `large` pada $0,50: hanya 1 attempt.
  - `large` pada $0,75: sampai ±3 bila tiap attempt menghabiskan ≤ ±$0,15.
  - `large` pada $1,00: 2 attempt atau lebih.

## Opsi untuk diputuskan reviewer (bukan keputusan saya)

1. Pecah menjadi 3a (pembaca + dua pemeriksa, tes golden saja) dan 3b (agregator) dengan masing-masing kontrak sendiri.
2. Tetap satu task, profil `large` dengan cap lebih tinggi dari $0,50, setelah preflight.
3. Perkecil bacaan wajib (memindahkan definisi laporan dari docstring tes ke berkas yang lebih kecil), sehingga profil `default` cukup.

Profil `large` 45k dan cap $1 **tidak** disetujui; tidak ada coder yang dijalankan.
