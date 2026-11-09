# Spek: chatbox penulis issue (UI kontrol fase 3c)

Status: **usulan Claude, menunggu keputusan Atha (bagian 9) dan "merge"**. Atha 2026-11-09: "Kalo gw pengen nulis issue di
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
| K1 | Bahasa | Chat bahasa Indonesia; issue bahasa Inggris (seperti sekarang; drafter dan tes memakai Inggris) |
| K2 | Repo yang boleh | `argus-viewer` (pwa_node22) dan `argus-ledger` (ledger_py312_up2); Argus-agent sendiri **tidak** (jalur ketat ditulis Claude) |
| K3 | Batas biaya | $0,10 per giliran, $0,50 per job issue; job code dari chatbox ≤ $1,00 (seperti sekarang) |
| K4 | Model penulis | `deepseek-v4-pro` (issue menentukan kualitas seluruh job; flash cukup untuk drafter, tapi kesalahan issue mahal). Diukur: bila pro tidak lebih baik dari flash pada 5 issue pertama, turun ke flash |
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
