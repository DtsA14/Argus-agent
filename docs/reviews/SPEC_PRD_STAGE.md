# SPEC tahap PRD (bagian B antrean PRD): memeriksa PRD dan daftar issue terhadap jalur data Argus, lalu satu persetujuan yang membuat antrean

Status: **rev 0, 2026-11-15, menunggu tinjauan Fable lalu keputusan D4 Atha.** Bagian B dari `docs/reviews/SPEC_PRD_QUEUE.md` (bagian A ter-merge #555, pilot v0 `pilots/queue_pilot_v0/`). Bahan: `pilots/prd_probe_v0/` (RESULT, GLUE_LOG: dua ketergantungan
tersembunyi di sisi Argus), `pilots/staging_stage19/steps.md` (yang ketiga: `/api/scoreboard/models` 404 lewat proxy), `router/stage_viewer.py:76` dan `:530`, `router/stage_data.py:93-98`, `router/queue.py`. Atha 2026-11-15: "Kenapa bagian B harus tunggu titik cek": bagian B ada di urutan inti yang diterima, jadi tidak menunggu.

## 1. Apa yang dibuktikan probe dan Stage 19, dan apa yang bukan

Tiga kali, ketergantungan yang menggigit ada di **jalur data yang melewati Argus**, bukan di kode aplikasi, dan tidak terlihat oleh siapa pun yang hanya membaca aplikasi: snapshot tanpa nama repo dan `as_is`; proxy yang hanya meneruskan jalur tetap; dan
(Stage 19) `/api/scoreboard/models` 404 lewat proxy karena regex `API` berjangkar penuh dan dicocokkan dengan jalur **beserta query** (`stage_viewer.py:530`: `/api/scoreboard?kind=x` pun 404). Yang belum dibuktikan: bahwa **model** yang menulis PRD
lebih baik dari Claude atau Atha yang menulisnya. Maka spek ini membagi bagian B:

- **B1 (dibangun sekarang): pemeriksa dan persetujuan, tanpa model.** `argus prd check` dan `argus prd approve`.
- **B2 (tidak dibangun; keputusan D4): penulis PRD di chat** (mesin penulis issue, `router/issue.py`, mode PRD, biaya model). Usul: tunda sampai log "permintaan yang chat belum bisa" atau pilot kedua menunjukkan bahwa PRD ditulis tangan adalah hambatannya.

## 2. Masukan: satu folder

`<dir>/PRD.md` (untuk manusia; tidak diurai kecuali sha-nya), `<dir>/issues.json`, dan satu berkas per issue (`issue-1.md`, ...).
```json
{"repo": "argus-ledger", "commit": "<40 heksa = HEAD repo sekarang>", "max_usd": 3.0,
 "items": [{"n": 1, "file": "issue-1.md",
            "paths": [{"side": "viewer-api", "path": "/api/scoreboard/models"}],
            "fields": ["JOB_FIELDS.max_usd"]}]}
```
`side`: `viewer-api` (jalur yang **viewer** panggil lewat proxy 8710, harus cocok dengan `stage_viewer.API`) atau `ledger` (jalur yang dibangun di ledger sendiri; tidak diperiksa terhadap proxy). `fields`: `<TABEL>.<nama>` dari `JOB_FIELDS`, `STAGE_FIELDS`, `LOG_FIELDS` yang item itu perlukan di snapshot.

## 3. `argus prd check <dir>` (baca saja, tanpa model, tanpa uang)

Temuan bertingkat **BLOKIR** atau **PERINGATAN**; keluar 0 hanya tanpa BLOKIR. Pemeriksaan mengimpor **kode yang berjalan** (`router.stage_viewer.API`, `router.stage_data.JOB_FIELDS` dan kawan-kawannya), tidak menyalin daftar.

BLOKIR:
1. Struktur: `issues.json` bukan JSON objek yang dikenal, `repo` bukan nama di `issue_writer.repos` atau checkout Argus (lewat `queue.new`'s aturan yang sama), `commit` bukan HEAD sekarang, `n` bukan 1..N berurutan, 1 sampai `QUEUE_MAX_ITEMS` item, berkas issue hilang, atau teks issue gagal `message_problem`.
2. Jalur `viewer-api`: `API.match(path)` (jalur penuh dengan query, seperti `stage_viewer.py:530`) kosong: "proxy tidak meneruskan `<path>` (`stage_viewer.py:76`): perubahan Argus jalur ketat dan restart proxy dulu, di luar antrean".
3. Field `<TABEL>.<nama>` yang tidak ada di tabel itu: "snapshot tidak menerbitkan field itu: perubahan Argus jalur ketat dulu".
4. **Jalur yang tidak dideklarasikan:** setiap kemunculan `/api/...` di teks issue (pola `/api/[A-Za-z0-9_./?=&-]*`) yang tidak cocok `API` dan tidak tercantum di `paths` item itu. (Menutup risiko bagian 9 SPEC_PRD_QUEUE: PRD yang lupa menulis `paths`.) Kemunculan yang cocok `API` hanya PERINGATAN bila tidak dideklarasikan.

PERINGATAN: `PRD.md` kosong atau tanpa kata "kontrak"; dua issue yang menyebut jalur yang sama dengan bentuk berbeda tidak diperiksa (tidak ada pemeriksaan semantik; dikatakan di keluaran).

Keluaran mencetak **sha PRD** (sha256 dari `PRD.md`, `issues.json` dan isi berkas issue berurutan, dengan nama), supaya manusia menyetujui yang ia lihat.

## 4. `argus prd approve <dir> --sha <12+ heksa dari check>`

Menjalankan `check` lagi (BLOKIR menolak), memeriksa sha, lalu memanggil `rq.new(...)` dengan teks issue dari folder dan mencatat `prd: {sha, dir}` di `queue.json` (ikut `list_sha`, jadi mengubah PRD sesudah itu menolak `step`).
Hasilnya antrean `PENDING`; **uang tetap `queue go`** (D2). Persetujuan PRD = persetujuan isi dan urutan, bukan uang dan bukan draf (D3 tetap: tiap draf dan patch oleh manusia).

## 5. Keputusan D4 untuk Atha
Siapa menulis PRD pada B1: **Claude atau Atha menulis folder itu (seperti probe)**; B2 (model di chat) ditunda. Alternatif: bangun B2 sekarang (biaya model, mode baru di penulis issue, jalur ketat); tidak diusulkan karena tidak ada bukti bahwa penulisan adalah hambatannya.

## 6. Tes (sebelum kode)
`tests/test_prd_stage.py`, tanpa model: folder sehat lolos; **kasus Stage 19** (`/api/scoreboard/models`, `viewer-api`) BLOKIR dengan `stage_viewer.py:76` di pesan; `/api/scoreboard?kind=code` BLOKIR (query); `/api/jobs/<id>/draft` lolos; field yang tidak ada BLOKIR; jalur di teks issue yang tidak dideklarasikan BLOKIR; cocok `API` tapi tidak dideklarasikan PERINGATAN; `API` diganti (monkeypatch) mengubah hasil (bukti memakai kode yang berjalan); `commit` bukan HEAD; repo Argus; `n` melompat; berkas issue hilang; `approve` dengan sha salah, setelah folder diubah, dan dengan BLOKIR menolak dan tidak membuat antrean; `approve` yang sah membuat antrean `PENDING` dengan `prd.sha`; antrean dengan PRD yang berkas issuenya diubah menolak `step`; `check` tidak menulis apa pun. Mutan di `verification/prd_stage_mutants.py`.

## 7. Urutan kerja dan batas
Alur jalur ketat (spek, tinjauan Fable, tes, kode, tinjauan Fable atas diff, mutan, `precheck`, satu `verify_at`, merge atas kata Atha). Tanpa uang model sama sekali. Batas: pemeriksaan hanya menangkap jalur dan field yang **ditulis** atau terlihat sebagai `/api/...` di teks issue; jalur yang disusun dari potongan teks lolos. Ia memeriksa Argus, tidak menilai apakah PRD-nya bagus.
