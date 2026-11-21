# Spec T4a: tombol rencana di chat (`prd approve` dan `queue go`), tanpa apply

Status: **rev 1** (tinjau Opus 2026-11-21: GO WITH CHANGES, empat penghalang B1-B4 dan tujuh catatan besar M1-M7; amandemennya di bagian 10, mengikat dan menggantikan bagian 1-9 bila bertentangan). Belum disetujui untuk dibangun penuh: PR1 (CLI) boleh jalan; PR2 menunggu keputusan batas harian (K3). Diminta Atha 2026-11-21 ("T3 kalo dilewat dan langsung T4 gimana bro" lalu, sesudah T3 ringan 4 dari 6, "Ok gass"). Ditulis Claude. Menyambung `SPEC_KARTU_SETUJU.md` (kartu rencana hanya baca; "tombol adalah T4", butir M8 di bagian 3) dan `SPEC_CHAT_APP.md` (prepare lalu confirm, 11.3, 11.8, 13.7 butir 9 "never an approve" dikecualikan di sini untuk `prd approve` dan `queue go`, bukan untuk approve draf atau apply).

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

`queue_go` menyetujui uang sampai `max_usd` antrean. Itu **eksposur** 24 jam dan dihitung ke batas harian chat: (a) `argus queue go` mendapat `--via ui` dan mencatat `approved.via`, `approved.at`; (b) `exposure()` mendapat cabang antrean: tiap antrean di `queues_dir` dengan `approved.via == "ui"` dalam 24 jam dihitung `max_usd`-nya; (c) jaring audit (baris `queue_go ok confirm`) seperti riset dan PRD; (d) `check_cap` menolak `prepare` dan `confirm` bila `used + max_usd` melewati batas. `prd_approve` menambah 0. Dengan batas bawaan $2,00: PRD ($1,50) lalu antrean $1,00 sudah melewati batas; **angka ini ditampilkan di kartu** dan batas dinaikkan hanya dengan kata Atha (K3). Pembacaan folder antrean memakai pola `openat`/`O_NOFOLLOW` (11.13 SPEC_CHAT_APP), bukan `open()` biasa.

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

## 10. Amandemen dari tinjau Opus (2026-11-21, GO WITH CHANGES; mengikat)

1. **B1: antrean terikat ke folder yang ditunjukkan kartu.** Klien hanya mengirim `{action, job}`: **tanpa id antrean**. Server menurunkan satu antrean dengan syarat: `q.prd.sha` = `folder_sha` giliran terakhir, realpath `q.prd.dir` = `jobs_dir/<job>/prd-<giliran>`, folder tidak SUPERSEDED, `_same_jobs_dir(q)`, tiap `issue-n.md` cocok `issue_sha256`, `q.max_usd` = `max_usd` giliran, jumlah item sama, tidak ditutup dan belum disetujui. Digest memuat id antrean, **list_sha penuh**, `max_usd`, `job_cap`, commit12, judul item. Argv memakai sha **64 heks penuh**.
2. **B2: M8 berarti `domain_read.kind == "ok"`** untuk tiap item yang punya contoh (`counts.calls > 0`); `fresh` tidak cukup (True juga untuk `concerns`). `one`, `stale`, `error`, `none`, `tidak_terbaca`, `concerns` menolak `queue_go`.
3. **B3: "BLOCK" tidak bisa dihitung saat prepare** (menjalankan git, melanggar 11.10). `prd_approve` ditolak server hanya atas fakta yang dibaca: job PRD bukan `AWAITING_HUMAN` atau `spawner.busy`, giliran `stale`, folder SUPERSEDED, sha folder tidak cocok catatan giliran, antrean belum selesai di repo itu (dibaca lewat fd dari `queues_dir`). Pemeriksaan CLI (termasuk HEAD bergeser) tetap gerbang BLOCK saat `confirm`: exit 2 menjadi 409. Untuk `queue_go`, B1 menggantikan "BLOCK".
4. **B4: alasan satu rumah.** PR1 menambah `queue go --reason-file F` (atau `--reason=TEXT` satu token), divalidasi oleh `apply._accepted_reason` yang dipindah ke modul bersama; disimpan sebagai `approved.reason`; audit hanya memuat `sha256(alasan)`; alasan masuk digest kartu; `reason` yang dikirim untuk kartu yang tidak membutuhkannya 400. (Menggantikan "di audit dan di antrean" bagian 3.)
5. **M1: batas harian.** Uang antrean `min(5, n x code_max_usd)` (`prd_job.py:63-65`, `code_max_usd` $1,00): PRD dengan 2 issue atau lebih sudah ditolak di batas $2,00. **K3 diputuskan Atha sebelum PR2** (usul Claude: naikkan `chat.daily_cap_usd` ke $7,00; pagar, bukan pemakaian: pemakaian nyata job sekitar $0,04; atau `chat.queue_daily_cap_usd` terpisah). Kartu menampilkan angkanya terang-terangan.
6. **M2: eksposur antrean.** `audited_jobs` punya varian antrean (`QUEUE_ID`, lexists pada direktori antrean, baris audit `ok:confirm` memuat `queue` dan `usd`); satu kunci `seen` `("go", qid)` untuk pindai direktori, pending, dan jaring; queue.json rusak atau `approved.via == "ui"` dengan `at` tak terbaca memberi 503 (satu antrean rusak menahan semua aksi berbayar chat; dinyatakan); tidak memakai `_queue_rows` (pemangkasan `SCAN_QUEUES` menghitung kurang); antrean tertutup tetap dihitung 24 jam; persetujuan dari terminal (tanpa `via`) tidak dihitung; **batas yang diketahui:** antrean terus berjalan sesudah jendela 24 jam; `queue_step` dari chat kelak menambah 0. Tidak ada hitung ganda dengan job code (`kind: code` tanpa `via`, diabaikan `exposure()`) maupun dengan eksposur PRD (uang penulis lain dari uang kode).
7. **M3: rasio** dihitung dari antrean (`max_usd / jumlah item`) terhadap `_reference` yang sama; `ratio` None (kurang dari 3 job code APPLIED) menolak tanpa alasan diketik (gagal tertutup); ambang berlaku pada angka yang tampil dan dibulatkan, `>= 3`. Dinyatakan: dengan config nyata rasio sekitar 1 untuk n ≤ 5, jadi gerbang ini hanya menangkap penyimpangan config.
8. **M4: pengakuan "tanpa contoh baru".** Bidang `ack: "1,3"` (teks; PARAMS hanya teks) harus sama persis dengan himpunan item yang `warning`-nya terisi; masuk digest; salah atau kurang 409; dikirim saat tidak ada item yang membutuhkan 400.
9. **M5: eksekusi.** Pelari sinkron baru seperti `control_cli` (batas waktu, `stdin=DEVNULL`, kode keluar ke audit, `with_config`): `argus --jobs-dir J --queues-dir Q [--config] prd approve DIR --sha FULL` dan `queue go QID --sha FULL --via ui [--reason-file F]`; tanpa `--key-file` dan tanpa `--yes` (`queue go --key-file` adalah galat argparse, kode 2: tes); baris penolakan CLI di-scrub sebelum 409 dan audit (temuan BLOCK mengutip jalur tulisan model).
10. **M6: keadaan tombol** dari satu fungsi yang juga dipakai `build`, ditambahkan ke `GET /api/approve/prd/<job>` (`t4: {action|null, why}`), supaya UI tidak menawarkan yang ditolak `prepare`.
11. **M7:** chat menolak bila `realpath(DIR) != DIR` (tanpa subproses); folder diganti antara kartu dan confirm: 409 digest; antara confirm dan CLI: penolakan sha CLI atau berkas SUPERSEDED; antrean disetujui atau ditutup sementara itu: penolakan CLI.
12. **Tes tambahan:** antrean dari giliran lama tidak ditawarkan dan 409; SUPERSEDED, `stale`, WRITING/busy, ABANDONED ditolak; `jobs_dir` antrean lain dan teks issue tak cocok ditolak; `concerns` dan `one` ditolak; rasio None; `ack` himpunan persis; alasan (pendek, panjang, mirip kunci, dikirim saat tak perlu 400; tersimpan di `approved.reason`; audit hanya hash); `queue go --key-file` exit 2; CLI exit 2 jadi 409 tanpa `executed`; eksposur (queue.json rusak 503, persetujuan terminal tak dihitung, via ui di luar 24 jam tak dihitung, antrean tertutup dihitung, jaring audit dengan `QUEUE_ID` tanpa hitung ganda, dua `queue_go` berturut-turut); argv sha penuh dan tanpa `--yes`; grep fixture antrean rusak (`test_chat_cards.py:656`) di PR2.
13. **Teks yang diamandemen (PR2/PR3):** SPEC_CHAT_APP 11.6 ("`approve` di luar cakupan"), 13.7 butir 9 ("tak ada tombol atau teks approve"); komentar `chat_actions.py:47` ("never an approve"); docstring `approve_cards.py:4` ("There is no button here"); SPEC_KARTU_SETUJU bagian 2 ("tombol adalah T4"); aturan "Chat app" di AGENTS.md (satu-satunya persetujuan di chat: `prd_approve` dan `queue_go`, lewat prepare/confirm, penolakan M8 dan rasio di server, batas harian; tidak pernah approve draf, apply, atau `queue step`). `test_chat_decide.py:219` (`job_approve` 404) tetap. PR3 sengaja menulis ulang `test_chat_ui.py:248-256` (melarang "approve" dan "setujui" di JS/HTML). **Batas yang diketahui:** `queue go` dari terminal tidak menegakkan M8 (chat yang menegakkan; beda dari `apply`).
14. **Kartu konfirmasi ramping:** digest tanpa `spent` dan cap waktu bacaan domain, supaya tidak 409 palsu.
15. **PR1** memuat `queue go --via ui` (`rq.go(..., via=None)`, `approved.via` hanya bila diberikan, `choices=rj.VIA`) **dan** `--reason-file`; tes lama (`test_queue.py:129`, fixture `approved={"sha":"x"}`) tetap.
16. **Mutan** (28, daftar tinjau Opus): ditulis di spek kode PR2/PR3, dijalankan sekali sesudah tinjau kode.
