# Spec T4b (bagian 1): `queue step` dan approve draf dari chat; apply tetap terminal

Status: **rev 0, untuk ditinjau.** Disetujui arahnya oleh Atha 2026-11-24 ("Ok setuju bro", atas usul: buka bertahap, `queue step` dan approve draf dulu, apply paling akhir, dengan amandemen aturan chat hanya untuk dua langkah pertama). Ditulis Claude. Menyambung `SPEC_CHAT_T4A.md` (pola prepare lalu confirm, tanda mesin di atas, tombol mati di server, batas harian) dan `SPEC_KARTU_SETUJU.md` (kartu pasang). Jalur ketat.

## 1. Dasar dan batas

**Dasar:** T4a membuka `prd_approve` dan `queue_go`. Sesudah `queue_go` antrean berhenti menunggu tiga hal per issue yang semuanya terminal: `queue step` (mulai drafter), approve draf (mulai agen), apply patch. Tidak satu pun bisa diketuk Atha dari HP, jadi tiap issue butuh Claude di tengah (angka E2: `without_claude` nol karena itu).

**Dalam cakupan (dua aksi baru):**
1. `queue_step`: setara `argus queue step Q`. Memulai drafter untuk item berikutnya dari antrean yang **Atha setujui lewat chat** (`approved.via == "ui"`). Memakai uang yang sudah disetujui di `queue_go`: eksposur tambahan 0.
2. `draft_approve`: setara `argus approve JOB --sha DRAFTSHA`. Menyetujui draf (kontrak tes dan batas) dan memulai agen kode. Memakai uang dalam batas job yang sudah dihitung di `queue_go`: eksposur tambahan 0.

**Di luar cakupan (tetap terminal atau operator):** apply, `applied`, reject, abandon, `queue retry/close`, redraft, retry agen, `prd reply`, buka PR, merge. **Apply tidak dibuka di spek ini**: ia butuh catatan pembaca angka untuk item antrean PRD, dan pembaca angka belum teruji (T3b gagal tiga putaran); itu keputusan C6/C9 dan spek sendiri.

## 2. Aturan chat yang diamandemen (butuh kata Atha tertulis)

SPEC_CHAT_APP 13.7 butir 9 ("never an approve", sudah dikecualikan T4a untuk `prd_approve` dan `queue_go`) dan aturan chat di `AGENTS.md` diamandemen: **chat boleh `queue_step` dan `draft_approve` hanya untuk item dari antrean yang disetujui lewat chat (`approved.via == "ui"`)**, tiap aksi lewat prepare lalu confirm; chat tidak pernah apply, reject, abandon, retry atau redraft; klien tidak pernah memilih sha, antrean, uang atau argumen lain. Bunyi baru `AGENTS.md`: "The chat's only approvals are `prd_approve`, `queue_go` (SPEC_CHAT_T4A) and, for the items of a queue that the chat itself approved, `queue_step` and `draft_approve` (SPEC_CHAT_T4B)... Flag any chat route that applies a patch, rejects or retries a job, or lets the client pick a queue, a sha or an amount."

## 3. Alur dan kartu

**`queue_step`.** Kartu antrean (T4a) yang `WAITING` dengan item berikutnya siap mendapat tombol **"Mulai issue N"**. `prepare` dengan `{action: "queue_step", queue}` (id antrean dari halaman; server memeriksa bahwa antrean ada di `queues_dir`, disetujui via ui, tidak ditutup dan bahwa itemnya berikutnya). Kartu konfirmasi: permintaan Atha kata per kata untuk item itu, batas job, uang antrean tersisa dan **yang akan terjadi**: "drafter menulis tes dan kontrak; kamu tetap harus menyetujui draf". Argv tetap: `argus ... queue step Q --yes --key-file <slot kode>`; tidak ada `--sha` (antrean memutuskan item), tidak ada id item dari klien.

**`draft_approve`.** Antrean `WAITING` dengan draf `AWAITING_APPROVAL` mendapat kartu **"Setujui draf issue N"**. Klien mengirim `{action: "draft_approve", queue}`; server mencari item yang menunggu, membaca draf terakhir dan menghitung sha-nya (klien tidak mengirim sha). Kartu konfirmasi menampilkan, di atas tombol: **tanda mesin** (bagian 4), lalu permintaan item (kata Atha), nama tes yang akan ditulis dan berkas yang disentuh (data harness, tulisan model berlabel), batas uang job dan sisa antrean. Argv tetap: `argus ... approve JOB --sha DRAFTSHA --via ui --yes --key-file <slot kode>`.

Keduanya mulai proses panjang di latar belakang (drafter beberapa menit; agen 5 sampai 17 menit): chat memakai pola yang sudah ada untuk riset dan PRD (anak proses, halaman status dari berkas job, bukan dari keluaran proses).

## 4. Tanda mesin, tombol yang mati di server

`draft_approve` ditolak di server (`confirm` 409, bukan hanya tombol disabled) bila salah satu: draf ditandai oleh gerbang (`_conflict_refusal`, `scope:no_test_detection`, tes lama bentrok) atau `argus approve` sendiri akan menolak (kartu menjalankan pemeriksaan baca-saja yang sama seperti kartu pasang, dari berkas yang sama); item bukan item antrean via ui; sha draf berubah antara prepare dan confirm (digest kartu); job bukan `AWAITING_APPROVAL`; sisa uang antrean kurang dari batas job. Tanda yang tidak menghalangi tetapi **ditampilkan di atas**: peringatan `leaks` (penasihat), profil anggaran `default` untuk berkas besar, tes yang diubah (bukan hanya ditambah). `queue_step` ditolak bila uang tersisa kurang dari satu job, antrean `STOPPED`, `CLOSED` atau bukan via ui.

## 5. Uang dan batas harian

Tidak ada uang baru: `queue_go` sudah menyetujui `max_usd` antrean dan menghitungnya ke batas harian chat (T4a bagian 4). `queue_step` dan `draft_approve` menambah 0 ke eksposur; yang berubah hanya **siapa yang memulai**. Antrean yang disetujui dari terminal (`approved.via` bukan ui) tidak bisa dijalankan dari chat justru supaya uangnya tidak lolos dari batas harian.

## 6. Pelaku (E2)

`argus approve` mendapat `--via ui` (divalidasi seperti `reject` dan `abandon`), dan `argus queue step` mendapat `--via ui`; `rj.actor` (SPEC_ACTOR_RECORD) mencatat `ui`. Dengan ini angka `without_claude` untuk issue yang approve drafnya lewat chat mulai bisa naik; apply masih terminal, jadi sampai apply terbuka tidak ada issue yang `without_claude` penuh.

## 7. Tes wajib (gagal bila jaminannya rusak)

Klien tidak dapat memilih antrean di luar antrean via ui, item, sha, uang atau argumen; field tak dikenal 400. Token terikat digest: draf diganti, antrean ditutup, item bergeser atau config berubah antara prepare dan confirm memberi 409 tanpa spawn. `draft_approve` untuk draf yang ditandai gerbang, antrean terminal, job bukan `AWAITING_APPROVAL` atau uang tidak cukup: 409. Argv memuat `--via ui` dan `--yes`, `--key-file` hanya slot kode, tidak memuat `--sha` untuk `queue_step`. Aksi apply, reject, abandon, retry tidak ada di dispatch (aksi tak dikenal ditolak). Audit satu baris per aksi sebelum spawn, tanpa teks pesan. Dua `confirm` berturut-turut untuk draf yang sama memulai satu agen. `actor` tercatat `ui` untuk approve via chat. Tombol tidak muncul untuk antrean via terminal.

## 8. PR (jalur ketat; tinjau Opus spek lalu kode; mutan sekali; precheck; `verify_at`)

- **PR1 (CLI):** `argus approve --via ui` dan `argus queue step --via ui` (validasi, `actor` ui), tes.
- **PR2 (chat, tanpa UI):** aksi `queue_step` dan `draft_approve` di `chat_actions` (kartu, tanda mesin, audit, dispatch, penolakan di server), tes dan mutan.
- **PR3 (UI):** dua tombol di tab Kartu, tanda mesin di atas, pin hash statis; amandemen `AGENTS.md` dan SPEC_CHAT_APP 13.7 dalam PR yang sama dengan PR2.

## 9. Keputusan untuk Atha

| | Pertanyaan | Usul Claude |
|---|---|---|
| K1 | Apakah ketukan "Setujui draf" memang harus dari kamu, atau draf yang semua tanda mesinnya hijau disetujui otomatis? | Ketukan manusia dulu. Kamu tidak menilai isi draf (tes dan kontrak), jadi ketukan itu mudah jadi stempel; alasannya tetap: persetujuan yang disengaja, dan kartu menaruh tanda merah di atas. Otomatis-bila-hijau adalah langkah berikutnya dan butuh data: berapa draf hijau yang akhirnya ditolak |
| K2 | Antrean yang disetujui dari terminal boleh dijalankan dari chat? | Tidak (bagian 5), supaya uang tetap di batas harian |
| K3 | Pembaca angka dan apply | Spek terpisah sesudah keputusan C6/C9; tidak dibuka di sini |

## 10. Yang belum dicek (rev 0)

Apakah `queue step` dari anak proses chat memegang kunci dengan cara yang sama seperti `research_new` (slot kunci kode `ARGUS_CHAT_KEY_FILE`, bentuk `--key-file openrouter=...`); apakah halaman antrean T4a sudah menampilkan item berikutnya dan status draf tanpa pembacaan baru; apakah `argus approve` memeriksa `--sha` terhadap draf terakhir saja (diasumsikan, perlu dibaca); apakah pemeriksaan kartu pasang (a sampai i) bisa dipakai ulang untuk draf atau perlu fungsi baru (`approve_code.py` hanya mencakup patch); bentuk eksposur bila antrean via ui dijalankan sebagian lewat terminal. Tinjau Opus diminta memeriksa terutama butir ini dan amandemen bagian 2.
