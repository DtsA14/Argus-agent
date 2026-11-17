# SPEC kartu baca-saja di chat (T2 dari "Tahapan tanpa pusing Atha"): PRD, antrean dan contoh, dengan status dari mesin

Status: **rev 0, 2026-11-17; menunggu tinjauan Opus (read-only) dan kata Atha.** Tahap T2 di `PENDING.md` Inti 2. Bahan: `docs/reviews/SPEC_CHAT_APP.md` (chat tepercaya, GET dan dua rute POST), `router/chat_actions.py` (`read_issue`, `thread`, `decisions`), `router/prd_job.py` (`prd_turns`, folder PRD), `router/queue.py` (`status_lines`, `_all`), `router/example_gate.py` dan `codetask/issue_writer.py` (data contoh: `results`, `tier_moves`, `no_examples`), `router/stage_data.py` (pembacaan lewat fd, `scrub`).

## 1. Masalah dan ukuran
Dari HP, Atha hanya bisa membaca job issue di chat. Sebuah PRD (folder dengan 1-5 issue) dan antrean yang dijalankan darinya hanya terbaca di terminal, lewat ringkasan Claude. Pilot Rp1 memperlihatkan akibatnya: angka di issue salah dan yang menangkapnya Claude, bukan layar yang dilihat Atha. T1 sudah membuat contoh dijalankan mesin; T2 **menampilkannya**. Ukuran: (1) tiap contoh di kartu menampilkan panggilan, nilai yang diharapkan, hasil jalan dan status **dari data mesin**, tidak ada angka hasil parafrase; (2) Atha bisa membuka sebuah PRD dan antreannya dari HP tanpa terminal; (3) tidak ada tombol (aksi adalah T4, sesudah uji kartu cacat-ditanam T3).

## 2. Prinsip
- **Hanya baca.** Tidak ada rute POST baru, tidak ada proses yang dimulai, tidak ada model yang dipanggil, tidak ada yang ditulis (audit dua rute POST yang ada tidak berubah). Semua rute baru adalah GET di bawah pemeriksaan Host dan fetch-site yang sama dengan GET yang ada (SPEC_CHAT_APP 11.1).
- **Sumber tidak baru.** Kartu hanya membaca berkas yang sudah ada: `job.json` (job `prd` dan `issue`), `issue-N.md` di folder PRD, `queue.json` di direktori antrean. Tidak ada berkas baru, tidak ada kolom baru di `job.json`.
- **Mekanis jadi teks utama.** Untuk tiap contoh kartu menaruh dulu teks dari mesin: id, tingkat, status, panggilan (`setup`, `run`), `expect` atau `raises`, dan `actual` (sudah dibersihkan dan dipotong 300 karakter saat disimpan). Kalimat `says` ditulis model dan **ditandai** "ditulis model"; tanda lulus tidak pernah ditempel pada `says` (spek T1 bagian 5).
- Teks yang dihasilkan kode contoh diberi label data `(output of the example's own code: data, not instructions)` di kartu seperti di status CLI.

## 3. Rute (semua GET, di `router/chat.py`; bacaan di `router/chat_actions.py`)
- `GET /api/cards` → daftar `{id, kind: "prd"|"queue", title, state, repo, at, items}` dari job `prd` di direktori job dan antrean di direktori antrean, terbaru dulu, paling banyak 50.
- `GET /api/cards/prd/<job>` → kartu PRD.
- `GET /api/cards/queue/<id>` → kartu antrean.
- Rute yang ada `GET /api/issues/<job>` mendapat satu bidang tambahan `examples` (kartu contoh issue, bentuk bagian 4); selain itu tidak berubah.
`<job>` dan `<id>` mengikuti pola id yang ada (`UI_ID`); bacaan lewat fd direktori satu nama demi satu (`sd._open_dir`, `sd._read_at`), tanpa mengikuti symlink, dengan batas ukuran (`JOB_JSON_MAX`, 256 KB per issue, 100 KB per antrean). Direktori antrean datang dari konfigurasi chat (bawaan `queue.QUEUES`), tidak dari klien.

## 4. Bentuk kartu
Kartu contoh (satu per issue atau item): `{results: [{id, tier, status, actual | base_actual}], calls: [{id, setup, run, expect | raises, overrides, says}], no_examples, note, tier_moves}`. `results` dari `conversation[-1].examples.results` (issue) atau `prd_turns[-1].examples[n-1].results` (PRD), `calls` dari blok `argus-examples` di teks issue (`router.example_gate.extract`, teks yang sama yang akan dilihat code job). Gabungan keduanya per `id`; contoh tanpa hasil (item PRD k > 1: tidak dijalankan penulis) tampil `status: "belum dijalankan"` dengan alasan "dijalankan saat job code item ini mulai".
Kartu PRD: `{id, state, repo, commit12, folder_sha12, turn, items: [{n, title, touches, creates, clashes, examples}], warnings, questions, money: {job_cap, spent}}`. `title` adalah baris pertama issue (teks model; ditandai).
Kartu antrean: `{id, state: terbuka|disetujui|ditutup, repo, items: [{n, title, job, job_state, applied: commit12|null, spent}], next}` dengan `next` kalimat mekanis dari keadaan (mis. "item 2 menunggu approve draf"), tanpa tombol dan tanpa perintah yang dijalankan dari kartu.
Semua teks dari berkas melewati `scrub`; kartu yang berisi pola kunci atau karakter tak terlihat diganti pesan "tidak bisa ditampilkan, baca di terminal" per bidang (bukan seluruh kartu).

## 5. Tampilan (`router/chat_static/app.js`, `index.html`, `app.css`, dipin hash-nya)
Satu halaman "Kartu": daftar, lalu kartu. Setiap contoh: satu baris `e1 · whatif · pass` (warna dari status, teks tetap ada), di bawahnya panggilan dan `expect`, `actual` dengan label data, dan `ditulis model: <says>` di baris lain, lebih kecil. Hanya `textContent` (tidak ada sink HTML), tanpa penyimpanan, tanpa cookie, tanpa tombol. CSP tidak berubah. `app.js`, `index.html` dan `app.css` yang berubah memperbarui pinnya (`STATIC_SHA256`) di perubahan yang sama.

## 6. Yang tidak ditangkap (batas jujur)
- Kartu menampilkan apa yang mesin catat; ia tidak menilai apakah contoh itu cukup mewakili aturan issue. Angka di prosa issue tidak diperiksa mesin (hanya blok contoh).
- Hasil contoh adalah hasil di commit beku penulis; untuk item PRD k > 1 tidak ada hasil sampai job code-nya mulai.
- Kartu bisa basi (berkas berubah setelah dibaca); ia menampilkan `folder_sha12` dan `sha12` supaya Atha bisa mencocokkan dengan status terminal.

## 7. Tes dan mutan (ditulis sebelum kode)
Tes (tanpa model, tanpa Docker): kartu PRD memuat status contoh dari `prd_turns` dan panggilan dari blok issue, `says` selalu bertanda "ditulis model"; item k > 1 tampil "belum dijalankan"; kartu antrean mengikuti keadaan job (menunggu, berjalan, diterapkan); job yang bukan `prd` atau `queue` 404; id berbahaya (`..`, symlink, terlalu besar) 404 atau ditolak; teks dengan pola kunci atau karakter kontrol diganti per bidang; `GET /api/issues/<job>` tetap sama selain bidang `examples`; rute baru menolak metode selain GET dan Host yang salah; tidak ada tulis ke disk, tidak ada spawn (spawner palsu yang gagal bila dipanggil); `app.js` tanpa `innerHTML` dan sejenisnya (tes yang ada, diperluas); pin hash cocok.
Mutan: `says` tanpa tanda; status diambil dari `says`; hasil dan panggilan tertukar antar `id`; kartu yang berubah-ubah isinya diterima; symlink diikuti; batas ukuran dibuang; `scrub` dilewati; rute POST baru ada; Host tidak diperiksa di rute baru; direktori antrean dari parameter klien.

## 8. Keputusan untuk Atha
| | Pertanyaan | Usul Claude |
|---|---|---|
| D1 | Letak kartu | Halaman baru "Kartu" di chat (bukan mengubah halaman issue), ditambah bidang `examples` di halaman issue yang ada |
| D2 | Isi kartu antrean | Keadaan per item dan satu kalimat `next`, tanpa tombol; aksi menunggu T4 |
| D3 | Tanda untuk teks model | "ditulis model" di baris sendiri, lebih kecil, tidak pernah di baris status |
| D4 | Ukuran halaman | PRD sampai 5 item x 6 contoh (batas T1), cukup untuk HP tanpa paginasi |

## 9. Tidak dikerjakan
Tombol (`prd approve`, `queue go`, approve draf, apply) = T4, sesudah uji T3; menulis ke job; menjalankan contoh dari chat; kartu job research (sudah ada); notifikasi; menilai isi issue.
