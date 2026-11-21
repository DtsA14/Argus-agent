# Spec T4a: tombol rencana di chat (`prd approve` dan `queue go`), tanpa apply

Status: **rev 0, belum ditinjau** (Opus sebelum kode, jalur ketat: persetujuan dan uang). Diminta Atha 2026-11-21 ("T3 kalo dilewat dan langsung T4 gimana bro" lalu, sesudah T3 ringan 4 dari 6, "Ok gass"). Ditulis Claude. Menyambung `SPEC_KARTU_SETUJU.md` (kartu rencana hanya baca; "tombol adalah T4", butir M8 di bagian 3) dan `SPEC_CHAT_APP.md` (prepare lalu confirm, 11.3, 11.8, 13.7 butir 9 "never an approve" dikecualikan di sini untuk `prd approve` dan `queue go`, bukan untuk approve draf atau apply).

## 1. Dasar dan batas

**Dasar:** T3 ringan (enam kartu fixture; PENDING "T3 ringan"): Atha menolak kartu rencana yang tujuannya menyimpang dan yang biayanya 5x, tetapi **menerima kartu pasang yang tanda mesinnya merah** (file terlindungi dan di luar issue). Jadi: kartu rencana boleh diberi tombol; tombol apply (T4b) **tidak** dibuka di spek ini.

**Dalam cakupan (dua aksi baru, keduanya diketik atau dipilih manusia, tanpa model):**
1. `prd_approve`: setara `argus prd approve DIR --sha FOLDERSHA`. Membuat antrean `PENDING`. Tidak ada uang yang keluar.
2. `queue_go`: setara `argus queue go QUEUE --sha LISTSHA`. Menyetujui daftar dan **uangnya** (batas antrean). Tidak menjalankan apa pun.

**Di luar cakupan:** `queue step` (drafter), approve draf, apply, buka PR, merge, `prd reply`, `queue retry/close`; semuanya tetap terminal atau operator (keputusan K2 di bawah). Tidak ada model dalam jalur ini.

## 2. Alur dan kartu

Dari tab Kartu, kartu rencana PRD yang ada (`GET /api/approve/prd/<job>`) mendapat satu tombol sesuai keadaannya:
- PRD punya folder yang lolos `prd check` dan belum ada antrean darinya: tombol **"Setujui rencana"** (`prd_approve`).
- Antrean `PENDING` dari PRD itu: tombol **"Jalankan antrean (uang $X)"** (`queue_go`).
Tiap tombol memakai `prepare` lalu `confirm` yang ada. Klien hanya mengirim `{action, job}` (id job PRD; untuk `queue_go` juga id antrean): **tidak ada `sha`, `dir`, atau jumlah uang dari klien**. Server membaca folder dan antrean dari harness, menghitung sha-nya, dan kartu konfirmasi menampilkannya; token terikat digest kartu (11.3); `confirm` membangun ulang kartu dari data hidup dan menolak bila berubah (folder diganti oleh giliran PRD baru, antrean ditutup atau sudah disetujui, repo bergeser).

## 3. Tanda mesin di atas, tombol yang mati secara mekanis (pelajaran T3)

Kartu konfirmasi menaruh **tanda mesin di bagian paling atas**, sebelum tombol, dan bukan di bawah ringkasan hijau. Tanda dan akibatnya:
- **Biaya per issue ≥ 3x acuan** (rasio dari kartu rencana, SPEC_KARTU_SETUJU M1): `queue_go` meminta **alasan yang diketik** (10-500 karakter, aturan `--accept-concerns`: tanpa karakter kontrol atau pola kunci), dicatat di audit dan di antrean. Tanpa alasan, tombol mati.
- **Issue tanpa contoh** (peringatan bagian 3 SPEC_KARTU_SETUJU) dan **catatan baca angka belum segar** untuk item yang punya contoh (M8): sesuai aturan kartu rencana yang ada; `queue_go` mati sampai catatannya segar atau Atha mencentang peringatan tanpa-contoh secara eksplisit.
- **BLOCK dari `prd check`**: kedua tombol mati.
- Tujuan menyimpang tidak bisa ditandai mesin; kartu menampilkan **permintaan Atha kata per kata** berdampingan dengan ringkasan penulis (berlabel tulisan model), dan itu penilaian Atha (T3: ia menangkapnya).
Mekanis berarti server menolak `confirm` (kode 409), bukan hanya tombol disabled di JS.

## 4. Uang dan batas harian

`queue_go` menyetujui uang sampai `max_usd` antrean. Itu **eksposur** 24 jam dan dihitung ke batas harian chat: (a) `argus queue go` mendapat `--via ui` dan mencatat `approved.via`, `approved.at`; (b) `exposure()` mendapat cabang antrean: tiap antrean di `queues_dir` dengan `approved.via == "ui"` dalam 24 jam dihitung `max_usd`-nya; (c) jaring audit (baris `queue_go ok confirm`) seperti riset dan PRD; (d) `check_cap` menolak `prepare` dan `confirm` bila `used + max_usd` melewati batas. `prd_approve` menambah 0. Dengan batas bawaan $2,00: PRD ($1,50) lalu antrean $1,00 sudah melewati batas; **angka ini ditampilkan di kartu** dan batas dinaikkan hanya dengan kata Atha (K3). Pembacaan folder antrean memakai pola `openat`/`O_NOFOLLOW` (13.13 SPEC_CHAT_APP), bukan `open()` biasa.

## 5. Gerbang yang tetap dipegang CLI

Chat hanya menjalankan argv tetap `argus ... prd approve DIR --sha S` dan `argus ... queue go Q --sha S --via ui` (`--jobs-dir`, `--queues-dir`, `--config` seperti aksi lain), tanpa `--key-file` (keduanya tidak memakai model dan tidak butuh kunci; **diverifikasi saat kode**). `DIR` dibangun server dari id job (folder `prd-wN` terakhir, bukan dari klien). Pemeriksaan sha folder, `check`, kunci antrean, penolakan antrean ditutup atau sudah disetujui, dan `rq.new` tetap di CLI; chat tidak menduplikasi.

## 6. Tes wajib (gagal bila jaminannya rusak)

Klien tidak dapat memilih `dir`, `sha`, jumlah uang, atau antrean di luar PRD itu; field tak dikenal 400. Token terikat digest: folder PRD diganti, antrean disetujui atau ditutup, atau config berubah antara prepare dan confirm memberi 409 tanpa spawn. Biaya ≥ 3x tanpa alasan 409; dengan alasan lolos dan alasan tercatat (audit dan antrean). Issue tanpa contoh dan catatan basi menolak `queue_go` di server. Dua `confirm` berturut-turut tidak melewati batas harian. `queue_go` dihitung sebagai eksposur dari direktori antrean, dari pending, dan dari jaring audit (tanpa hitung ganda; di luar jendela 24 jam tidak dihitung). `prd_approve` tidak menambah eksposur. Argv `queue go` memuat `--via ui` dan tidak memuat `--key-file`. Aksi tak dikenal tetap ditolak (dispatch eksplisit, spek mandor 13.9). Pesan alasan tidak pernah ditulis ke audit selain hash. Kartu rencana tanpa folder lolos tidak menampilkan tombol; tombol tidak pernah menampilkan tombol kedua sebelum yang pertama selesai.

## 7. PR (jalur ketat; tinjau Opus spek lalu kode; mutan sekali; precheck; `verify_at`)

- **PR1 (CLI):** `argus queue go --via ui` (rekam `approved.via`, `approved.at`; id antrean dan `--via` divalidasi), tes.
- **PR2 (chat, tanpa UI):** aksi `prd_approve` dan `queue_go` di `chat_actions` (kartu, tanda mesin, alasan, eksposur antrean, audit, dispatch), tes dan mutan.
- **PR3 (UI):** tombol di tab Kartu, tanda mesin di atas, kolom alasan, pin hash statis.

## 8. Keputusan untuk Atha

| | Pertanyaan | Usul Claude |
|---|---|---|
| K1 | Dua tombol terpisah atau satu ("Setujui dan jalankan") | dua: yang pertama gratis, yang kedua uang; sesuai CLI dan T3 |
| K2 | `queue step` (drafter) dari chat ikut? | tidak di spek ini; operator atau terminal; dibahas sesudah T4a dipakai |
| K3 | Batas harian | tetap $2,00; kartu menampilkan "PRD $1,50 + antrean $1,00 = $2,50 > $2,00" bila lewat, naikkan hanya dengan kata Atha |
| K4 | Ambang tanda biaya | 3x acuan (spek kartu), dengan alasan yang diketik |

## 9. Yang belum dicek (rev 0)

Bentuk JSON kartu rencana (`router/approve_cards.py`: bidang untuk "contoh ada atau tidak", "catatan segar", biaya dan rasio) dan apakah tanda M8 sudah dihitung di sana atau perlu dihitung ulang di sisi chat; `rq.list_sha(q)` dan apakah deterministik dari folder (menentukan apakah satu `confirm` dua langkah mungkin, ditolak di K1); apakah `queue go` dan `prd approve` boleh dijalankan tanpa kunci model (`rj.live`); letak `approved` di berkas antrean untuk `exposure()`; apakah chat sudah punya jalur ke `queues_dir` untuk `exposure()` (hari ini hanya `Cards`). Tinjau Opus diminta memeriksa terutama butir ini dan bagian 3-4.
