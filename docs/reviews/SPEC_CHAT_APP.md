# Spec CHAT-APP (v2): aplikasi chat tepercaya di samping viewer; Argus tetap mesin

Status: **DRAF v2, menunggu tinjau Opus dan keputusan Atha**; kode belum disentuh. Ditulis Claude 2026-11-14.
Menggantikan draf v1 (opsi A: satu origin di 8710), yang **ditolak** oleh tinjau Opus 2026-11-14 (NO-GO): JS viewer ditulis agen Argus, dan bila satu origin dengan rute POST, cek Origin dan token F3 tidak lagi membedakan Atha dari JS itu; bertentangan dengan `SPEC_CONTROL_UI.md:144-145,169`, `SPEC_PWA_VIEWER.md:95,113`, `SPEC_ISSUE_WRITER.md:5,96-98`. Draf v1 ada di riwayat git.
Keputusan Atha 2026-11-14: **opsi B** (dua port: chat tepercaya yang menyerap kontrol, viewer baca-saja); chat app ditulis Claude, bukan agen Argus; di VM ini, akses HP tetap SSH forward.

## 1. Prinsip

1. **Dua origin, dua tingkat kepercayaan.** `8710` viewer: kode ditulis agen Argus, hanya baca, **tidak berubah**. `8712` chat: kode ditulis Claude di jalur ketat, tepercaya, satu-satunya tempat aksi dari HP. Viewer dan chat tidak pernah satu origin; hubungannya hanya **tautan** (navigasi GET), tidak pernah `fetch` lintas origin.
2. **Argus tetap mesin.** Chat memanggil CLI yang sama (`scripts/argus.py ...`) lewat proses anak, persis seperti `router/control.py`. Lock job, gerbang state, sha draf, `LLMCaller`, anggaran: tetap di bawah CLI, tidak diduplikasi di chat.
3. **Chat tidak memutuskan apa pun yang berbayar.** Aksi berbayar atau yang mengubah job (`start`, `approve`, `reject`, `abandon`, riset baru) selalu dua langkah: **siapkan** (server menyusun kartu konfirmasi dari data harness: repo, commit beku, environment, batas biaya, sha256 issue/draf) lalu **konfirmasi** (satu ketukan Atha, token sekali pakai terikat isi kartu itu). Tanpa model yang bisa melewati langkah kedua.
4. **Tanpa penerjemah niat berbasis model di v1.** Mode dipilih lewat chip (`Issue`, `Status`, `Riset`) dan perintah garis miring. Model hanya dipanggil di dalam job Argus yang memang memakai model (penulis issue, riset), bukan oleh chat sendiri. Lapisan bahasa bebas ada di bagian 8 (v2).

## 2. Susunan port

| Fase | 8710 viewer | 8711 kontrol | 8712 chat |
|---|---|---|---|
| sekarang | ada | ada | – |
| C1-C3 | tidak berubah | tidak berubah | **baru** (Status, Issue, Riset) |
| C4 | tidak berubah | **diserap** ke chat, dimatikan sesudah satu rilis stabil | reject, abandon, start di chat |

Kunci HP (`~/.ssh/authorized_keys`) sudah punya `permitopen` 8710 dan 8711; 8712 ditambahkan di C1 dan 8711 dicabut di akhir C4. Port hanya `127.0.0.1`, tidak pernah `0.0.0.0`, `localhost`-nama, 8000, 8710, atau 8711 (aturan F1 dipertahankan).

## 3. Service chat (`router/chat.py` dan paket di bawahnya)

- stdlib seperti `control.py`; unit `systemd --user argus-chat`; bind `127.0.0.1:8712`; satu permintaan sekaligus; klien macet diputus sesudah 10 detik.
- **Rute tetap** (lainnya 404, metode lain 405): halaman `GET /` (shell), aset statis `GET /static/*` (daftar nama tetap, sha dipin seperti `sw.js`), `GET /api/threads`, `GET /api/threads/<id>`, `GET /api/status` (dibaca dari direktori job, bukan snapshot), `POST /api/prepare`, `POST /api/confirm`, `POST /api/message` (hanya untuk thread issue yang sudah ada).
- **Data dibaca langsung dari direktori job** oleh kode harness (seperti `control_issues.py` hari ini), jadi chat bisa menampilkan percakapan issue, judul, dan laporan riset yang **tidak** ada di snapshot viewer. Tetap lewat scrubber yang sama (pola key, karakter kontrol).
- **Gerbang POST (F3, dipindah utuh):** `Host` tepat `127.0.0.1:8712`/`localhost:8712`; `Origin` ada dan tepat origin itu (`Sec-Fetch-Site` bila ada `same-origin`); isi valid **sebelum** token; token HMAC `aksi|job|sha|waktu` (rahasia 32 byte di memori, umur ≤ 30 menit, sekali pakai) yang **terbit di respons `prepare`** bersama kartu konfirmasi, bukan lewat GET yang bisa diminta siapa saja; `sha` harus sha draf/issue terakhir saat ini; aksi lewat CLI di bawah lock job. Audit F5: satu baris per POST, berhasil atau ditolak.
- **Header:** CSP `default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; form-action 'none'; frame-ancestors 'none'; base-uri 'none'` (tanpa `unsafe-inline` dan `unsafe-eval`), `Cache-Control: no-store` pada `/api/*`, `X-Content-Type-Options`, `Referrer-Policy: same-origin`. Tanpa CORS, tanpa cookie, tanpa penyimpanan browser untuk data job.
- **Frontend** (HTML, CSS, JS statis tanpa build tool pihak ketiga, atau satu bundel yang ditulis dan di-review Claude): semua teks dari job, issue, draf, dan keluaran model dirender dengan `textContent`; tidak ada `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write`, `eval`, `new Function`. Pemindai build harness menolak pola itu, dan CSP memblokir skrip sisipan walau lolos.
- **Batas biaya:** per aksi tetap dari config (`control.issue_*`, `router.research_max_usd`), **tidak dari form**. Ditambah batas **harian untuk job yang dimulai dari UI** (config, bawaan $2,00), dihitung dari ledger job; terlampaui → `prepare` menolak tanpa memanggil CLI.
- Pesan: ≤ 4000 (pertama) / ≤ 2000 (balasan), tanpa kategori C*, Zl, Zp; selalu lewat file sementara milik service dan `--message-file`, tidak pernah argv. Key tidak pernah dibaca service dan tidak tampil di halaman atau audit.

## 4. Bentuk (HP dan layar lebar)

Satu halaman: kotak input di bawah dengan chip mode; aliran percakapan di atas, hasil sebagai **kartu**; panel samping (geser dari kiri, tetap tampak di layar lebar) berisi daftar thread/job menurut state, papan skor, pengaturan. Kartu: job (state, biaya terhadap batas, tahap, tautan ke viewer untuk detail), issue (ringkasan, tombol **Siapkan Start**), riset (status, laporan dirender di chat), konfirmasi (fakta dari harness, tombol **Konfirmasi** dan **Batal**). Tabel papan skor yang terpotong di HP diselesaikan sebagai kartu.

Mode **Status** tidak memanggil model dan tidak memakai teks bebas selain filter/pencarian id; mode **Issue** memakai penulis issue yang ada (model Argus, anggaran Argus); mode **Riset** memulai job riset yang ada.

## 5. Yang berubah pada yang lain

- **Viewer:** tidak ada kode baru yang wajib. Tautan `Decide` (F7) menunjuk `http://localhost:8712/...` setelah C4. Viewer tidak pernah memanggil rute chat.
- **Snapshot publik:** tidak berubah (tetap tanpa teks issue atau percakapan).
- **`control.py`/`control_issues.py`:** dipakai ulang sebagai pustaka (gerbang, token, form-validasi), dipindah bukan ditulis ulang; tes F9 lama dipertahankan dan dijalankan terhadap rute baru, dengan Host/Origin 8712.
- **`AGENTS.md`:** satu baris: chat adalah kode tepercaya yang ditulis di jalur ketat, tidak oleh agen Argus.

## 6. Fase (tiap PR jalur ketat kecuali dinyatakan lain)

| | Isi |
|---|---|
| C0 | spek ini, tinjau Opus, keputusan Atha |
| C1 | kerangka service 8712 + shell + mode **Status** (hanya baca) + deploy `argus-chat` + `permitopen` 8712; tanpa POST |
| C2 | mode **Issue**: `prepare`/`confirm` untuk `issue new|reply|start|abandon`, kartu issue, batas harian |
| C3 | mode **Riset**: mulai dan baca laporan |
| C4 | serap kontrol: `reject`/`abandon` job, panel Keputusan; matikan 8711 dan cabut `permitopen` 8711; ubah tautan F7 |
| C5 | poles: kosong dan galat, sambung ulang, bahasa |

C1 memberi Atha manfaat tanpa satu pun aksi. Sesudah C1, pakai seminggu sebelum C2.

## 7. Tes wajib (gagal bila jaminannya rusak; mutan)

- Bind hanya `127.0.0.1:8712`; `Host` dan `Origin` asing, 8710, dan 8711 ditolak; `Sec-Fetch-Site: cross-site` ditolak.
- Rute: selain daftar tetap 404; metode lain 405; varian (`/api/threads/x/`, query, `..`, `%2F`, huruf besar) 404; `HEAD`/`OPTIONS` pada rute POST 405; tanpa header CORS.
- Token: terbit hanya di respons `prepare`; terikat aksi, job, sha, waktu; kedaluwarsa, dipakai dua kali, atau sha berubah → ditolak tanpa memanggil CLI; `confirm` tanpa `prepare` ditolak.
- Tidak ada rute atau jalur yang menjalankan `start`, `approve`, `reject`, `abandon`, riset tanpa `prepare` lalu `confirm`.
- Pesan: panjang dan karakter C*/Zl/Zp ditolak; tidak pernah lewat argv; key tidak pernah di halaman atau audit; teks `<script>` dan `<img onerror>` dari issue/draf/riset tampil sebagai teks.
- Frontend: pemindai menolak `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write`, `eval`, `new Function`, `import()` dinamis, dan sumber skrip di luar daftar; aset statis dipin sha.
- Batas harian: terlampaui → `prepare` ditolak; batas per aksi dari config, bukan form; model tanpa harga ditolak (di CLI).
- Mode Status: nol subproses model (tes mengunci dengan CLI palsu yang gagal bila dipanggil).
- Viewer: tes bahwa tidak ada rute chat di allowlist proxy dan bahwa proxy tetap menolak semua non-GET (tes lama, tidak diubah).
- Audit: satu baris per POST, termasuk yang ditolak di gerbang mana pun.
- C4: tes F9 lama lulus untuk rute pengganti; 8711 tidak lagi mendengarkan sesudah dimatikan (cek `ss`).

## 8. Lapisan bahasa bebas (v2, tidak dikerjakan di sini)

Asisten percakapan umum yang memilih alat sendiri. Syarat desain yang sudah ditetapkan: alatnya **daftar tetap yang sama** dengan chip (status, issue, riset, siapkan); model **tidak pernah** memegang `confirm`, token, atau key; keluaran model dirender sebagai teks; biayanya lewat `harness/llm.py` bila dijalankan oleh Argus, atau terpisah dan berbatas bila oleh sisi chat (keputusan K3). Ditulis sebagai spek sendiri sesudah C3 dipakai.

## 9. Di luar cakupan

Akses dari internet (Vercel atau lainnya): mengubah model ancaman dan butuh spek sendiri. Approve draf lewat chat (fase 3 kontrol) selain lewat langkah `prepare`/`confirm` ini; streaming; banyak pengguna; penyimpanan percakapan di browser; mengubah viewer.

## 10. Keputusan untuk Atha

| | Pertanyaan | Usul Claude |
|---|---|---|
| K1 | Port dan fase | 8712 baru dulu (C1-C3), serap 8711 di C4 |
| K2 | Frontend | JS statis tanpa build tool, ditulis Claude; atau React bila Atha menginginkan |
| K3 | Biaya lapisan bahasa bebas (v2) | putuskan saat spek v2; pastikan dulu apakah langganan Claude mencakup pemakaian lewat aplikasi sendiri (setahu Claude: API ditagih terpisah; belum diperiksa) |
| K4 | Batas harian UI | $2,00 bawaan, ubah di config |
| K5 | Repo yang boleh di mode Issue | tetap `argus-viewer` dan `argus-ledger` (SPEC_ISSUE_WRITER K2) |
| K6 | Menunggu seminggu antara C1 dan C2 | ya |
