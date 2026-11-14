# Spec DRAFTER-STYLE: the appended test block is written like the file's own tests (prompt only)

Status: **DITARIK (withdrawn) 2026-11-14, tidak dibangun.** Review Opus: NO-GO sebagaimana ditulis; gue memeriksa dua klaim kuncinya di kode dan keduanya benar (bagian 4). Spec ini disimpan sebagai catatan supaya perbaikan yang sama tidak diusulkan lagi tanpa membaca alasannya. Ditulis Claude.

## 0. Masalah (terukur)

Sesudah APPEND-TESTS (#506), 8 dari 8 draf batch 3 menambah tesnya ke `tests/test_more.py` (APPEND_MEASUREMENT.md). Pembacaan buta Opus (APPEND_READ.md): tes draf bernilai 7 B dan 1 D, tes maintainer 6 A; kelemahan yang konsisten pada blok draf adalah pembungkus `try/except Exception -> AssertionError` yang tidak dipakai berkas itu, dan kelas TestCase baru yang berdiri sendiri.
Dihitung langsung dari 8 blok (`jobs/j20261114_*/runs/*/draft.json`, blok = isi berkas baru dikurangi berkas lama): **7 dari 8 blok memuat `try:` (15 pembungkus di total)**, 3 blok memakai `assertRaises`, **0 memakai `subTest`**, 8 dari 8 menulis tepat satu kelas baru, 0 fungsi tingkat atas.

## 1. Yang bisa dan tidak bisa diperbaiki dengan prompt

Aturan append menaruh blok **di akhir berkas** (`codetask/drafter.py:127`: "added at the end of the existing file"), jadi prompt **tidak dapat** membuat tes masuk ke kelas TestCase yang sudah ada (itu butuh `insert_into`, pekerjaan terpisah dan lebih besar; **klaim gue sebelumnya bahwa prompt bisa melakukannya keliru**). Yang bisa: gaya blok baru itu.

Perubahan (hanya teks prompt di `codetask/drafter.py`, aturan "Put new tests where the repository keeps its tests"): satu kalimat tambahan pada aturan itu dan satu pada deskripsi field `append`, yang bunyinya, intinya:
1. Bila tes berkas itu adalah kelas `unittest.TestCase`, tulis satu kelas TestCase baru dan **jangan** fungsi tingkat atas `test_*` (pytest menjalankannya, `python -m unittest` tidak melihatnya; maintainer menjalankan unittest).
2. Namai kelas dan metodenya seperti tetangganya (baca kelas tes terdekat untuk fungsi yang sama sebelum menulis) dan pakai alat yang mereka pakai (`assertEqual`, `assertRaises`, `subTest`).
3. **Jangan** membungkus pemanggilan dengan `try/except` untuk mengubah pengecualian menjadi kegagalan: biarkan pengecualiannya menggagalkan tes, atau pakai `assertRaises` bila pengecualian memang yang diharapkan.

Tidak berubah: aturan append, batas ukuran, `new_tests`, apa pun di `acceptance/`, semua pemeriksaan harness. Tidak ada pemeriksaan baru yang menolak draf (prompt bisa diabaikan model; pemeriksaan harness atas `try/except` atau fungsi tingkat atas di berkas unittest sengaja **tidak** dibangun di sini: butuh bukti dulu bahwa prompt tidak cukup, dan menolak draf yang benar adalah risiko).

## 2. Verifikasi

- **Tes** (`tests/test_drafter_style.py`): tiap aturan di atas hadir di system prompt dan di deskripsi `append`; aturan lama (append, `new_tests`, `__main__`) tetap ada; prompt tetap muat batas yang sudah dijaga tes prompt yang ada. Tes ini mengunci **teks**, bukan perilaku model.
- **Mutan** (`verification/drafter_style_mutants.py`): tiap kalimat aturan dihapus atau dibalik harus membuat tes gagal.
- Satu `verify_at` penuh; satu review independen atas spec ini.
- **Efek pada perilaku tidak dibuktikan oleh tes**: hanya oleh pengukuran draf-saja (sekitar $0,08, 8 isu batch 3, tanpa approve dan tanpa agen), yang butuh **persetujuan uang Atha** dan dijalankan **setelah** merge; sampai saat itu perubahan ini berlabel "belum terukur". Ukurannya otomatis, tanpa pembaca: jumlah `try:` per blok (dasar: 7 dari 8 blok, 15 total), jumlah blok dengan `subTest`/`assertRaises` (dasar: 0 dan 3), fungsi tingkat atas (dasar: 0), dan tetap 8 dari 8 draf yang diterima harness dan yang menambah ke berkas lama.
- **Mundur**: satu commit dikembalikan (hanya teks).

## 3. Batas yang diketahui

Satu repositori, satu model (DeepSeek flash), n = 8, satu run tiap isu: hitungan, bukan laju. Penempatan di kelas yang ada (`insert_into`) tidak disentuh. Aturan 1 menganggap berkas itu unittest; pada repositori pytest murni model tetap memakai fungsi (kalimatnya bersyarat). Model bisa mengabaikan prompt.

## 4. Mengapa ditarik (review Opus 2026-11-14, diperiksa Claude)

1. **Pembungkus `try/except -> AssertionError` bukan kebiasaan buruk; itu dituntut harness.** Prompt Argus sendiri (`codetask/drafter.py:244-246`) memerintahkannya, dan pemeriksaan merah menolak tes wajib yang gagal bukan lewat assertion (`acceptance/draft.py:393-396`, `NOT_ASSERTION_HINT` di `:368`). Pada kode lama, `peekable[int]` melempar TypeError, `replace(default_arg=)` TypeError, `mi.synchronized` AttributeError, `interleave_evenly([])` IndexError, `reversed()` pada rentang kosong IndexError, `r[index]` dan `r.index` IndexError dan ValueError: tanpa pembungkus, tes wajibnya gagal bukan lewat assertion dan drafnya ditolak. Dari 15 `try:` di 8 blok, hanya sekitar 1 atau 2 bisa ditulis lain (satu `try/except/else` menjadi `assertRaises`, satu `hasattr` lebih dulu). Maintainer tidak memerlukannya karena tidak ada gerbang merah-lewat-assertion di PR mereka. **Ketidakcocokan gaya ini adalah akibat dari gerbang itu, sebuah keputusan desain, bukan cacat prompt.**
2. **Aturan 3 (draf pertama) bertentangan dengan aturan 244** dan akan menaikkan penolakan draf dan putaran `ReviseDraft` (biaya dan tingkat penerimaan turun). Spec tidak menyebut aturan 244 di daftar "tidak berubah".
3. **Aturan 1 (fungsi tingkat atas)**: 0 dari 8 blok melakukannya; tidak ada yang diperbaiki. Alasannya ("maintainer menjalankan unittest") tidak berlaku bagi harness, yang menjalankan `python -m pytest`.
4. **Sisa yang nyata kecil**: `subTest` dipakai 31 kali dan `assertRaises` 112 kali di `tests/test_more.py` lama, tetapi blok draf memakai `subTest` 0 kali (beberapa blok memakai loop `assertEqual` dengan pesan). Itu pantas satu kalimat bersyarat suatu hari, bukan perubahan strict-lane tersendiri; sebelum itu perlu bukti bahwa ia bernilai.
5. **Tidak ada batas panjang prompt yang dipin oleh tes** (klaim di draf tentang "batas yang dijaga tes prompt" menunjuk ke ketiadaan).

**Yang tetap benar dan tetap terbuka:** kelas TestCase baru di akhir berkas (7 dari 8 kasus bernilai B karena itu dan gaya) hanya bisa diperbaiki dengan `insert_into` (tes masuk ke kelas yang ada), pekerjaan strict-lane tersendiri dengan spec sendiri. Ukuran yang lebih baik untuk itu nanti: jumlah blok yang masuk ke kelas yang ada, bukan jumlah `try:`.
