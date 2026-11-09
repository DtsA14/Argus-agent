# Spek: UI kontrol (fase 0)

Status: **disetujui Atha 2026-11-07** ("Ok gw setuju bro. Boleh merge"): K1-K6 sesuai usul Claude (bagian 5), dengan
tambahan integritas dan audit dari review GPT. **Amandemen 1 (usul Claude, disetujui Atha 2026-11-07, #346):**
ringkasan terstruktur buatan harness untuk halaman approve (D1 `summary`, D2, D4 urutan halaman, F6), karena memecah
`DRAFT_REVIEW.md` per heading bisa dipalsukan oleh teks tidak tepercaya di dalamnya. Hanya dokumen; tidak ada kode di PR ini. Lanjutan butir PENDING "UI kontrol interaktif" (Atha 2026-10-30) dan `docs/Reconciliation.md`
bagian 6-7 (ADR-007). Fase 1 dirinci untuk dikoding; fase 2-4 hanya kerangka dan keputusan, dispek lagi sebelum dikoding.

## 1. Masalah dan ukuran

Hari ini setiap keputusan manusia atas job lewat chat: Claude membaca `DRAFT_REVIEW.md` di terminal, meringkas, lalu
Atha bilang "approve"/"go live", dan Claude menjalankan `argus approve <job> --sha ...`. Atha tidak bisa membaca draf
sendiri dari HP, dan persetujuannya tidak tercatat di job (ADR-007: "persetujuan run di chat tidak tercatat").

Yang ingin dicapai, bertahap: (1) Atha **membaca** draf dan hasil judge di HP; (2) Atha **menolak/membuang** job dari HP;
(3) Atha **menyetujui** draf dari HP, tercatat di job; (4) tombol staging. Ukuran keberhasilan: menit Atha per keputusan
(`PENDING.md`, supervisi per pilot) dan jumlah keputusan yang tidak lagi lewat Claude. Bukan ukuran: jumlah fitur.

## 2. Yang sudah ada (dan tidak berubah)

- **Viewer** (`SPEC_PWA_VIEWER.md`): aplikasi React yang ditulis agen, disajikan proxy harness di `127.0.0.1:8710`,
  **hanya GET**, allowlist tiga path API (`/api/summary`, `/api/jobs`, `/api/jobs/<id>`), CSP ketat, cek `Host`, tanpa
  penyimpanan di browser (A1-A5). API diteruskan ke argus-ledger staging lewat socket.
- **Snapshot data** (`SPEC_STAGING_REAL_DATA.md`, `router/stage_data.py`): `job.json` dan ledger setiap job diproyeksikan
  lewat allowlist field, dipindai pola key, dipublikasikan read-only; diperbarui monitor setiap 15 menit. **Isi draf tidak
  ikut** (issue, rencana, tes, konteks riset).
- **Akses HP**: kunci SSH `iphone-viewer` dengan `restrict,port-forwarding,permitopen="127.0.0.1:8710"`, perintah paksa
  `sleep`. Port tidak pernah dibuka ke publik.
- **Approve**: `argus approve <job> --sha <12+>` terikat sha draf yang dilihat, menolak draf berpenanda konflik, menampilkan
  batas biaya dan meminta konfirmasi, lalu menjalankan agen (menit). Key dari `--key-file`.

## 3. Fase 1: halaman review draf, read-only

**Tujuan:** di viewer, job `AWAITING_APPROVAL` (dan job sesudahnya) punya halaman yang menampilkan review draf yang
sama dengan yang dibaca Claude, plus vonis judge bila ada. Tidak ada tombol, tidak ada penulisan.

Dua pilihan jalur (keputusan K1):

**Jalur A (usul Claude): lewat snapshot dan viewer yang ada.** Tanpa port baru, tanpa izin baru di kunci HP. Viewer dan
argus-ledger ditulis agen Argus (shadow batch), jadi fase 1 sekalian menjadi pekerjaan nyata untuk Argus.
- **D1 (harness, jalur ketat, `stage_data`):** proyeksi ditambah, per job, berkas review draf terakhir
  (`runs/<job>-dN/DRAFT_REVIEW.md`) dan berkas judge terakhir (`JUDGE-jN.md`), masing-masing dengan sha256-nya dan sha
  draf (`draft_sha256` dari `job.json`). Syarat publikasi: UTF-8 valid; karakter kontrol selain `\n`/`\t` dibuang;
  ≤ 256 KB per berkas (lebih besar: dipotong di batas baris dengan penanda `[dipotong harness: N byte]`); lolos pemindaian
  pola key yang sudah ada (gagal → berkas tidak dipublikasikan, job tetap ada, alasan di manifest tanpa nilai). Berkas
  lain di `runs/` tetap tidak ikut.
  **Integritas (masukan review GPT, Atha 2026-11-07):** review, `draft.json` dan sha berasal dari **stage yang sama**
  (`runs/<job>-dN/`). Saat snapshot dibaca, sha kanonik `draft.json` di direktori itu dihitung ulang dan harus sama dengan
  `stages.dN.draft_sha256` di `job.json`; berbeda atau tidak terbaca → review stage itu tidak dipublikasikan (alasan di
  manifest). Jadi sha yang tampil di HP selalu sha draf yang reviewnya tampil. `DRAFT_REVIEW.md` sendiri tidak memuat sha.
  **Ringkasan terstruktur (amandemen 1).** Per stage draf yang lolos cek integritas, harness juga menerbitkan `summary`
  (JSON), dibangun dari `draft.json` dan `check_report.json` di direktori stage yang sama dengan fungsi yang sama yang
  merender `DRAFT_REVIEW.md` (`codetask/drafter.py`), bukan dengan membaca markdown. `check_report.json` ikut cek
  integritas: `draft_sha256`-nya harus sama dengan sha hasil hitung ulang; berbeda → `summary` stage itu tidak terbit.
  Isi, tidak lebih:
  - `draft_sha256`; `cost`: `{"usd", "cap_usd"}` stage dari `job.json`;
  - `conflicts`: daftar entri penanda konflik (`conflict_entries`, gerbang yang sama dengan `argus approve`);
  - `red`: per tes baru yang wajib lulus, `{"validation", "test", "status", "reason"}`, `reason` = baris `red_lines`
    (tipe, berkas, baris pertama pesan; tercatat tidak ada → teks "how it fails was not recorded");
  - `plan`: `{"files", "steps", "risks"}`; `scope`: `{"writable", "protected"}`; `warnings` (peringatan scope harness);
  - `unverifiable`.
  Setiap string melewati aturan D1 (karakter kontrol dibuang, pemindaian key) dan batas panjang per field seperti di
  `DRAFT_REVIEW.md` (`cell`); daftar dibatasi jumlahnya dengan penanda `[dipotong harness: N]`. Field lain dari draf
  (isi tes, issue, konteks riset) **tidak** masuk `summary`; itu hanya ada di teks lengkap.
- **D2 (argus-ledger, issue untuk agen, jalur cepat):** `GET /api/jobs/<id>/draft` → `{"draft_sha256", "summary": {...},
  "review": {"sha256", "text"}, "judge": null | {"sha256", "text"}}` dari snapshot; 404 bila tidak ada. `summary`
  diteruskan apa adanya (ledger tidak menghitung ulang atau menambah field).
- **D3 (harness, jalur ketat, proxy):** allowlist A1 ditambah tepat satu bentuk, `/api/jobs/<id>/draft`. Aturan lain proxy
  tidak berubah (GET/HEAD saja, tanpa query, `no-store`).
- **D4 (argus-viewer, issue untuk agen, jalur cepat):** halaman `/jobs/<id>/draft`: teks ditampilkan sebagai teks
  (`<pre>` atau subset markdown tanpa HTML mentah; **tidak** `dangerouslySetInnerHTML`), 12 karakter pertama sha draf
  terlihat jelas (itu yang nanti diapprove), tautan dari halaman job. **Urutan (amandemen 1), dari atas:**
  1. kartu keputusan dari `summary`: job, state, sha12, biaya stage vs cap, `conflicts` (bila ada, menonjol);
  2. alasan merah per tes (`summary.red`), dikutip apa adanya: bagian terpenting, karena alasan merah yang bukan
     perilaku yang diminta issue berarti jangan approve (pilot prompt injection V4);
  3. rencana, scope, `warnings`, `unverifiable`;
  4. teks lengkap review (`review.text`) di bawah, tertutup secara default; judge (bila ada) sebagai bagian terpisah.
  Struktur halaman hanya dari field `summary`; viewer **tidak** memecah atau mencari di `review.text`/`judge.text`
  (heading di teks itu bisa berasal dari konteks riset atau kode tes). Vonis judge baru ada sesudah agen
  (`REVIEW_READY`), jadi bukan bagian keputusan approve draf.
- Kesegaran: draf muncul paling lambat saat refresh snapshot berikutnya (≤ 15 menit). Lebih cepat (refresh sesudah
  `argus code` selesai) bukan bagian fase 1.

**Jalur B: service kontrol `127.0.0.1:8711` sejak fase 1.** Kode harness membaca `jobs/` read-only dan merender review
sebagai HTML yang di-escape. Lebih sedikit bagian (tidak lewat ledger dan viewer), dan fase 2-4 tinggal menambah aksi di
service yang sama. Harganya: port kedua dan `permitopen` kedua di kunci HP sejak awal, satu service always-on lagi, dan
tidak ada pekerjaan untuk agen.

**Jaminan fase 1 (jalur A), dites dan di-mutant:**
- F1. Tidak ada berkas dari `runs/` selain `DRAFT_REVIEW.md` dan `JUDGE-*.md` di snapshot; tidak ada berkas lewat
  symlink/hardlink (pola `openat`/`O_NOFOLLOW` yang sudah ada).
- F1b. Sha yang dipublikasikan = sha kanonik `draft.json` stage yang sama, dihitung ulang (D1 integritas); mutant: sha
  dari stage lain atau dari `approval` → tes gagal.
- F2. Berkas dengan pola key tidak dipublikasikan; manifest menyebut alasan tanpa nilai.
- F3. Batas ukuran dan karakter kontrol seperti di D1.
- F4. Proxy: path baru hanya untuk id job yang sah; varian lain (`/draft/x`, query, trailing slash, `..`) 404; POST 405.
- F5. Isi draf adalah **data tidak tepercaya** (issue dan konteks riset bisa memuat teks web; pilot prompt injection v0
  memuat baris injeksi di draf): viewer merendernya sebagai teks; CSP yang ada tetap berlaku.
- F6 (amandemen 1). `summary` hanya dari `draft.json` dan `check_report.json` stage yang sama dan lolos cek integritas;
  `check_report.json` dengan sha lain → tidak ada `summary`. Mutant: `red` dari stage lain, dari `DRAFT_REVIEW.md`, atau
  tanpa cek sha `check_report.json` → tes gagal. Satu tes dengan baris `## Why they fail now` palsu di konteks riset:
  `summary.red` tetap sama dengan cek merah.

**Implementasi D1+D3 (PR jalur ketat, 2026-11-07).** Per job, di snapshot: `jobs/<job>/draft/meta.json`, `review.md`,
`judge.md` (bukan di `runs/`: argus-ledger membaca `runs/` sendiri). `meta.json` = `{"stage", "draft_sha256", "review":
null | {"sha256"}, "summary": null | {...}, "judge": null | {"file", "sha256"}}`; `summary` persis field amandemen 1
(`draft_sha256`, `cost`, `conflicts`, `red`, `plan`, `scope`, `warnings`, `unverifiable`). Stage = stage draf dengan nomor
terbesar; judge = `JUDGE-jN.md` dari stage judge terakhir yang `draft_sha256`-nya sama dengan draf itu (review #357: vonis atas draf lama tidak pernah tampil di samping draf baru). Selain karakter kontrol, karakter format tak terlihat (bidi override/isolate, zero-width, BOM) juga dibuang (review #357), karena manusia menyetujui apa yang tampil; berkas sumber > 16 MB tidak dibaca. Gagal cek sha `draft.json` → tidak ada `draft/` sama sekali; review atau
judge yang gagal D1 (bukan UTF-8, pola key, link) → `null` di meta, berkasnya tidak ada; `summary` yang gagal (sha
`check_report.json` lain, pola key di salah satu string) → `null`. Alasan di manifest `withheld` (`{job, why}`, tanpa nilai).
Daftar > 50 → 49 butir + penanda `[dipotong harness: N]` (untuk `red`: butir dengan `test` = penanda, field lain kosong).
Pemindaian key `summary` per string (bukan bentuk JSON-nya, yang meng-escape `"`). `validate()` mengulang D1 atas berkas yang
ditulis (field meta, sha tiap teks, UTF-8, karakter kontrol, ukuran, key per string, tidak ada berkas lain).
Untuk issue D2: `GET /jobs/<id>/draft` → `{"draft_sha256": meta.draft_sha256, "summary": meta.summary, "review": null |
{"sha256", "text": isi review.md}, "judge": null | {"sha256", "text": isi judge.md}}`; 404 bila `draft/meta.json` tidak
ada. `review` bisa `null` (bentuk D2 di atas dilonggarkan untuk itu). Cek pada data nyata `~/pilot3a_live` (76 job): 71
draf terbit; 7 review ditahan karena `PASSWORD = "..."` di tes login argus-ledger (positif palsu yang disengaja, F2; ringkasannya
tetap terbit), 3 stage draf tanpa `draft_sha256` (draf gagal). Mutants 25/25. **A1 diperluas (Atha 2026-11-07, digabung ke PR ini):** allowlist lama menolak model gateway (`openrouter:vendor/nama[:varian]`) dan log `stage_started`, sehingga 36 dari 112 job (semua job yang di-judge dan job riset) tidak ada di snapshot dan halaman draf tidak bisa muncul untuk mereka. Sekarang 112/112 job, 81 draf, 10 dengan judge; argus-ledger Stage 13 di `ledger_py312_up2` (tanpa network) menjawab snapshot itu: `/summary` 112 job, `skipped` 0, semua `/jobs/<id>` 200. Setelah merge, refresh monitor berikutnya dari `~/pilot3a_live` menerbitkannya ke staging live. Mutants 3/3.

**Urutan PR fase 1 (jalur A):** satu PR jalur ketat untuk D1+D3 (spek ini bagian 3, mutants, `/code-review medium` dan
`/security-review`, `verify.sh`, "merge" Atha), lalu issue D2 dan D4 untuk Argus (dua job, shadow), lalu deploy viewer dan
ledger lewat `PLAN.md` dengan satu "go live". Mulai **sesudah up2** (D1 dan D3 menyentuh jalur staging yang dipakai up2).

**Amandemen 2: kalimat untuk orang awam (Atha 2026-11-08, "gw kurang ngerti issue nya jadi cenderung approve aja").**
Ukuran K6 bersih (draf 025: 3 menit, approve) menunjukkan keputusan cepat tetapi tanpa paham isi: approve yang tidak
dipahami bukan pengawasan. Harness meminta drafter menulis `for_human`: satu-dua kalimat dalam `drafter.for_human_language`
(config, sekarang `Indonesian`) untuk orang yang tidak membaca kode, tentang apa yang akan ia lihat berubah.
- Dibekukan di policy drafter (`drafter_policy.for_human`); job lama dan policy tanpa bahasa: tidak diminta, dan
  `for_human` yang tetap dikirim ditolak sebagai argumen ("not asked for").
- Diminta, tidak wajib: draf tanpa `for_human` tetap diterima (halaman menulis bahwa kalimat itu tidak ada). Bila dikirim,
  dicek `acceptance/draft.py` (`for_human_problem`): string satu baris, 1-400 karakter, tanpa karakter kontrol (C0, DEL,
  C1).
- Bagian dari `draft.json`, jadi sha yang di-approve mencakupnya: kalimat yang dibaca Atha terikat ke draf yang
  di-approve. `DRAFT_REVIEW.md` menampilkannya di bagian "For the human (written by the drafter, not checked by a test)",
  sebelum Plan.
- D1: `summary.for_human` (string dibersihkan seperti field ringkasan lain, maks 500, atau `null`), ikut pemindaian key per
  string (key → `summary` null). argus-ledger meneruskan `summary` apa adanya (issue 016), jadi tanpa perubahan ledger.
- Viewer (issue terpisah, jalur cepat): kalimat itu di baris pertama kotak Ringkasan dengan label bahwa ia ditulis model
  dan tidak dicek tes; bagian teknis di bawahnya tertutup.
- Batas: kalimat ditulis model dari issue dan rencana; tes tidak memeriksanya. Ia membantu membaca, bukan bukti.

## 4. Fase 2-4: aksi (kerangka; dispek lagi sebelum dikoding)

Aksi selalu lewat **service kontrol terpisah** di `127.0.0.1:8711` (kode harness, stdlib, `systemd --user`), bukan lewat
proxy viewer: proxy tetap GET-only selamanya, sehingga kode agen (viewer, ledger) tidak pernah berada di jalur aksi.

- **Fase 2, aksi tanpa biaya:** `reject` dan `abandon` (dirinci di 4a).
- **Fase 3, aksi berbayar:** `approve` (agen jalan), mungkin `redraft`/`retry`.
- **Fase 4, staging:** `deploy`/`rollback` untuk satu `PLAN.md`.

Aturan yang sudah pasti untuk semua aksi:
- C1. Service memanggil perintah `argus` yang sama (proses anak `scripts/argus.py ... --key-file ...`), jadi setiap
  gerbang yang ada tetap berlaku: sha draf, penanda konflik, cap, ledger, crash-resume. Service tidak punya jalan pintas.
- C2. Hanya `POST`, dengan token CSRF per halaman, cek `Origin` dan `Host` (`127.0.0.1:8711`/`localhost:8711`), tanpa CORS.
  Mencegah situs lain di browser HP memicu aksi lewat port forward.
- C3. Setiap aksi tercatat di `job.json` (`log`: `what`, `by: "ui"`, waktu, job, sha yang dilihat, hasil, dan untuk aksi
  berbayar biaya yang terpakai saat selesai), menutup gap ADR-007 untuk aksi lewat UI. Penolakan juga tercatat.
- C4. Approve hanya untuk sha yang tampil di halaman dan dicek terhadap draf **live**, bukan snapshot (seperti `--sha`
  sekarang). Halaman bisa sampai 15 menit tertinggal: draf yang sudah berganti (redraft) → approve ditolak, Atha membaca
  ulang. Klik ganda ditolak oleh state job.
- C5. Aksi panjang (agen) jalan sebagai proses latar dengan log; halaman hanya menampilkan status. Satu aksi per job
  sekaligus (lock job yang ada).
- C6. Batas biaya dicek **di server** (K3), tidak dari form.

## 4a. Amandemen 3: fase 2 dirinci, fase 3 dikunci desainnya (usul Claude, Atha 2026-11-09 "Ok ikut saran lu")

Fase 2 (reject, abandon) dikoding lebih dulu sebagai kerangka keamanan tanpa risiko uang; fase 3 (approve) memakai
kerangka yang sama dan dikoding sesudah fase 2 dipakai. Jalur ketat: kode harness yang ditulis Claude, review, mutants,
`verify.sh`, merge oleh Atha. Agen (viewer, ledger) tidak menulis bagian mana pun dari jalur aksi.

**F1. Service.** `router/control.py`, perintah `argus control serve`, unit `systemd --user` `argus-control`, stdlib
(`http.server`), satu proses, satu permintaan sekaligus. Bind `127.0.0.1:8711` saja (konstanta, tidak pernah `0.0.0.0`
atau `localhost`, tidak pernah 8000/8710). Membaca dan mengubah job **live** (`jobs/` di checkout `~/pilot3a_live`),
bukan snapshot: halamannya tidak tertinggal 15 menit. Tidak memegang key; fase 3 hanya meneruskan path `--key-file`.

**F2. Rute (semua lainnya 404, metode lain 405).**
- `GET /`: job yang punya aksi di fase yang aktif (`AWAITING_APPROVAL`, `DRAFT_FAILED`, `REVIEW_READY`,
  `REVIEW_INVALID`, `AWAITING_RESEARCH_REVIEW`), terbaru dulu, masing-masing tautan ke halamannya.
- `GET /jobs/<id>`: HTML buatan server, semua teks di-escape: id, state, sha12 draf terakhir (bila ada), biaya, tautan ke
  halaman draf viewer (`http://localhost:8710/jobs/<id>/draft`), lalu satu form per aksi yang diizinkan state itu.
  Reject: kolom alasan **wajib** (1-300 karakter, satu baris, tanpa karakter kontrol). Abandon: alasan **opsional**
  (kosong → `abandoned from the phone`).
- `POST /jobs/<id>/reject`, `POST /jobs/<id>/abandon` (fase 2); `POST /jobs/<id>/approve` (fase 3). Body
  `application/x-www-form-urlencoded` maks 4 KiB: `token`, `sha` (sha12 yang tampil; wajib bila job punya draf),
  `reason`. Jawaban: halaman job dengan pesan hasil (200; memuat ulang mengirim token yang sudah terpakai, jadi ditolak), atau penolakan yang menyebut sebabnya (400/403/404/409/413).
- `<id>` harus cocok `^j\d{8}_\d{6}_[0-9a-f]{4}$` dan direktorinya ada; selain itu 404 tanpa menyentuh disk lain.

**F3. Gerbang setiap POST** (urutan, berhenti di yang pertama gagal; tidak ada aksi sebelum semuanya lolos):
1. `Host` tepat `127.0.0.1:8711` atau `localhost:8711`.
2. `Origin` ada dan tepat `http://127.0.0.1:8711` atau `http://localhost:8711`; `Sec-Fetch-Site`, bila ada, `same-origin`.
   Tanpa `Origin` → ditolak (Safari iOS mengirimnya pada POST form).
3. Isi form valid (alasan, sha 12 hex; maks 8 field, tanpa field ganda). Diperiksa **sebelum** token (code review
   2026-11-09): alasan yang ditolak karena bentuknya tidak menghanguskan token, dan ditulis kembali ke form.
   Alasan: satu baris, tanpa karakter kategori Unicode C* (kontrol, format/bidi, privat, belum ditetapkan) dan tanpa
   pemisah baris/paragraf (Zl, Zp).
4. `token` = HMAC-SHA256(rahasia, `aksi|job|sha|waktu terbit`), terbit di halaman itu, umur ≤ 30 menit, **sekali pakai**
   (yang terpakai dicatat per MAC, dan waktu terbit hanya satu ejaan: angka tanpa nol di depan).
   Rahasia 32 byte acak dibuat saat service mulai, hanya di memori (restart membatalkan semua halaman yang terbuka).
5. `sha` harus sha12 draf terakhir job **saat ini** (kosong hanya bila job tidak punya draf); halaman yang dibuka sebelum
   draf ada, atau draf yang tidak terbaca, → ditolak (409) tanpa memanggil CLI.
6. Aksi dipanggil lewat CLI yang sama (C1): proses anak `scripts/argus.py reject|abandon <job> <reason> --sha <sha12>
   --via ui`; gerbang state, lock job dan cek sha ada **di `router/job.py` di bawah lock**, bukan di service (C4). Klik
   ganda: token kedua sudah terpakai; kalaupun lolos, state job menolaknya.

Satu permintaan sekaligus; klien yang macet diputus sesudah 10 detik.

Header setiap jawaban: `Content-Security-Policy: default-src 'none'; style-src 'self'; form-action 'self';
frame-ancestors 'none'; base-uri 'none'`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Cache-Control:
no-store`, `X-Content-Type-Options: nosniff`. Tanpa JavaScript, tanpa CORS, tanpa cookie.

**F4. Perubahan CLI (jalur ketat, PR yang sama).** `reject` dan `abandon` menerima `--sha <12+ hex>` (opsional di CLI;
bila diberikan dan job punya draf, harus awalan sha draf terakhir, dicek di bawah lock, beda → ditolak "draft changed")
dan `--via ui` (satu-satunya nilai). Entri log `job.json` dari `job.move` mendapat `via: "ui"` dan `sha` bila ada, di
samping `by`, `reason`, waktu (C3). Tanpa `--via`, perilaku CLI hari ini tidak berubah.

**F5. Audit di luar job.** Setiap POST (berhasil atau ditolak di gerbang mana pun) ditulis satu baris JSON (aksi yang lolos gerbang: satu baris `attempt` sebelum CLI dan satu baris hasil sesudahnya) ke
`~/.local/state/argus-control/audit.jsonl`: waktu, path, job (bila valid), gerbang yang menolak atau hasil CLI (exit,
baris terakhir), tanpa isi token. Pengganti C3 untuk penolakan sebelum job tersentuh (id tidak valid, token, Origin):
tidak menulis ke `job.json` job yang mungkin bukan job.

**F6. Akses HP.** Kunci `iphone-viewer` di `~/.ssh/authorized_keys` mendapat `permitopen="127.0.0.1:8711"` kedua (K5),
diubah Claude atas "ok" Atha saat fase 2 deploy; Atha menambah forward 8711 di Termius. Tidak ada port publik.

**F7. Viewer (jalur cepat, issue terpisah).** Halaman draf mendapat tautan `Decide` ke `http://localhost:8711/jobs/<id>`
(navigasi biasa; proxy 8710 tetap GET-only dan tidak meneruskan apa pun ke 8711).

**F8. Fase 3 (desain dikunci, kode nanti).** `POST /jobs/<id>/approve` dengan `sha` yang tampil: gerbang F3, lalu server
menolak bila `max_usd` job > $1,00 (K3, dicek di server dari `job.json`), lalu menjalankan `argus approve <job> --sha
<sha12> --key-file <path dari config service> --yes --via ui` sebagai **proses latar** dengan log
`jobs/<id>/ui-approve-<waktu>.log` (C5); halaman menampilkan "running" dari state job. Approve dari UI hanya untuk job
yang drafnya tidak berpenanda konflik (gerbang CLI yang ada).

**F9. Tes wajib (masing-masing gagal bila jaminannya rusak; mutants).** Bind hanya 127.0.0.1:8711; `Host` asing →
ditolak; `Origin` tidak ada / asing / `null` → ditolak; `Sec-Fetch-Site: cross-site` → ditolak; token tidak ada, salah,
kedaluwarsa, untuk aksi atau job lain, sudah terpakai → ditolak; GET tidak pernah mengubah job; id `..`, `%2F`, id tidak
cocok pola → 404; alasan kosong pada reject, > 300, multi-baris, karakter kontrol → ditolak; sha draf berganti → ditolak
oleh CLI dan job tidak berubah; state yang tidak boleh (mis. `APPLIED`) → ditolak oleh CLI; job sedang dikunci → ditolak;
teks job berisi `<script>`/`<img onerror>` tampil sebagai teks; setiap POST menulis satu baris audit tanpa token; aksi
berhasil menulis `via: "ui"` dan `sha` ke log job; header keamanan ada di setiap jawaban; body > 4 KiB ditolak.

## 5. Keputusan untuk Atha

| | Pertanyaan | Usul Claude | Dibutuhkan untuk |
|---|---|---|---|
| K1 | Fase 1 lewat jalur A (snapshot + viewer, ditulis agen) atau B (service 8711 sejak awal)? | A | fase 1 |
| K2 | Siapa yang boleh menekan tombol aksi? | Hanya Atha (kunci HP). Claude tetap lewat CLI, tidak lewat UI | fase 2 |
| K3 | Batas biaya per aksi lewat UI? | `--max-usd` tetap di server, ≤ $1,00 per job (batas pilot sekarang); di atasnya tetap lewat terminal | fase 3 |
| K4 | Tombol menggantikan "go live" di chat? | Ya untuk approve job (fase 3); staging (fase 4) tetap lewat chat sampai fase 3 terbukti | fase 3-4 |
| K5 | `permitopen="127.0.0.1:8711"` kedua di kunci `iphone-viewer`? | Ya, saat fase 2 dimulai (bukan sekarang bila K1 = A) | fase 2 |
| K6 | Kapan? | Fase 1 sesudah up2; fase 2 sesudah Atha memakai fase 1 dan menilai apakah membaca draf di HP memang menghemat waktu | semua |

## 6. Tidak dikerjakan

Akses publik, DNS/TLS, login/password (aksesnya kunci SSH yang dibatasi), pengguna kedua, Claude menekan tombol,
mengubah draf dari UI, notifikasi push (ntfy sudah ada untuk alert staging), production (M9).
