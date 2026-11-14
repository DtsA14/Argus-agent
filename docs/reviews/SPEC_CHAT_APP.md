# Spec CHAT-APP: satu aplikasi chat di HP (viewer 8710 dan kontrol 8711 digabung)

Status: **DRAF, menunggu keputusan Atha**; kode belum disentuh. Ditulis Claude 2026-11-14 atas permintaan Atha ("aplikasi yang siap pakai dan simple kayak Claude app, satu chatbox dengan fitur terintegrasi"). Belum ditinjau Opus.
Jawaban Atha 2026-11-14: fitur v1 = **tulis issue/PRD, lihat status job, riset**; akses **tetap lewat SSH forward**; gaya **chat plus panel samping**. Approve/reject/abandon lewat percakapan **tidak** masuk v1.

## 1. Yang ada dan tidak berubah

- **8710** viewer: `router/stage_viewer.py` menyajikan app React (`~/argus-viewer`), proxy **hanya GET**, allowlist `/api/summary|scoreboard|jobs|jobs/<id>[/draft]`, CSP ketat, cek `Host`, tanpa penyimpanan browser.
- **8711** kontrol: `router/control.py` (HTML dari server): reject, abandon, penulis issue (`router/control_issues.py`, rute `/issues*`), gerbang POST F3 (Host, Origin, token sekali pakai, form, audit) dan F5.
- **CLI** yang sudah memegang semua jaminan: `argus issue new|reply|start|abandon`, `argus research`, `argus status`. Lock job, gerbang state, sha draf, uang (`LLMCaller`) tetap di sana.
- **Kunci HP**: `permitopen="127.0.0.1:8710"` saja.

## 2. Prinsip

1. **Aplikasi hanyalah klien tipis.** Ia tidak punya logika uang, approve, atau sandbox; tiap aksi memanggil CLI yang sama lewat gerbang F3 yang sama. Tidak ada panggilan model baru di luar `harness/llm.py`.
2. **Tanpa penerjemah niat berbasis model.** Pesan masuk ke satu dari tiga mode yang dipilih Atha (chip di bawah kotak input: `Issue`, `Status`, `Riset`; bawaan mengikuti percakapan terakhir). "Status" tidak memanggil model sama sekali (membaca snapshot). Ini menjaga uang deterministik dan menghindari agen yang memilih aksi sendiri.
3. **Tidak ada aksi yang mengubah jaminan di v1.** `start` issue tetap lewat layar ringkasan dengan token terikat sha256 issue (SPEC_ISSUE_WRITER bagian 6); approve draf, reject, abandon tetap di halaman yang ada. Chat hanya menaut ke sana.
4. **Satu origin.** Pengguna melihat satu alamat (`127.0.0.1:8710`); tidak ada port kedua di kunci HP.

## 3. Bentuk

Layout (HP): kotak input di bawah; aliran percakapan di atas, hasil sebagai **kartu** di dalam aliran (kartu job: state, biaya dari cap, tahap, tautan draf; kartu issue: ringkasan dan tombol `Start` yang membuka layar ringkasan; kartu riset: status dan tautan hasil). Panel samping (geser dari kiri): daftar percakapan/job (issue, riset, job code) dengan state, papan skor, dan pengaturan (bahasa, mode bawaan). Di layar lebar panel selalu tampak.

Halaman yang sudah ada (draf, job, papan skor) tetap, dan dibuka dari kartu. Tabel papan skor yang terpotong di HP (PENDING) diselesaikan di sini sebagai kartu.

## 4. Penggabungan port (jalur ketat)

Pilihan yang diusulkan: **A, satu origin di 8710.** Proxy viewer tetap hanya meneruskan GET; **rute `/chat/*` ditangani proses kontrol yang sama dengan kode F3 yang sudah ada, dimount di bawah awalan itu**, bukan oleh proxy yang membuka POST ke mana saja. Konsekuensi yang harus ditulis dan diuji:

- proxy mendapat daftar **tetap** rute POST (`/chat/issue/new|reply`, `/chat/research/new`) yang diteruskan ke handler kontrol; semua lainnya tetap 405. Jaminan lama "proxy tidak meneruskan POST" menjadi "proxy meneruskan POST hanya pada daftar tetap itu";
- `Host` dan `Origin` diterima hanya `127.0.0.1:8710`/`localhost:8710` (8711 dan 127.0.0.1:8710 ditolak oleh tes kontrol lama; tes diubah, bukan dilonggarkan);
- CSP viewer (`default-src 'self'`) dan CSP halaman kontrol (`form-action 'self'`) disatukan dengan yang paling ketat yang cukup; chat memakai `fetch` same-origin, bukan form;
- token sekali pakai F3.3 tetap per halaman/aksi; audit F5 tetap satu baris per POST;
- port 8711 tetap tersedia di VM untuk Claude (tanpa `permitopen` HP) selama masa transisi, lalu dimatikan setelah satu rilis stabil.

Alternatif yang ditolak untuk v1: **B** (dua service, tampilan sama; masih dua port) dan **C** (satu proses baru; menyentuh deploy dan rollback staging).

## 5. Urutan kerja

| Tahap | Isi | Jalur |
|---|---|---|
| P0 | Spek ini, tinjau Opus, keputusan Atha | – |
| P1 | Kerangka chat di app React lewat issue ke Argus: aliran, kartu, chip mode, panel samping, mode **Status** (hanya membaca snapshot; belum ada POST) | viewer, job kecil (≈ $0,05-0,15 per irisan) |
| P2 | Mode Issue: rute `/chat/issue/*` di kontrol, di bawah gerbang F3 | **ketat** |
| P3 | Penggabungan origin (bagian 4) dan pensiun port 8711 dari alur HP | **ketat** |
| P4 | Mode Riset: `/chat/research/new`, kartu hasil | **ketat** (menyentuh biaya riset via CLI yang ada) |
| P5 | Poles: bahasa, kosong dan galat, pemulihan sesudah koneksi putus | viewer |

P1 berguna tanpa P2 sampai P4 (Atha sudah bisa melihat status dalam bentuk chat), dan tidak mengubah satu pun jaminan.

## 6. Tes wajib (gagal bila jaminan rusak; mutan)

Proxy: hanya tiga rute POST tetap yang diteruskan, POST lain 405, GET `/chat/*` tidak ada, Host/Origin 8711 ditolak. Kontrol di bawah awalan: semua tes F9 yang ada tetap lulus pada rute baru; token terikat aksi dan sha; pesan tidak pernah lewat argv; key tidak pernah di halaman atau audit; teks percakapan berisi `<script>` tampil sebagai teks. Mode Status: nol panggilan model (tes mengunci). Mode Issue/Riset: batas biaya dari config, bukan form; model tanpa harga ditolak. Viewer: tes komponen untuk kartu, chip, panel, dan keadaan kosong/galat.

## 7. Di luar cakupan v1

Approve, reject, abandon dari percakapan (fase 3 tetap ditahan); jawaban huruf demi huruf (streaming; menyentuh `harness/llm.py`); akses dari internet (SSH forward tetap); login banyak pengguna; penyimpanan percakapan di browser.

## 8. Keputusan untuk Atha

| | Pertanyaan | Usul Claude |
|---|---|---|
| K1 | Penggabungan port | A (bagian 4). B bila A terlalu berat; C ditolak |
| K2 | Mulai dari P1 (tanpa mengubah jaminan) | Ya, P1 dulu; P2-P4 sesudah P1 dipakai satu minggu |
| K3 | Mode lewat chip, bukan model yang memilih | Ya (prinsip 2) |
| K4 | Daftar repo yang boleh di mode Issue | Tetap `argus-viewer` dan `argus-ledger` (SPEC_ISSUE_WRITER K2); Argus-agent tidak |
| K5 | Pensiun 8711 dari HP | Sesudah satu rilis stabil P3 |
