# Spek: chatbox penulis issue (UI kontrol fase 3c)

Status: **disetujui Atha 2026-11-09** ("Ok issue bahasa inggris. Semuanya ok bro. Merge"): K1-K6 sesuai bagian 9 (K4 flash dulu). Atha 2026-11-09: "Kalo gw pengen nulis issue di
chatbox argus" → "Chatbox aja sekalian". Hanya dokumen; kode menyusul per bagian 10, jalur ketat. Melanjutkan
`SPEC_CONTROL_UI.md` 4a (service `127.0.0.1:8711`, gerbang F3): chatbox adalah halaman baru service itu, bukan viewer.

## 1. Masalah dan ukuran

Hari ini issue ditulis Claude di terminal: membaca kode dan tes lama repo, mencari bentrok, menulis aturan dengan contoh
eksplisit, daftar tes, dan baris Environment. Atha tidak bisa memulai pekerjaan dari HP, dan kualitas issue bergantung pada
Claude. Pengalaman 2026-11-08/09: sebagian besar draf yang ditolak berasal dari issue (030 tes menyimpang karena contoh
kurang tegas; 032 mengunci `.stages td` yang dibutuhkan 033; 037 bentrok dengan kelas persis 032).

Yang ingin dicapai: Atha menulis keinginan kasar dalam bahasa Indonesia di HP, agen **penulis issue** mengubahnya jadi issue
gaya Argus sesudah membaca repo, Atha merevisi lewat percakapan, lalu menekan **Start job** (job `code` biasa).

Ukuran: (1) persen job dari chatbox yang drafnya lolos tanpa reject/redraft karena issue (dibandingkan dengan issue tulisan
Claude, batch 026-039); (2) biaya per issue; (3) jumlah giliran percakapan per issue. Bukan ukuran: jumlah fitur.

## 2. Alur

1. `GET /issues/new` (8711): pilih repo dari daftar tetap (bagian 9, K2) dan tulis pesan pertama (≤ 4000 karakter).
2. `POST /issues/new`: gerbang F3 (Host, Origin, token sekali pakai, form) → `argus issue new --repo <nama> --message-file
   <file> --via ui --key-file <path dari config service> --yes` sebagai proses latar. Harness membuat **job `issue`**
   (state `WRITING`), mencatat pesan Atha, lalu menjalankan giliran penulis `w1`. Halaman berpindah ke `GET /issues/<id>`.
3. `GET /issues/<id>`: percakapan sebagai kartu (pesan Atha, balasan penulis), lalu **issue saat ini** (teks penuh,
   di-escape), daftar **kemungkinan bentrok** dengan tes lama, dan **pertanyaan** penulis. Selama giliran berjalan halaman
   memuat ulang sendiri tiap 5 detik (`<meta http-equiv="refresh">`, tanpa JavaScript).
4. Atha membalas (form, ≤ 2000 karakter) → `POST /issues/<id>/reply` → `argus issue reply` → giliran `w2`, `w3`, ... Setiap
   giliran membaca seluruh percakapan dan issue terakhir.
5. **Start job** → `POST /issues/<id>/start` → `argus issue start <id> --max-usd <K3> --via ui --key-file ... --yes`:
   menjalankan `argus code --repo <path> --commit HEAD --issue-file <issue terakhir> --environment <env repo>` yang sudah
   ada (drafter, red check, `DRAFT_REVIEW.md`). Job issue berpindah ke `HANDED_OFF` dengan id job code; halaman menautkan
   halaman draf viewer begitu drafnya ada. Approve tetap jalur yang berlaku (bagian 9, K5).
6. **Discard** → `POST /issues/<id>/abandon` → `ABANDONED`.

Juga dari terminal (Claude): `argus issue new|reply|start|abandon|status`, dengan gerbang biaya dan kunci yang sama.

## 3. Job `issue` (router/issue.py)

- `kind: "issue"`, state: `WRITING` → `AWAITING_HUMAN` (giliran selesai) ⇄ `WRITING` (balasan Atha) → `HANDED_OFF`
  (job code dibuat) | `WRITE_FAILED` (giliran gagal; balasan berikutnya mencoba lagi) | `BLOCKED` (tidak bisa didanai /
  provider gagal) | `ABANDONED`. Transisi lewat tabel LEGAL seperti job lain.
- Percakapan di `job.json` `conversation`: `[{"from": "human"|"writer", "at", "text", "stage"}]`; pesan Atha dicatat
  **sebelum** gilirannya mulai (crash-resume tidak kehilangan pesan). Issue tiap giliran di `runs/<id>-wN/issue.txt`;
  `issue_sha256` dan giliran terakhir di `job.json`.
- Repo dibekukan saat job dibuat: path dan commit `HEAD` saat itu (seperti intake drafter); alat baca melihat salinan
  snapshot `runs/<id>-wN/source` (read-only), bukan repo hidup. `start` memakai commit beku itu. Bila HEAD repo sudah lain
  saat Start, halaman menyebutnya ("repo moved since the issue was written: N commits") dan Atha memilih tetap Start atau
  membalas "update to HEAD" (giliran baru dengan snapshot HEAD).
- Satu aksi per job sekaligus (lock job yang ada); giliran berjalan → balasan/start ditolak sampai selesai.

## 4. Giliran penulis (satu stage, `research/loop.py` `run_stage` + `tool_loop`)

- Role `issue_writer` (model bagian 9, K4), system prompt harness berisi **gaya issue Argus** (diturunkan dari issue
  `argus-viewer-issues/026-039`): judul satu baris; masalah dan alasan; aturan bernomor, **setiap aturan dengan contoh
  eksplisit** (nilai masuk → keluar, termasuk batas dan pembulatan); kelas/selector/teks persis bila UI; "Nothing else
  changes: ... The existing tests keep passing unchanged."; paragraf `Tests:` yang mendaftar tes dengan nilai dari contoh;
  baris terakhir `Environment: <env repo>`. Bahasa issue Inggris, balasan ke Atha bahasa Indonesia sederhana.
- Wajib sebelum submit: mencari di tes lama repo (SearchFiles) selector, teks, kelas, dan perilaku yang disentuh
  perubahan; setiap kemungkinan bentrok masuk `clashes` dengan file dan baris. Larangan: issue yang mengunci daftar kelas
  persis (pakai "also has"/"contains"), atau yang meminta perubahan di luar repo.
- Alat: `ListFiles`, `SearchFiles`, `ReadFile` pada snapshot (dari `codetask/tools.py`), lalu `SubmitIssue`:
  `{reply (Indonesia, ≤ 1200), issue (≤ MAX_ISSUE), clashes: [{file, line, why}] (≤ 10), questions: [str] (≤ 5)}`.
  Gerbang harness atas SubmitIssue (masalahnya dikembalikan ke model, maks 3 submit): issue diawali judul satu baris,
  memuat paragraf yang diawali `Tests`, baris terakhir tepat `Environment: <env repo>`, tanpa karakter kontrol/format
  (kategori C*, Zl, Zp kecuali `\n`), panjang dalam batas; `clashes.file` ada di snapshot.
- Tanpa alat tulis, tanpa jaringan, tanpa sandbox. Konten repo yang dibaca **tidak tepercaya** (bisa berisi teks injeksi):
  penulis hanya menghasilkan teks yang dibaca Atha sebelum Start; tidak ada aksi lain.

## 5. Uang

Semua panggilan lewat `LLMCaller` dalam reservasi stage yang dipulihkan dari ledger (seperti stage riset). Batas per
giliran dan per job issue (bagian 9, K3), dicek **sebelum** giliran mulai (job yang sisa batasnya tidak cukup untuk satu
giliran → `BLOCKED`, tanpa memanggil model). Model tanpa harga ditolak. `start` membuat job code dengan `--max-usd` dari
config service (≤ $1,00), dicek di server, bukan dari form. Biaya issue dan biaya job code tercatat terpisah; halaman
menampilkan keduanya.

## 6. Service 8711 (router/control.py)

- Rute baru: `GET /issues`, `GET /issues/new`, `GET /issues/<id>`, `POST /issues/new`, `POST /issues/<id>/reply`,
  `POST /issues/<id>/start`, `POST /issues/<id>/abandon`. `<id>` pola UI (`^i\d{8}_\d{6}_[0-9a-f]{4}$`, awalan `i` untuk
  job issue). Semua POST melewati gerbang F3 (Host, Origin, form sebelum token, token sekali pakai terikat
  `aksi|job|giliran terakhir|waktu`, CLI di bawah lock) dan audit F5.
- Pesan Atha: ≤ 4000 (pertama) / ≤ 2000 (balasan) karakter, multi-baris boleh (`\n`), tanpa karakter kategori C* lain,
  Zl, Zp. Ditulis ke file sementara milik service dan diteruskan sebagai `--message-file` (bukan argv).
- Repo dipilih dari `<select>` berisi nama dari config (`control.issue_repos: {nama: {path, environment}}`); service
  menolak nama lain. Path repo tidak pernah datang dari form.
- `start` menampilkan, sebelum tombol, ringkasan yang akan dijalankan: repo, commit beku, environment, batas biaya job
  code, dan sha256 issue; token `start` terikat ke sha256 issue itu (issue berubah → token tidak berlaku).
- Key: service membaca path key dari config-nya sendiri dan meneruskannya sebagai `--key-file`; key tidak pernah dibaca
  service dan tidak pernah tampil di halaman atau audit.

## 7. Viewer

Tanpa perubahan wajib. Opsional sesudahnya (issue jalur cepat): kartu "Issues" di beranda dengan job `issue` per state.
Snapshot publik hanya memuat state, biaya dan waktu job issue, **tidak** percakapan atau teks issue; percakapan hanya di
8711.

## 8. Tes wajib (gagal bila jaminannya rusak; mutants)

Job issue: transisi LEGAL; pesan dicatat sebelum giliran; crash di tengah giliran → resume tidak membeli ulang langkah yang
sudah di-commit dan tidak kehilangan pesan; giliran ditolak tanpa panggilan model bila batas tidak cukup; model tanpa
harga ditolak. Gerbang SubmitIssue: tiap aturan (judul, `Tests`, `Environment` cocok repo, karakter, panjang, clash file
ada). Alat hanya pada snapshot (path `..`, symlink keluar ditolak oleh alat yang ada). `start`: memakai issue terakhir dan
commit beku; menolak saat giliran berjalan, saat state bukan `AWAITING_HUMAN`, saat sha256 issue berubah; `--max-usd` dari
config, bukan form. Service: semua tes F9 untuk rute baru; repo di luar daftar ditolak; pesan multi-baris diterima, C*/Zl/Zp
ditolak; pesan tidak pernah lewat argv; key tidak pernah di halaman/audit; teks percakapan dan issue berisi
`<script>`/`<img onerror>` tampil sebagai teks.

## 9. Keputusan untuk Atha

| | Pertanyaan | Usul Claude |
|---|---|---|
| K1 | Bahasa | Chat bahasa Indonesia; issue bahasa Inggris: drafter menulis tes yang mencocokkan teks persis (label UI Inggris, kelas, contoh), dan kode, tes lama serta issue 026-039 berbahasa Inggris. Balasan penulis menjelaskan isi issue dalam bahasa Indonesia sederhana, jadi Atha tidak perlu membaca issue Inggrisnya |
| K2 | Repo yang boleh | `argus-viewer` (pwa_node22) dan `argus-ledger` (ledger_py312_up2); Argus-agent sendiri **tidak** (jalur ketat ditulis Claude) |
| K3 | Batas biaya | $0,10 per giliran, $0,50 per job issue; job code dari chatbox ≤ $1,00 (seperti sekarang) |
| K4 | Model penulis | **`deepseek-flash`** (Atha 2026-11-09: "coba flash dulu"). Diukur pada 5 issue pertama (bagian 1); bila drafnya sering di-redraft/ditolak karena issue, coba `deepseek-v4-pro` |
| K5 | Approve draf dari job chatbox | Tidak berubah: jalur cepat tetap Claude (delegasi 2026-11-08) atau Atha lewat Fase 3a bila sudah ada |
| K6 | Urutan kode | Sesudah Fase 3a (Approve) atau sebelum? Usul: **sebelum** — chatbox tidak bergantung pada approve dari HP, dan langsung mengurangi ketergantungan pada Claude |

## 10. Rencana kode (jalur ketat, tiap PR: tes, mutants, verify, review, "merge")

1. `router/issue.py` + `argus issue new|reply|status|abandon` + giliran penulis (stage, gerbang SubmitIssue, system
   prompt gaya issue) — dari terminal dulu, diuji Claude dengan 2-3 issue nyata argus-viewer (biaya < $0,50).
2. `argus issue start` (handoff ke `argus code`).
3. Rute 8711 (bagian 6) + deploy (restart `argus-control`, satu aksi sungguhan dari Safari sebelum dinyatakan selesai).
4. Ukur (bagian 1) pada 5 issue pertama dari HP.

## 11. Tidak dikerjakan

Streaming jawaban, JavaScript di halaman kontrol, issue untuk Argus-agent, penulis issue yang mengedit repo, approve
otomatis, notifikasi push (ntfy sudah ada), percakapan di viewer/ledger, pengguna kedua.

## Amandemen 1 (2026-11-10): chat yang terasa cepat

Status: **usul Claude, menunggu Atha** (Atha 2026-11-10: "Tiap chat argus selalu lama ya bro, ga bisa cepat kayak kita
chat" → "Ok catat semua ke pending bro. Boleh mulai kerjain"; mockup https://claude.ai/artifact/EDTz2G7Pqipt5GVcJwdtGC
"Nah ini ok").

**Masalah dan ukuran.** Giliran pertama dari HP (j20261109_162802_3ff8, "Apa yang fitur yang perlu ditambahkan ke argus
viewer?") makan 24 detik untuk 7 panggilan model (1-9 detik masing-masing, input tumbuh 1,5k → 28k token) sebelum gagal,
karena (1) penulis selalu membaca repo dan wajib menulis issue, juga untuk pertanyaan umum; (2) tiap giliran mulai dari
nol; (3) halaman diam sampai giliran selesai. Menyalakan CLI ±1 detik (bukan penyebab). Ukuran: detik dari kirim sampai
balasan tampil, per giliran (dari `events.jsonl`: `run_start` → `run_end`), dipisah giliran tanpa issue dan dengan
issue; target giliran tanpa issue ≤ 10 detik. Bukan ukuran: jumlah fitur.

**A1. Giliran tanpa issue.** `SubmitIssue.issue` boleh kosong/tidak ada (versi alat `SubmitIssue` "2"): balasan saja,
untuk pertanyaan umum, saran, atau pertanyaan balik. Gerbang: `reply` tetap wajib; tanpa issue, `clashes` harus kosong;
dengan issue, semua aturan bagian 4 tetap. Prompt: jawab pertanyaan umum tanpa membaca repo bila tidak perlu, atau baca
sesedikit mungkin; tulis issue hanya bila Atha meminta perubahan. Giliran tanpa issue tidak mengubah `issue.txt`,
`issue_sha256`, atau issue di halaman; pesan penulis dicatat tanpa `issue_sha256`. Job tetap `AWAITING_HUMAN`; **Start
job** hanya tampil bila sudah ada issue (sudah: `start` menolak tanpa issue, halaman memerlukan sha).

**A2. Progres saat giliran berjalan.** Penulis mencatat event `writer_step` per alat (`tool`, `target` = path atau pola
pencarian, ≤ 120 karakter, dari argumen model: tidak tepercaya, di-escape di halaman). Halaman job selama `WRITING`
menampilkan langkah-langkah giliran berjalan (maks 12 terakhir) dan detik berjalan, dibaca dari `events.jsonl` run itu
(maks 64 KiB terakhir, baris rusak dilewati); tetap tanpa JavaScript, muat ulang tiap 3 detik.

**A3. Tampilan chat (mockup).** Halaman `/issues/<id>` mengikuti mockup: pesan Atha sebagai gelembung kanan, balasan
penulis teks kiri, issue dalam kartu dengan Start job di dalamnya, kotak balasan di bawah, info biaya kecil. Hanya HTML
dan CSS (`/style.css` service); `<details>` untuk issue lengkap; semua teks tetap di-escape. Gerbang F3, token, audit
tidak berubah.

**Tes wajib (mutants).** Gerbang: tanpa issue diterima dengan reply, ditolak bila ada `clashes` atau reply kosong;
dengan issue aturan lama tetap. Job: giliran tanpa issue tidak mengubah `issue.txt`/`issue_sha256` dan tidak membuat
Start mungkin bila belum ada issue. Halaman: langkah dan target tampil saat `WRITING`, `<script>`/`<img onerror>` di
target tampil sebagai teks, events rusak/hilang tidak membuat halaman gagal; Start tidak tampil sebelum ada issue.

**Tidak di amandemen ini (dicatat di PENDING):** jawaban huruf demi huruf (streaming, jalur uang `harness/llm.py`);
membawa hasil baca giliran sebelumnya ke giliran berikutnya; menggabung 8710 dan 8711.

## Amandemen 2 (2026-11-10): catatan repo antar giliran

Status: **Atha 2026-11-10 "Ok gass"** (usul Claude: kecepatan dulu, gerbang "keep passing unchanged" sesudahnya).

**Masalah dan ukuran.** Pilot p3 (#406): giliran w3 (60 detik, 10 panggilan) membaca ulang `App.jsx` dan file tes kartu
yang sudah dibaca w2; tiap giliran mulai dari nol. Ukuran: panggilan model dan detik per giliran kedua dan seterusnya,
dibanding w3 p3 (10 panggilan, 60 detik). Giliran pertama tidak berubah.

**N1.** `SubmitIssue.notes` (opsional, ≤ 1500 karakter, aturan karakter bagian 6, multi-baris boleh; versi alat "3"):
catatan penulis tentang repo untuk gilirannya nanti (file penting, isinya, tes yang menyentuhnya, kelas dan teks persis).
Disimpan di `job.json` `repo_notes` pada simpan akhir giliran yang sama (crash-resume: tidak ada simpan baru); submit tanpa
catatan mempertahankan yang lama, catatan baru menggantinya. Giliran berikutnya menerima catatan itu di prompt sebagai
data tentang commit beku yang sama, dengan aturan: pakai catatan, baca file lagi hanya untuk detail yang tidak ada.

**N2.** Catatan tidak tampil di halaman dan tidak masuk snapshot publik (allowlist `stage_data` tidak memuatnya). Catatan
berasal dari model yang membaca repo tidak tepercaya: hanya masuk prompt penulis issue yang sama, tidak ke drafter atau
job code.

**Tes wajib (mutants).** Gerbang: catatan kosong/tidak ada → None, panjang, karakter; job: catatan giliran N ada di prompt
giliran N+1, submit tanpa catatan mempertahankan, catatan baru mengganti; tidak ada di snapshot publik.

## Amandemen 3 (2026-11-10): issue yang bentrok mengatakannya sendiri

Status: **Atha 2026-11-10 "Ok next bro"** (antrean dari p3/p4).

**Masalah.** p3 w3 dan p4 w2: penulis mencatat `clashes` (7 dan 5 tes lama) dan menjelaskannya di balasan, tapi teks issue
tetap menulis "The existing tests keep passing unchanged". Drafter dan agen membaca issue, bukan balasan; human yang
menekan Start tanpa membaca balasan memulai job yang pasti merusak tes lama.

**C1.** Gerbang SubmitIssue (versi alat "4"): issue dengan satu `clashes` atau lebih ditolak bila paragraf "Nothing else
changes" memuat klaim tes lama tidak berubah ("keep(s) passing unchanged", "continue(s) to pass unchanged", "still pass as
before", "... without (any) change(s)", tanpa membedakan huruf besar dan spasi/baris). **C2.** Harness sendiri (bukan
model) menulis daftar clash ke issue yang disimpan, sebagai paragraf sebelum baris Environment: kalimat tetap "A human
loosens these existing tests first (the issue writer's clash check, added by the harness):" lalu satu baris `- file line
N: why` per clash; issue beserta daftar itu harus muat batas job code (`MAX_ISSUE`). Issue tanpa clash disimpan apa
adanya. (Code review: mengawasi kalimat model dengan regex rapuh; daftar dari harness deterministik.)

**Tes wajib (mutants).** Klaim ditolak dengan clash (enam ejaan); klaim di luar paragraf itu tidak ditolak; daftar ditulis
harness tepat sebelum baris Environment; batas panjang dengan daftar; tanpa clash disimpan apa adanya; prompt, versi alat.

## Amandemen 4 (2026-11-11): harness mencari tes lama yang disentuh

Status: **Atha 2026-11-11 "Ok 1"** (pilihan 1 dari `pilots/issue_writer_models_v0/RESULT.md`: Haiku sebagai penulis,
dengan pencarian bentrok yang dipaksa harness).

**Masalah dan ukuran.** Replay p4 (#416): Haiku 5.5 satu-satunya yang menandai data API yang belum pasti dan paling cepat
(20,6 dtk), tapi hanya membaca 8 langkah dan menemukan 2 dari 6 clash (terlewat daftar judul kolom
`job-page-share.test.jsx` 132/157/224 dan baris sum). Pencarian bentrok bergantung pada ketelitian model. Ukuran: clash
yang ditemukan pada replay p4 w2 (target 6), detik giliran issue, n = 3 per model.

**T1.** `SubmitIssue` (versi alat "5") mendapat `touches`: daftar 1-8 teks yang **sudah ada di kode** dan diubah atau
diandalkan perubahan (judul kolom, kelas CSS, selector, kunci API, nama fungsi), persis seperti di kode, masing-masing
2-80 karakter satu baris (aturan karakter bagian 6, dipotong spasi tepinya). Wajib untuk issue; untuk balasan saja
diabaikan. Teks yang tidak ada di file mana pun di snapshot ditolak ("sebut teks yang ada, persis").

**T2.** Harness sendiri membaca semua file tes di snapshot (path dengan folder `test`, `tests`, `__tests__`, `spec`,
`specs` atau `e2e`, huruf besar/kecil sama, atau nama `test_*`, `*_test.*`, `*_spec.*`, `*.test.*`, `*.spec.*`, `*Test.*`,
`*Tests.*`, `conftest.py`) lewat path jail yang sama dengan alat baca (tanpa symlink,
tanpa file khusus, `.git` dilewati, batas file/byte SearchFiles) dan mengumpulkan setiap baris yang memuat salah satu
`touches`, urut file lalu baris.

**T3.** Bila ada baris itu, issue diterima hanya bila `clash_check` sama dengan kode harness: 12 hex pertama sha256 dari
daftar baris (`file:baris:teks`). Tanpa kode yang cocok, submit ditolak dengan daftar baris (paling banyak 40, 8 per file,
sisanya dihitung) dan kodenya: model membaca baris yang bisa rusak, menaruhnya di `clashes` (atau mengubah issue), lalu
submit lagi dengan kode itu. Kode hanya didapat dari penolakan itu, jadi issue yang diterima pasti sudah melihat daftarnya;
`touches` lain → daftar lain → kode lain. Tanpa baris tes yang cocok, `clash_check` tidak diperlukan, kecuali pencarian
tidak lengkap (file terlalu besar, batas file/byte, file tak terbaca): maka kode tetap diminta dan penolakannya menyebut
bahwa sebagian file tidak dicari, dan touch yang tidak ketemu tidak ditolak sebagai "tidak ada" (mungkin ada di file yang
tidak terbaca). Gerbang deterministik
atas argumen dan snapshot beku (aman dijalankan ulang). `max_submits` giliran 3 → 4 (satu penolakan kini diharapkan).

**Batas yang disadari (code review).** Gerbang membuktikan daftar baris *ditunjukkan*, bukan bahwa tiap baris
ditindaklanjuti: baris yang memuat touch belum tentu rusak, jadi menilai mana yang clash tetap tugas model (dan human
membaca issue sebelum Start). `touches` hanya sejujur model: touch yang hanya ada di kode non-tes tidak memunculkan daftar.
Ukurannya replay n = 3, bukan gerbang ini sendiri.

**T4.** Hasil giliran menyimpan `touches` dan jumlah baris tes (`test_hits`) di `result.json`; issue, balasan dan clash
tidak berubah bentuk. Gate amandemen 3 tetap.

**Tes wajib (mutants).** touches wajib untuk issue, diabaikan untuk balasan saja, batas jumlah/panjang/karakter, teks yang
tidak ada ditolak; hanya file tes yang dicari (file non-tes tidak masuk daftar), `.git` dan symlink dilewati; kode salah
atau kosong ditolak dengan daftar dan kode, kode benar diterima; daftar dipotong 40/8; tanpa baris tes tidak perlu kode;
prompt, versi alat, config max_submits.

## Amandemen 5 (2026-11-11): touches terlalu umum, Haiku sebagai penulis, key penulis sendiri

Status: **Atha 2026-11-11 "Ok dua-duanya"** (usul `pilots/issue_writer_models_v1/RESULT.md`, #418).

**Masalah.** Replay n = 3 (#418): touches umum (`share`, `stages`) memberi 176-698 baris tes di 44 file; daftar 40 baris
yang ditunjukkan hampir tidak berguna, dan model yang mempersempit touches ke teks persis (a403: daftar judul kolom)
justru menemukan clash yang terlewat. Haiku menandai data API yang belum pasti 3/3 (DeepSeek 1017 0/3), 5× lebih cepat
dan 3× lebih murah; clash yang terlewat masih tertangkap sebelum Start (Claude membaca issue) dan oleh tes lama di job
code, data API yang salah tidak.

**B1.** Bila baris tes yang memuat touches lebih dari 40 (`HITS_SHOWN`), submit ditolak tanpa kode `clash_check`:
"touches terlalu umum" dengan jumlah baris dan file per touch, dan permintaan mengganti touch umum dengan teks persis yang
dicek tes (daftar judul kolom, selector, kelas, kalimat) atau membuangnya. Daftar ≤ 40 baris tetap seperti amandemen 4
(8 per file).

**B2.** Role `issue_writer` = `openrouter:anthropic/claude-haiku-5.5` (K4 sebelumnya DeepSeek V4.1 Flash), tanpa
param thinking DeepSeek; `issue_writer.turn.max_input_tokens` 150000 → 40000 (batas gateway Haiku #415, dicek
`settings()`).

**B3.** Service kontrol: giliran penulis (new, reply) memakai `ARGUS_CONTROL_WRITER_KEY_FILE` bila diisi, selain itu
`ARGUS_CONTROL_KEY_FILE`; Start (job code) tetap `ARGUS_CONTROL_KEY_FILE`. Aturan key file (satu provider per file,
tidak ada key lebih) tidak berubah. Atha menulis variabel itu di drop-in unit; Claude tidak membacanya.

**Tes wajib (mutants).** > 40 baris ditolak tanpa kode dengan jumlah per touch; tepat 40 tetap ditunjukkan dengan kode;
model, tanpa params, batas 40000; key penulis untuk new/reply, key lama untuk start, kosong → key lama, hanya key
penulis → Start tidak ditawarkan dan ditolak.
