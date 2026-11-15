# SPEC tahap PRD (bagian B antrean PRD): memeriksa PRD dan daftar issue terhadap jalur data Argus, lalu satu persetujuan yang membuat antrean

Status: **rev 1, 2026-11-15; tinjauan Fable atas spek dan diff GO WITH FIXES (semua temuan diterapkan); D4 (Atha 2026-11-15): B2 ditunda sampai pilot kedua (di repo luar: athena); B1 dibangun, `verify_at` PASS 5305, mutan 31/31 non-ekuivalen.** Bagian B dari `docs/reviews/SPEC_PRD_QUEUE.md` (bagian A ter-merge #555, pilot v0 `pilots/queue_pilot_v0/`). Bahan: `pilots/prd_probe_v0/` (RESULT, GLUE_LOG: dua ketergantungan
tersembunyi di sisi Argus), `pilots/staging_stage19/steps.md` (yang ketiga: `/api/scoreboard/models` 404 lewat proxy), `router/stage_viewer.py:76` dan `:530`, `router/stage_data.py:93-98`, `router/queue.py`. Atha 2026-11-15: "Kenapa bagian B harus tunggu titik cek": bagian B ada di urutan inti yang diterima, jadi tidak menunggu.

## 1. Apa yang dibuktikan probe dan Stage 19, dan apa yang bukan

Tiga kali, ketergantungan yang menggigit ada di **jalur data yang melewati Argus**, bukan di kode aplikasi, dan tidak terlihat oleh siapa pun yang hanya membaca aplikasi: snapshot tanpa nama repo dan `as_is`; proxy yang hanya meneruskan jalur tetap; dan
(Stage 19) `/api/scoreboard/models` 404 lewat proxy karena regex `API` berjangkar penuh dan dicocokkan dengan jalur **beserta query** (`stage_viewer.py:530`: `/api/scoreboard?kind=x` pun 404). Yang belum dibuktikan: bahwa **model** yang menulis PRD
lebih baik dari Claude atau Atha yang menulisnya. Maka spek ini membagi bagian B:

- **B1 (dibangun sekarang): pemeriksa dan persetujuan, tanpa model.** `argus prd check` dan `argus prd approve`.
- **B2 (tidak dibangun; keputusan D4): penulis PRD di chat** (mesin penulis issue, `router/issue.py`, mode PRD, biaya model). Usul: tunda sampai log "permintaan yang chat belum bisa" atau pilot kedua menunjukkan bahwa PRD ditulis tangan adalah hambatannya.

## 2. Masukan: satu folder

`<dir>/PRD.md` (untuk manusia; hanya di-hash), `<dir>/issues.json`, dan `<dir>/issue-1.md` ... `issue-N.md` (nama tetap; tidak ada kunci `file`: temuan Fable 6).
```json
{"repo": "argus-ledger", "commit": "<40 heksa = HEAD repo sekarang>", "max_usd": 3.0,
 "items": [{"n": 1,
            "paths": [{"side": "ledger", "path": "/scoreboard/models", "via_proxy": true}],
            "fields": ["JOB_FIELDS.max_usd", "EVENT_FIELDS.llm_call.usd_nano"]}]}
```
- `side: "viewer-api"`: jalur yang **viewer** panggil, ditulis `/api/...` seperti di proxy. `side: "ledger"`: jalur yang dibangun atau dipakai di ledger sendiri, ditulis **tanpa** `/api` (jalur yang diawali `/api/` pada sisi `ledger` ditolak: itu pintu belakang yang membungkam aturan 4).
  `via_proxy` **wajib** pada sisi `ledger` (true atau false): penulis harus memutuskan apakah viewer akan memanggilnya lewat proxy 8710; yang true diperiksa seperti `viewer-api` dengan jalur `"/api" + path`.
- `fields`: `<TABEL>.<nama>`; TABEL = `JOB_FIELDS`, `STAGE_FIELDS`, `LOG_FIELDS`, atau `EVENT_FIELDS.<event>` (bersarang per jenis kejadian, `router/stage_data.py:99-108`). Nama yang diterbitkan snapshot di luar tabel-tabel itu (misalnya `title`, `stages`, `log`, `router/stage_data.py:157-159,447`)
  dikenali lewat daftar kecualian eksplisit di `router/prd.py` yang dibaca PR dari kode itu, dengan tes yang gagal bila `stage_data` berubah; selain itu BLOKIR. Batas: ini daftar nama, bukan pemeriksaan bahwa nilainya cocok dengan yang issue harapkan.
- Kunci tak dikenal di mana pun BLOKIR.

## 3. `argus prd check <dir>` (baca saja, tanpa model, tanpa uang)

**Satu pembacaan:** folder dibaca sekali ke memori (`O_NOFOLLOW`, hanya berkas biasa, `PRD.md` dan `issues.json` paling besar 200 KB, tiap issue paling besar `message_max`, UTF-8 atau BLOKIR); temuan, sha dan `approve` semuanya memakai byte itu (temuan Fable 4, 6). Symlink, `..` atau jalur mutlak tidak mungkin (nama tetap).
Temuan **BLOKIR** atau **PERINGATAN**; keluar 0 hanya tanpa BLOKIR. Pemeriksaan mengimpor **kode yang berjalan** (`router.stage_viewer.API`, tabel `router.stage_data`), bukan salinan.

BLOKIR:
1. **Validasi yang sama dengan `queue new`:** satu fungsi `rq.validate_new(...)` diambil dari `new()` (repo di `issue_writer.repos` dan bukan checkout Argus, `commit` = HEAD sekarang, `0 < max_usd <= QUEUE_MAX_USD` dan `>= code_max_usd`, 1..`QUEUE_MAX_ITEMS` item, teks tidak kosong dan lolos `message_problem`, strip, tidak ada antrean belum-selesai pada repo itu) dipakai `check` dan `new`, supaya `check` tidak lolos sementara `approve` menolak (temuan 7). `n` berurutan 1..N.
2. **Jalur proxy:** untuk tiap `viewer-api` dan tiap `ledger` dengan `via_proxy: true`, `m = API.match(jalur penuh dengan query)` harus ada **dan** `m.end() == len(jalur)` (regex berakhir `$` yang meloloskan `\n` di ujung: temuan 2); jalur dengan spasi atau karakter kontrol BLOKIR. Pesan: "proxy tidak meneruskan `<path>` (`stage_viewer.py:76`): perubahan Argus jalur ketat dan restart proxy dulu, di luar antrean". Catatan bagi penulis: proxy tidak pernah meneruskan query (`_api` memakai `"/" + group(1)`), jadi `?kind=` lewat proxy butuh lebih dari regex.
3. **Field:** `<TABEL>.<nama>` yang tidak diterbitkan: "snapshot tidak menerbitkan field itu: perubahan Argus jalur ketat dulu".
4. **Jalur tak dideklarasikan di teks issue**, dua pola, dengan batas kiri `(?<![A-Za-z0-9_.-])`, ekor `.,;:)?]'"` dibuang, dan sebuah kemunculan yang diikuti `<`, `{`, `:` atau `$` (templat, `/api/jobs/<id>/draft`, `${id}`) dibaca sebagai awalan templat dan dicocokkan sebagai `/api/jobs/<id-sah>/draft`-nya bila deklarasi ada, selain itu PERINGATAN:
   a. `/api/...` (pola `/api/[A-Za-z0-9_./?=&-]*`); b. **`GET|HEAD|POST /jalur`** (pola `\b(GET|HEAD|POST)\s+(/[A-Za-z0-9_./?=&-]*)`), yaitu cara issue ledger menyebut endpointnya (kasus asli Stage 19: "Add `GET /scoreboard/models`").
   Setiap kemunculan harus **ada di `paths` item itu** (sama persis setelah normalisasi); yang tidak: BLOKIR "deklarasikan jalur ini dengan `via_proxy` true atau false". Jadi penulis dipaksa memutuskan, dan keputusan itu diperiksa (aturan 2).

PERINGATAN: `PRD.md` kosong atau tanpa kata "kontrak"; kemunculan templat tak terpasangkan; teks yang menulis jalur lewat potongan, `/API/...` atau `%2F` tidak terbaca (dikatakan di keluaran).

**sha PRD** = sha256 dari JSON kanonik `[["PRD.md", sha256(byte)], ["issues.json", sha256(byte)], ["issue-1.md", sha256(byte)], ...]` (temuan 5), dicetak oleh `check`.

## 4. `argus prd approve <dir> --sha <12+ heksa>`
Membaca folder sekali, menjalankan pemeriksaan yang sama pada byte itu (BLOKIR menolak), mencocokkan sha (`rj.SHA_SEEN`: 12 diterima, 11 ditolak), lalu memanggil `rq.new(..., prd={"sha": <64 heksa>, "dir": <jalur>})` dengan teks dari memori. **Perubahan di `router/queue.py`:** `new(..., prd=None)` menulis `prd` pada `_save` yang sama dengan antreannya (tidak ada antrean PENDING tanpa `prd` karena patch susulan); `_load` memvalidasi `prd` bila ada (dict, `sha` 64 heksa, `dir` string) supaya berkas rusak menjadi `Refused`;
`list_sha` menambahkan kunci `prd` **hanya bila `q.get("prd")`** (antrean tanpa `prd`, termasuk `q20261115T175659Z-94a1` yang sudah disetujui, menghasilkan sha yang sama persis seperti sebelumnya; ada tesnya). **`prd` adalah provenans**: `step` tidak membaca folder PRD (ia memeriksa salinan issue antrean sendiri, sudah ada). Persetujuan PRD = isi dan urutan; **uang tetap `queue go`** (D2); tiap draf dan patch oleh manusia (D3).
`approve` yang `rq.new`-nya menolak tidak meninggalkan direktori antrean.

## 5. Keputusan D4 untuk Atha
Siapa menulis PRD pada B1: **Claude atau Atha menulis folder itu (seperti probe)**; B2 (penulis PRD pakai model di chat) ditunda sampai log "permintaan yang chat belum bisa" atau pilot kedua menunjukkan bahwa PRD tulis tangan adalah hambatannya. Alternatif: bangun B2 sekarang (biaya model, mode baru, jalur ketat); tidak diusulkan.

## 6. Tes (sebelum kode)
`tests/test_prd_stage.py` (tanpa model) dan tambahan di `tests/test_queue.py`:
- folder sehat lolos; **bentuk asli Stage 19**: issue ledger yang menulis "Add `GET /scoreboard/models`" tanpa deklarasi BLOKIR; dengan `{"side":"ledger","path":"/scoreboard/models","via_proxy":true}` BLOKIR (proxy) dan dengan `via_proxy:false` lolos; `side: ledger` dengan jalur `/api/x` BLOKIR; `via_proxy` hilang BLOKIR;
- `/api/scoreboard?kind=code` BLOKIR; `/api/jobs/<id>/draft` lolos; `/api/summary\n` BLOKIR; spasi atau karakter kontrol BLOKIR; `API` diganti lewat monkeypatch **dan** `JOB_FIELDS` diganti mengubah hasil (kode yang berjalan, bukan salinan);
- teks: `See /api/scoreboard.` tidak BLOKIR palsu (titik diabaikan, jalur cocok); `/api/jobs/<id>/draft`, `{id}`, `:id`, `${id}` sebagai templat; `src/api/client.js` bukan jalur; `/api/jobs/j1?`; backtick, kurung, JSON, koma; kemunculan tak dideklarasikan BLOKIR dan yang cocok `API` tak dideklarasikan tetap BLOKIR (aturan 4b memaksa deklarasi);
- field: tidak ada BLOKIR, `EVENT_FIELDS.llm_call.usd_nano` lolos, kecualian `title` lolos, `repo` dan `as_is` (ketergantungan pertama probe) BLOKIR;
- masukan: `commit` bukan HEAD, repo Argus, `n` melompat, kunci tak dikenal, symlink dan `..` dan nama lain di folder, berkas besar, non-UTF-8, `max_usd` di bawah cap atau di atas $5, antrean belum selesai pada repo yang sama BLOKIR, semuanya **sama** di `check` dan `approve` (satu validator);
- `approve`: sha salah, 11 heksa, folder diubah sesudah `check` (byte yang dipakai satu pembacaan), BLOKIR, `rq.new` menolak: tidak ada antrean dan tidak ada direktori; sah: antrean `PENDING` dengan `prd.sha`; sha berbeda bila byte berpindah antar dua berkas issue; `check` tidak menulis apa pun;
- `tests/test_queue.py`: `prd` rusak (`_load` Refused), `prd.sha` diubah menolak `step` (ikut `list_sha`), `prd` dihapus menolak `step`, antrean lama tanpa `prd` punya sha yang sama dengan sebelumnya (tetapkan nilai tetap).
Mutan di `verification/prd_stage_mutants.py`.

## 7. Urutan kerja dan batas
Alur jalur ketat (spek, tinjauan Fable, tes, kode, tinjauan Fable atas diff, mutan, `precheck`, satu `verify_at`, merge atas kata Atha). Tanpa uang model. Batas: pemeriksaan hanya menangkap jalur dan field yang **ditulis** atau yang terlihat sebagai `/api/...` atau `GET /jalur` di teks issue; jalur yang disusun dari potongan, ditulis `/API/`, atau dikodekan `%2F` lolos.
Ia memeriksa sisi Argus, tidak menilai apakah PRD-nya bagus, dan tidak menjamin bahwa nilai field cocok dengan yang issue harapkan.
