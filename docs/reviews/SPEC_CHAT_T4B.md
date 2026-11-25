# Spec T4b (bagian 1): `queue step` dan approve draf dari chat; apply tetap terminal

Status: **rev 1** (rev 0 + tinjauan Opus 2026-11-24, GO dengan perbaikan; K4 diputuskan Atha 2026-11-25: A). Disetujui arahnya oleh Atha 2026-11-24 ("Ok setuju bro", atas usul: buka bertahap, `queue step` dan approve draf dulu, apply paling akhir, dengan amandemen aturan chat hanya untuk dua langkah pertama). Ditulis Claude. Menyambung `SPEC_CHAT_T4A.md` (pola prepare lalu confirm, tanda mesin di atas, tombol mati di server, batas harian) dan `SPEC_KARTU_SETUJU.md` (kartu pasang). Jalur ketat.

## 1. Dasar dan batas

**Dasar:** T4a membuka `prd_approve` dan `queue_go`. Sesudah `queue_go` antrean berhenti menunggu tiga hal per issue yang semuanya terminal: `queue step` (mulai drafter), approve draf (mulai agen), apply patch. Tidak satu pun bisa diketuk Atha dari HP, jadi tiap issue butuh Claude di tengah (angka E2: `without_claude` nol karena itu).

**Dalam cakupan (dua aksi baru):**
1. `queue_step`: setara `argus queue step Q`. Memulai drafter untuk item berikutnya dari antrean yang **Atha setujui lewat chat** (`approved.via == "ui"`). Memakai uang yang sudah disetujui di `queue_go`: eksposur tambahan 0.
2. `draft_approve`: setara `argus approve JOB --sha DRAFTSHA`. Menyetujui draf (kontrak tes dan batas) dan memulai agen kode. Memakai uang dalam batas job yang sudah dihitung di `queue_go`: eksposur tambahan 0.

**Di luar cakupan (tetap terminal atau operator):** apply, `applied`, reject, abandon, `queue retry/close`, redraft, retry agen, `prd reply`, buka PR, merge. **Apply tidak dibuka di spek ini**: ia butuh catatan pembaca angka untuk item antrean PRD, dan pembaca angka belum teruji (T3b gagal tiga putaran); itu keputusan C6/C9 dan spek sendiri.

## 2. Aturan chat yang diamandemen (butuh kata Atha tertulis)

SPEC_CHAT_APP 13.7 butir 9 ("never an approve", sudah dikecualikan T4a untuk `prd_approve` dan `queue_go`) dan aturan chat di `AGENTS.md` diamandemen: **chat boleh `queue_step` dan `draft_approve` hanya untuk item dari antrean yang disetujui lewat chat (`approved.via == "ui"`)**, tiap aksi lewat prepare lalu confirm; chat tidak pernah apply, reject, abandon, retry atau redraft; klien tidak pernah memilih sha, antrean, uang atau argumen lain. Bunyi baru `AGENTS.md`: "The chat's only approvals are `prd_approve`, `queue_go` (SPEC_CHAT_T4A) and, for the items of a queue that the chat itself approved, `queue_step` and `draft_approve` (SPEC_CHAT_T4B)... Flag any chat route that applies a patch, rejects or retries a job, or lets the client pick a queue, a sha or an amount."

## 3. Alur dan kartu

**`queue_step`.** Kartu antrean (T4a) yang `WAITING` dengan item berikutnya siap mendapat tombol **"Mulai issue N"**. `prepare` dengan `{action: "queue_step", queue}` (id antrean dari halaman; server memeriksa bahwa antrean ada di `queues_dir`, disetujui via ui, tidak ditutup dan bahwa itemnya berikutnya). Kartu konfirmasi: permintaan Atha kata per kata untuk item itu, batas job, uang antrean tersisa dan **yang akan terjadi**: "drafter menulis tes dan kontrak; kamu tetap harus menyetujui draf". Argv tetap, dites persis sama: `argus ... queue step Q --item N --via ui --yes --key-file <path>`; `N` dihitung server dari `derive` dan ditolak CLI bila bukan item berikutnya (PR1 menambah `--item`); tidak ada `--sha`, `--max-usd`, `--web`, `--reference-patch`, `--max-iterations`; klien tidak mengirim N. Slot kunci: `key_file(writer=False)` = `ARGUS_CHAT_KEY_FILE`, satu path biasa seperti `issue_start` (bukan bentuk `openrouter=`); tanpa kunci: 503 saat prepare. Kartu menyebut bila item adalah retry: temuan pembaca ikut ke drafter.

**`draft_approve`.** Antrean `WAITING` dengan draf `AWAITING_APPROVAL` mendapat kartu **"Setujui draf issue N"**. Klien mengirim `{action: "draft_approve", queue}`; server mencari item yang menunggu, membaca draf terakhir dan menghitung sha-nya (klien tidak mengirim sha). Kartu konfirmasi menampilkan, di atas tombol: **tanda mesin** (bagian 4), lalu permintaan item (kata Atha), nama tes yang akan ditulis dan berkas yang disentuh (data harness, tulisan model berlabel), batas uang job dan sisa antrean. Argv tetap: `argus ... approve JOB --sha DRAFTSHA64 --via ui --yes --key-file <path>` dengan sha penuh 64 hex; tidak ada `--max-usd` dan argumen lain. Hanya job `AWAITING_APPROVAL` (CLI juga menerima `DRAFT_FAILED`; chat lebih ketat). Fungsi baru baca-saja `draft_card` meniru penolakan `rj.approve` (status, `_last_draft`, sudah disetujui, `_conflict_refusal`, `environment_changed`, `cap < need`); pemeriksaan a sampai i kartu pasang khusus patch dan tidak dipakai ulang. `dr.check` (sandbox) dan HEAD hanya diperiksa CLI; kartu menyebut itu.

Keduanya mulai proses panjang di latar belakang (drafter beberapa menit; agen 5 sampai 17 menit): chat memakai pola yang sudah ada untuk riset dan PRD (anak proses, halaman status dari berkas job, bukan dari keluaran proses).

## 4. Tanda mesin, tombol yang mati di server

`draft_approve` ditolak di server (`confirm` 409, bukan hanya tombol disabled) bila salah satu: draf ditandai oleh gerbang (`_conflict_refusal`, tes lama bentrok; `scope:no_test_detection` dibuang karena kriteria saat patch) atau `argus approve` sendiri akan menolak (kartu menjalankan pemeriksaan baca-saja yang sama seperti kartu pasang, dari berkas yang sama); item bukan item antrean via ui; sha draf berubah antara prepare dan confirm (digest kartu); job bukan `AWAITING_APPROVAL`; sisa uang antrean kurang dari batas job; `min(agent_max_usd[profil], left_usd) < attempt_usd` (kalau lolos, `approve` akan menjadikan job BLOCKED); `queue_step` juga memeriksa batas drafter. Juga ditolak bila `spawner.busy(job)` atau `spawner.busy(queue)` (jendela job NEW tanpa stage), atau `jobs_dir` antrean berbeda (`_same_jobs_dir`). Tanda yang tidak menghalangi tetapi **ditampilkan di atas**: peringatan `leaks` (penasihat), profil anggaran `default` untuk berkas besar, tes yang diubah (bukan hanya ditambah). `queue_step` ditolak bila uang tersisa kurang dari satu job, antrean `STOPPED`, `CLOSED` atau bukan via ui.

## 5. Uang dan batas harian

`queue_go` menghitung `max_usd` ke batas harian chat hanya selama `approved.at` dalam 24 jam (`chat_plan.py:349`). **K4 (Atha, A):** bila `queue_go` antrean itu tidak lagi dalam jendela, `exposure_of(queue_step)` = batas satu job penuh dan dihitung ke batas harian; dalam jendela tetap 0. `draft_approve` selalu 0 (job sudah dihitung saat step). Aksi diaudit dengan nama sendiri (bukan `queue_go`/`research_new`) supaya jaring audit tidak salah hitung. Antrean yang disetujui dari terminal (`approved.via` bukan ui) tidak bisa dijalankan dari chat justru supaya uangnya tidak lolos dari batas harian.

## 6. Pelaku (E2)

`argus approve` mendapat `--via ui` (divalidasi seperti `reject` dan `abandon`), dan `argus queue step` mendapat `--via ui`; `rj.actor` (SPEC_ACTOR_RECORD) mencatat `ui`. Dengan ini angka `without_claude` untuk issue yang approve drafnya lewat chat mulai bisa naik; apply masih terminal, jadi sampai apply terbuka tidak ada issue yang `without_claude` penuh.

## 7. Tes wajib (gagal bila jaminannya rusak)

Klien tidak dapat memilih antrean di luar antrean via ui, item, sha, uang atau argumen; field tak dikenal 400. Token terikat digest: draf diganti, antrean ditutup, item bergeser atau config berubah antara prepare dan confirm memberi 409 tanpa spawn. `draft_approve` untuk draf yang ditandai gerbang, antrean terminal, job bukan `AWAITING_APPROVAL` atau uang tidak cukup: 409. Argv memuat `--via ui` dan `--yes`, `--key-file` hanya slot kode, tidak memuat `--sha` untuk `queue_step`. Aksi apply, reject, abandon, retry tidak ada di dispatch (aksi tak dikenal ditolak). Tambahan rev 1: eksposur di luar 24 jam (K4); `DRAFT_FAILED` ditolak; `jobs_dir` beda ditolak; `cap < need` 409 dan job tidak jadi BLOCKED; job NEW tanpa stage dihitung sibuk; `--item` tidak cocok ditolak CLI; slot kunci = `KEY_ENV`; argv persis (tanpa `--max-usd`, `--web`, `--reference-patch`, `--max-iterations`); nama audit bukan `queue_go`/`research_new`. Digest memuat: id antrean, `list_sha`, `approved.sha`, nomor item, id job, `run_id` draf, sha draf penuh, batas agen dari config, ada-tidaknya `retry_note`. Audit satu baris per aksi sebelum spawn, tanpa teks pesan. Dua `confirm` berturut-turut untuk draf yang sama memulai satu agen. `actor` tercatat `ui` untuk approve via chat. Tombol tidak muncul untuk antrean via terminal.

## 8. PR (jalur ketat; tinjau Opus spek lalu kode; mutan sekali; precheck; `verify_at`)

- **PR1 (CLI):** `argus approve --via ui`, `argus queue step --via ui --item N` (validasi, item harus yang berikutnya, `actor` ui tercatat di `item.actor` dan entri `created` job), tes.
- **PR2 (chat, tanpa UI):** aksi `queue_step` dan `draft_approve` di `chat_actions` (kartu, tanda mesin, audit, dispatch, penolakan di server), tes dan mutan.
- **PR3 (UI):** dua tombol di tab Kartu, tanda mesin di atas, pin hash statis; amandemen dalam PR yang sama dengan PR2: `AGENTS.md:66` jadi "...approves a draft or starts a drafter of a queue not approved via the UI, or passes `--max-usd`/`--web`/`--reference-patch`/`--max-iterations`", komentar `chat_actions.py:49`, SPEC_CHAT_APP 11.6 dan 13.7.

## 9. Keputusan untuk Atha

| | Pertanyaan | Usul Claude |
|---|---|---|
| K1 | **Diputuskan Atha 2026-11-24: ketukan manusia dulu.** Pertanyaan: apakah ketukan "Setujui draf" memang harus dari kamu, atau draf yang semua tanda mesinnya hijau disetujui otomatis? | Ketukan manusia dulu. Kamu tidak menilai isi draf (tes dan kontrak), jadi ketukan itu mudah jadi stempel; alasannya tetap: persetujuan yang disengaja, dan kartu menaruh tanda merah di atas. Otomatis-bila-hijau adalah langkah berikutnya dan butuh data: berapa draf hijau yang akhirnya ditolak |
| K2 | Antrean yang disetujui dari terminal boleh dijalankan dari chat? | Tidak (bagian 5), supaya uang tetap di batas harian |
| K4 | **Diputuskan Atha 2026-11-25: A.** Antrean disetujui lebih dari 24 jam lalu | A: `queue_step` dihitung satu job penuh ke batas harian; B (ditolak): tolak dari chat |
| K3 | Pembaca angka dan apply | Spek terpisah sesudah keputusan C6/C9; tidak dibuka di sini |

## 10. Yang dicek Opus (rev 0, hasil dimasukkan di atas)

Lima butir ini sudah diperiksa terhadap kode: slot kunci (salah di rev 0, diperbaiki), halaman antrean (sebagian; butuh pembacaan baru `{n, job, draft_sha}` lewat fd), `--sha` hanya draf terakhir (benar, prefiks minimal 12), kartu pasang (tidak bisa dipakai ulang), eksposur sebagian-terminal (terbatas oleh `left_usd` dan `committed`; hanya hakim ≤$0.30 di luar). Teks asli rev 0 butir ini:

Apakah `queue step` dari anak proses chat memegang kunci dengan cara yang sama seperti `research_new` (slot kunci kode `ARGUS_CHAT_KEY_FILE`, bentuk `--key-file openrouter=...`); apakah halaman antrean T4a sudah menampilkan item berikutnya dan status draf tanpa pembacaan baru; apakah `argus approve` memeriksa `--sha` terhadap draf terakhir saja (diasumsikan, perlu dibaca); apakah pemeriksaan kartu pasang (a sampai i) bisa dipakai ulang untuk draf atau perlu fungsi baru (`approve_code.py` hanya mencakup patch); bentuk eksposur bila antrean via ui dijalankan sebagian lewat terminal. Tinjau Opus diminta memeriksa terutama butir ini dan amandemen bagian 2.
