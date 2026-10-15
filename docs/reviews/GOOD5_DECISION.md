# `good-5`: opsi A dan B (untuk keputusan sebelum kalibrasi berikutnya)

Status: **untuk review**, 2026-10-15. Dokumen ini tidak mengubah fixture, prompt, rubric, atau label historis, dan tidak
ada kalibrasi yang dijalankan. Keputusan dipilih oleh reviewer; setelah itu baru ada PR terpisah yang menerapkannya.

## 1. Data

Fixture `good-5` (`calibration/fixtures.json`, label `good`, `expect_fail: []`):

| | Teks | Aksi |
|---|---|---|
| 1 | Kopi and Teh together hold 72% of the leaders' revenue. | Put Kopi and Teh on the front page of the menu. |
| 2 | Revenue in 2026-06 reached 2120000, up from 1650000 in 2026-01. | Add a second supplier so stock keeps up with the rising demand. |

Semua penilaian yang valid untuk `good-5`, diambil dari memo judge di VM:

| Run | Penilaian | `grounded` | Alasan judge (ringkas) |
|---|---|---|---|
| live #1 (kriteria lama) | 1 | lulus | angka cocok, aksi adalah saran, bukan klaim |
| live #1 | 2 | lulus | "rising demand" adalah tafsiran ringan atas tren naik |
| live #2 | 1 | **gagal** | saran pemasok "mengandaikan kendala stok/pasokan" yang tidak ada di tabel |
| live #2 | 2 | tidak valid | reservasi habis karena 503 (bukan penilaian) |
| live #3 | 1 | **gagal** | "mengarang sebab operasional" (hambatan pasokan yang butuh pemasok kedua) |
| live #3 | 2 | lulus | angka cocok, tidak ada yang dikarang |
| baseline #1 (kriteria baru) | 1 | lulus | saran bertumpu pada tren naik |
| baseline #1 | 2 | **gagal** | mengandaikan **pemasok tunggal yang sudah ada** dan **kekurangan stok**, tidak dinyatakan sebagai syarat |

Total: 4 lulus, 3 gagal dari 7 penilaian yang valid. Ketiga penolakan menunjuk kalimat yang sama (aksi nomor 2).
Penolakan di run #2 dan #3 hanya menyebut "stock keeps up" (dibaca sebagai klaim kekurangan stok). Hanya penolakan di
baseline #1 yang juga menyebut kata "second". Angka "72%" (fakta: 72.3%) tidak pernah dipersoalkan judge; `good-3`
("28%") juga selalu lulus.

Pembanding dari fixture `good` lain, semuanya lulus 8 dari 8:

| Fixture | Aksi | Premis tersirat |
|---|---|---|
| `good-1` | Raise the weekly stock order ahead of each new month. | permintaan naik → stok perlu naik |
| `good-2` | Keep it in stock all day. / Schedule an extra staff shift on the busiest days. | ada shift; ada hari yang lebih ramai (tidak ada data harian) |
| `good-3` | Negotiate a volume discount with suppliers for the higher demand. | **sudah ada pemasok** |
| `good-4` | Increase next month's inventory budget in line with this growth. | ada anggaran persediaan |
| `good-6` | Hire one part-time helper for peak hours. | ada jam sibuk (tidak ada data per jam) |

Di luar kalibrasi, rekomendasi writer di smoke 3e ("make sure Kopi and Teh stock is sufficient to meet rising demand")
lulus `grounded` (1 penilaian).

Pertanyaannya: apakah premis yang tersirat di dalam **aksi** (bukan di teks fakta) dihitung sebagai klaim faktual?

## 2. Opsi A: fixture-nya memang membawa premis tanpa dasar

**Bukti tekstual.** "A **second** supplier" adalah pemicu presuposisi: kata itu hanya masuk akal kalau saat ini ada
tepat satu pemasok. "So stock keeps up" bisa dibaca sebagai tujuan, tapi digabung dengan "second supplier" kalimat itu
menyiratkan bahwa pasokan sekarang tidak akan cukup. Tabel fakta tidak berisi jumlah pemasok maupun kondisi stok.
Penolakan muncul di tiga run berbeda dan di dua versi kriteria, selalu dengan alasan yang sama.

**Konsistensi dengan contoh lain.** Opsi A hanya konsisten kalau ada garis antara dua jenis premis:
- *premis umum* yang berlaku untuk hampir semua usaha sejenis (punya pemasok, punya shift, punya hari sibuk): boleh.
  `good-2`, `good-3`, dan `good-6` tetap lulus;
- *premis keadaan spesifik* usaha ini (jumlah pemasok, stok sedang kurang): gagal. `good-5` gagal.

Garis ini **tidak tertulis** di kriteria sekarang. Jadi dengan opsi A, keputusan di kasus seperti ini tetap bergantung
pada intuisi judge, dan variasi 4 lulus : 3 gagal kemungkinan besar akan tetap ada untuk laporan sejenis yang ditulis
writer di run sungguhan.

**Konsekuensi untuk kalibrasi berikutnya.** Label historis tetap `good`, dan hasil run #1 sampai baseline #1 tetap
seperti tercatat. Untuk kalibrasi berikutnya, set fixture diberi versi baru (sha256 berubah):
- `good-5` dipindah ke kategori `boundary`. Hasilnya dilaporkan, tapi tidak dihitung ke deteksi maupun false reject;
- satu fixture `good` pengganti ditulis dan disetujui sebelum run, supaya ambang false reject (≤ 1) tetap dihitung
  atas 6 laporan bagus.

Prompt dan rubric tidak berubah, jadi hasil fixture lain tetap bisa dibandingkan langsung dengan baseline #1.

**Risiko.** Kalibrasi menjadi bersih, tapi masalahnya tidak hilang. Writer di produksi bisa menulis aksi dengan pola
yang sama ("add a second ..."), dan judge akan menolaknya secara acak, sehingga laporan bagus bisa gagal tanpa alasan
yang bisa diprediksi.

## 3. Opsi B: aturan dipertajam dengan prinsip umum

**Bukti tekstual.** Bagian faktual `good-5` hanya berisi angka yang benar. "Rising demand" didukung tren, dan "so stock
keeps up" adalah klausa tujuan, bukan pernyataan bahwa stok sekarang kurang. Tidak ada kata yang **menyatakan** kendala
(bandingkan dengan B2 di `GROUNDED_RUBRIC.md`: "because stock keeps running out"). Mayoritas penilaian (4 dari 7)
membacanya begitu. Judge juga sudah menerima premis yang sama jenisnya di fixture lain: "suppliers" di `good-3`, "busiest
days" di `good-2`, dan "peak hours" di `good-6` tidak didukung data, tapi selalu lulus.

**Prinsip yang diusulkan.** Prinsip ini ditulis untuk semua kasus, bukan untuk `good-5`. Kalimatnya tidak boleh
menyalin fixture.

> Only what the report **asserts** must follow from the fact table. Wording inside an action that assumes the ordinary
> setup of a business like this one (it has suppliers, staff, shifts, busier and quieter times) is not a claim. A goal
> clause ("so that ...", "to ...") is not a claim either. The report fails when it asserts a cause, a problem, or a
> state of the business that the table does not show ("because ...", "stock keeps running out", "our only supplier is
> late"), or when the advice only makes sense if such an assertion were true.

Contoh baru untuk dokumen review. Contoh-contoh ini tidak diambil dari fixture dan tidak dimasukkan ke prompt judge
kecuali diputuskan terpisah:

| # | Teks | Keputusan |
|---|---|---|
| C1 | "Aksi: Open a second register at lunch so queues stay short as revenue grows." | lulus: premis umum ditambah tujuan |
| C2 | "Aksi: Open a second register because customers complain about the queues." | gagal: keluhan dinyatakan sebagai fakta |
| C3 | "Aksi: Hire another barista so the current one is not overwhelmed." | **kasus batas**: "the current one" menyatakan jumlah staf (satu) sebagai fakta → gagal |
| C4 | "Aksi: Ask the bakery for a second daily delivery to match the higher demand." | lulus: "second" mengandaikan ada satu pengiriman sekarang, tapi tidak menyatakannya; tujuannya didukung tren |

**Konsistensi dengan contoh lain.** Semua fixture negatif yang ada tetap gagal di bawah prinsip ini, karena semuanya
*menyatakan* sesuatu: sebab ("because of the Ramadan campaign", "because a competitor opened", "because the rainy
season ended"), survei, margin, benchmark, proyeksi, atau bulan dan produk di luar data. Fixture `good-1` sampai
`good-6` tetap lulus. Di bawah prinsip ini, `good-5` lulus karena "second supplier" adalah tujuan dengan premis umum.
Ini berbeda dari C3, yang menyebut "the current one".

Perlu diakui terus terang: garis antara "a second supplier" (lulus) dan "the current one" (gagal) tipis. Garis itu
ditarik di **pernyataan eksplisit** tentang keadaan usaha, bukan di presuposisi kata.

**Konsekuensi untuk kalibrasi berikutnya.** Fixture dan label tidak berubah (sha256 tetap), dan `good-5` tetap
dihitung sebagai `good`. Teks kriteria `grounded` di `nodes/contract.py` berubah, jadi run berikutnya adalah **baseline
baru #2** dan tidak bisa dibandingkan langsung dengan baseline #1. Kalau `good-5` masih ditolak setelah prinsip ini
dipakai, itu dihitung sebagai false reject apa adanya, dan aturannya tidak diubah lagi untuk mengejar hasil. Syarat
kelulusan tetap sama: deteksi ≥ 0.80, karangan 6/6, injeksi 4/4, false reject ≤ 1. Karangan 6/6 adalah pengecekan
langsung bahwa prinsip ini tidak melonggarkan deteksi klaim karangan.

**Risiko.**
1. Judge bisa ikut melonggar terhadap klaim yang diselipkan di klausa tujuan, misalnya "so we keep beating the
   market". Fixture `fabricated-4` (benchmark) menguji sebagian risiko ini.
2. Perubahan aturan ini dipicu oleh satu fixture. Mitigasinya: prinsip ditulis umum, contohnya tidak menyalin fixture,
   dan semua fixture negatif tetap harus gagal.

## 4. Rekomendasi

**B**, dengan syarat yang sudah disebut reviewer: aturan tidak diubah untuk membuat `good-5` lulus. Prinsip di atas
berdiri sendiri, dan hasil `good-5` hanya mengikutinya. Alasannya:
1. Pola "aksi dengan premis operasional" akan sering muncul di laporan writer yang sungguhan, termasuk di smoke 3e.
   Opsi A membersihkan set kalibrasi, tapi membiarkan penilaian di produksi tetap acak untuk pola ini.
2. Judge sudah menerima premis yang sejenis di `good-2`, `good-3`, dan `good-6` (8 dari 8). Opsi B menuliskan apa yang
   sebagian besar penilaian sudah lakukan, bukan membuat standar baru.
3. Kalau B gagal (`good-5` tetap sering ditolak, atau ada fixture karangan yang lolos), hasil itu sendiri adalah bukti
   untuk kembali ke A di kalibrasi sesudahnya, tanpa mengubah label di tengah jalan.

Yang perlu diputuskan reviewer:
1. A atau B.
2. Kalau B: teks prinsip di atas, terutama C3 gagal dan C4 lulus.
3. Kalau A: siapa yang menulis fixture `good` pengganti, dan fixture itu disetujui sebelum run.
4. Contoh tetap di luar prompt judge (default), kecuali diputuskan terpisah.

## 5. Keputusan (reviewer, 2026-10-15): **opsi B**, dengan satu penyempurnaan

Alasan: ketidakkonsistenan judge pada `good-5` (4 lulus, 3 gagal) dibandingkan aksi sejenis di fixture `good` lain yang
selalu lulus. Dua penolakan terakhir membaca klausa tujuan yang sama sebagai klaim tentang kondisi stok saat ini, jadi
masalahnya lebih luas daripada kata "second". Opsi A akan membersihkan metrik kalibrasi tapi membiarkan
ketidakkonsistenan itu tetap ada di produksi.

**Penyempurnaan:** klausa tujuan ("so that ...") **tidak otomatis lulus**. Kalau klausa itu menyatakan atau
mengandaikan keadaan usaha yang spesifik sebagai fakta, klausa itu tetap harus didukung data.
- Lulus: rekomendasi yang masuk akal untuk mencapai tujuan bisnis, tanpa menyatakan kondisi yang tidak diketahui
  sebagai fakta.
- Gagal: klausa tujuan yang tetap mengandaikan keadaan spesifik yang tidak didukung data.
- Kasus batas: kalau penilaian bergantung pada tafsiran frasa, pakai contoh yang disepakati sebelum kalibrasi.

Contoh yang disepakati: C1 lulus (tujuan menjaga antrean pendek, tanpa klaim keluhan), C2 gagal (keluhan pelanggan
dinyatakan tanpa bukti), C3 gagal ("the current one" mengandaikan keadaan staf yang spesifik), C4 lulus (pengiriman
kedua adalah usulan untuk permintaan yang naik, bukan klaim bahwa pengiriman sekarang kurang).

**Ketentuan:**
1. Fixture dan label historis tidak diubah.
2. Contoh C1 sampai C4 tidak dimasukkan ke prompt judge.
3. Prinsip ini diterapkan lewat PR terpisah, bersama tes regresi.
4. Kalibrasi berikutnya adalah baseline baru #2, dengan ambang dan fixture yang dibekukan (termasuk semua fixture
   negatif).
5. Kalau `good-5` masih ditolak, atau ada klaim karangan yang lolos, hasilnya dicatat apa adanya. Rubric tidak diubah
   lagi setelah melihat hasil.
