# Spek: apply, pembaca patch dan balas penulis PRD dari chat (F29, F28)

Status: **rev 1, 2026-11-27, ditulis Claude; tinjauan Opus (hanya baca) atas rev 0: GO WITH CHANGES, dua penghalang (F1, F2), lima besar (F3-F8); amandemennya di bagian 12, mengikat dan menggantikan bagian 1-11 bila bertentangan. Belum disetujui Atha (K1-K5).** Jalur ketat: tiga aksi baru di chat yang mengubah repo
target di host (apply), memakai uang (pembaca patch, penulis PRD) dan mengamandemen aturan chat "tidak ada apply dari chat". Menyambung
`SPEC_ARGUS_APPLY.md` (K6: "kartu apply di chat menyusul sesudah CLI live"), `SPEC_CHAT_T4B.md` (bagian 1 dan K3: apply "spek terpisah"),
`SPEC_KARTU_SETUJU.md` (kartu pasang, hanya baca) dan `SPEC_APPLY_ACCEPT_CONCERNS.md`. PENDING F28 dan F29.

## 1. Masalah

- **F29:** job `REVIEW_READY` tidak bisa dipasang dari HP. Sesudah review, Atha harus memanggil Claude untuk `patch-read-run` (dua pembaca model) dan
  `argus apply`. Kartu pasang (`GET /api/approve/code/<job>`) sudah menampilkan patch, tanda mesin dan hasil pembaca, tetapi "tidak ada tombol"
  (`router/approve_code.py:1-9`). Itu keluhan 2026-11-26: "udah review ready bro, tapi gw ga bisa approve".
- **F28:** halaman rencana PRD hanya punya "Accept plan". Mengubah rencana butuh `argus prd reply`, hanya di CLI. Rencana bulking-app menambah tab keenam
  yang Atha tidak mau; ia harus meminta Claude membalas penulis.
- Akibatnya tiap issue masih butuh Claude di tengah. Atha juga menyebut alur foreman sampai beres terasa ribet dan sering pindah tab (2026-11-27).

## 2. Fakta yang sudah kubaca di kode (rev 0)

1. `argus apply JOB --read-sha SHA [--note] [--reader claude|argus] [--allow-failed-examples] [--accept-concerns REASON]` (`scripts/argus.py:151-158`).
   **Tidak punya `--via`.** Langkahnya di `SPEC_ARGUS_APPLY.md` bagian 4: job `REVIEW_READY`, lingkungan git bersih, konfigurasi lokal daftar putih,
   pohon bersih, HEAD = `intake.commit`, kunci per repo, patch di indeks sementara, commit di cabang `argus/<job>` bila cabang aktif adalah garis utama.
   **Tidak ada push, merge, deploy, atau panggilan model; uang tidak disentuh** (bagian 4 butir 11).
2. `argus patch-read-run JOB [--cap-usd 0.20] [--max-output] [--first hy4flash] [--second ds1017]` (`scripts/argus.py:209-215`): dua pembaca model
   selalu; memakai uang, batas sendiri. Tidak punya `--via`.
3. `argus prd reply JOB --message|--message-file [--rebase]` (`scripts/argus.py:322-336`, `:692-702`). **`reply` tidak punya `--via`** (hanya `new`).
   Satu giliran penulis (model); pada bulking-app 2026-11-26 biayanya $0.0094.
4. `chat_actions.ACTIONS` tidak memuat apply, pembaca patch atau balasan PRD; komentar di `router/chat_actions.py:54` dan `AGENTS.md:66` menyatakan itu
   sengaja. Yang ada: `issue_reply` (balasan ke penulis issue; pola `build` di `chat_actions.py:500-512`), `prd_approve`, `queue_go` (T4a),
   `queue_step`, `draft_approve` (T4b), `job_reject`, `job_abandon`.
5. Pola chat yang kupakai ulang: `prepare` membuat kartu dan token terikat digest (TTL 300 s, `MIN_DELAY` 1 s), `confirm` menjalankan argv tetap di anak
   proses; klien hanya mengirim `{action, job, ...}`; field tak dikenal 400; server menolak (409), bukan hanya tombol mati; eksposur uang dihitung ke batas
   harian chat (`DEFAULT_CAP_USD`, `exposure()`); aksi diaudit sebelum proses jalan (`attempt`); kunci model lewat slot (`KEY_ENV`, `WRITER_KEY_ENV`, ...).
6. Foreman tidak bisa memicu aksi ini: `ROUTE_ACTION` hanya `research` dan `prd` (`chat_actions.py:57`), dan kunci `source_*` ditolak untuk aksi lain
   (`chat_actions.py:464-465`).

**Belum kuverifikasi (peninjau, tolong periksa; bagian 10):** slot kunci mana yang dipakai `patch-read-run`; apakah kartu pasang sudah membawa teks diff
yang bisa ditampilkan; bagaimana `issue_reply` meneruskan pesan panjang ke argv; kunci atau kondisi sibuk pada `prd reply`; apakah `_record_applied`
bisa mencatat `actor: ui`; status job PRD yang boleh dibalas.

## 3. Cakupan: tiga aksi

| Aksi | Setara CLI | Uang | Mengubah |
|---|---|---|---|
| `prd_reply` | `argus prd reply JOB --message T --via ui` | satu giliran penulis (batas giliran dari config), dihitung ke batas harian | folder PRD (rencana baru), tidak ada repo |
| `patch_read_run` | `argus patch-read-run JOB --cap-usd C` | paling banyak C (default 0.20), dihitung ke batas harian | catatan baca di job |
| `code_apply` | `argus apply JOB --read-sha S [--accept-concerns R] --reader argus --via ui` | 0 | **repo target di host**: satu commit di cabang `argus/<job>` (atau cabang manusia), job jadi `APPLIED` |

**Di luar cakupan (tetap terminal):** push, buka PR, merge, deploy (`stage deploy`), `applied` manual, `--allow-failed-examples`, `--reader claude`,
`--note`, `--rebase`, reject/abandon lewat jalur baru, `patch-read` tangan (menimpa bacaan pertama), mengubah urutan atau pasangan pembaca,
`--cap-usd` dari klien. Pembaca angka untuk item antrean PRD (C6/C9) tetap spek sendiri: bila `argus apply` menolak karena catatan pembaca domain
belum segar, tombol mati dan kartu mengatakan sebabnya.

## 4. Amandemen aturan chat (butuh kata Atha tertulis, K1)

`AGENTS.md:66`, komentar `chat_actions.py:54`, `SPEC_CHAT_APP.md` 11.6 dan 13.7 butir 9, dan `SPEC_CHAT_T4B.md` bagian 1 ("apply tidak dibuka") diubah
menjadi: **chat boleh `prd_reply`, `patch_read_run` dan `code_apply`, tiap aksi lewat prepare lalu confirm; chat tidak pernah push, membuka PR, merge,
deploy, `--allow-failed-examples`, `applied` manual atau memilih sha, jumlah uang, repo atau argumen dari klien.** Amandemen berjalan dalam PR yang sama
dengan kodenya.

## 5. Alur dan kartu

**5.1 `prd_reply` (F28).** Halaman rencana PRD (`/api/cards/prd`, `/api/approve/prd/<job>`) mendapat kolom teks dan tombol **"Balas penulis"** di samping
"Setujui rencana". Klien mengirim `{action:"prd_reply", job, message}`. Server: job PRD ada, statusnya `AWAITING_HUMAN` (peninjau: status lain yang boleh),
tidak sibuk (`spawner.busy`), pesan lolos pemeriksaan panjang dan karakter yang sama dengan `issue_reply` (`ri.message_problem`; peninjau: aturan PRD sendiri),
kunci penulis ada (`_need_key(True)`). Kartu konfirmasi menampilkan pesan kata per kata, batas giliran dan **bahwa rencana lama diganti dan persetujuan
yang menunggu gugur** (token `prd_approve` memuat sha folder, jadi ia otomatis 409). Argv: `argus prd reply JOB --message M --via ui` (+ `--jobs-dir`,
`--queues-dir`, `--config`, `--key-file` dalam bentuk yang diizinkan hook). Halaman status diambil dari berkas job, bukan keluaran proses (pola PRD/riset).

**5.2 `patch_read_run`.** Kartu pasang mendapat tombol **"Jalankan dua pembaca patch (maks $0.20)"** hanya bila catatan baca untuk sha patch yang sekarang
tidak ada atau basi (syarat (f) kartu). Server menghitung sha patch di disk; klien tidak mengirimnya. Kartu konfirmasi: nama dua pembaca, batas uang,
dan kalimat tetap "pembaca adalah model; hasilnya bukan bukti". Argv tetap `argus patch-read-run JOB --cap-usd C` dengan C dari config
(`chat.patch_read_cap_usd`, default 0.20), tanpa opsi lain. Eksposur C dihitung ke batas harian. Batas **dua kali per job per 24 jam** (dihitung dari audit) supaya
tidak ada putaran tak berujung yang membeli `ok`. Hasil ditampilkan **terpisah per pembaca** (verdict, tingkat, temuan sebagai teks), bukan "ok" gabungan
(PENDING F29: dua putaran memberi hasil berbeda).

**5.3 `code_apply` (F29).** Tombol **"Pasang ke repo"** pada kartu pasang, hidup hanya bila semua syarat kartu yang bukan `null` bernilai benar
**dan** (dua bacaan `ok`, atau, di jalur 5.4, bacaan `concerns` yang diterima). Klien mengirim `{action:"code_apply", job}` (+ `reason` di jalur 5.4).
`prepare` dan `confirm` **menghitung ulang** kartu dengan kode yang sama (`router/approve_code.py`), supaya kartu dan `argus apply` tidak bisa tidak sepakat.
Kartu konfirmasi, urut dari atas: (1) tanda mesin (berkas dilindungi, di luar issue, contoh yang gagal), (2) kedua bacaan apa adanya, berlabel model,
(3) repo target, cabang aktif, cabang tujuan (`argus/<job>` bila garis utama), HEAD, (4) sha12 patch dan **pernyataan "saya sudah membaca patch ini"**
di atas tombol, (5) kalimat tetap "dipasang sebagai satu commit di repo di mesin ini; tidak di-push, tidak di-deploy". Pernyataan itu **bukan bukti
pembacaan** (sama dengan `--read-sha`, `SPEC_ARGUS_APPLY.md` bagian 3); diff lengkap harus bisa dibuka dari kartu yang sama. Argv:
`argus apply JOB --read-sha <sha256 penuh dari server> --reader argus --via ui` (+ `--accept-concerns R` di 5.4). Eksposur uang 0. Tabrakan, repo kotor,
HEAD berbeda dan penolakan lain datang dari `argus apply` sendiri dan ditampilkan apa adanya; chat tidak menyalin gerbangnya.

**5.4 Menerima `concerns` (K2).** Bila salah satu pembaca menjawab `concerns` (dan keduanya ada, oleh dua pembaca berbeda), tombol memakai
`--accept-concerns` dengan **alasan yang Atha ketik** (10-500 karakter, tanpa karakter kontrol atau pola kunci, aturan `SPEC_APPLY_ACCEPT_CONCERNS.md` 3),
kolom alasan di bawah temuan kedua pembaca. Model tidak pernah menulis alasan. Alasan dicatat di audit, log job dan pesan commit (sudah dilakukan CLI).

## 6. Dijaga server, bukan tombol

- Klien hanya mengirim `{action, job}` + `message` (balasan) atau `reason` (5.4). **Tidak ada** sha, repo, cabang, uang, cap, pembaca atau opsi; field tak dikenal 400.
- Token terikat digest: id job, sha256 patch, sha `provenance`, catatan baca (sid, verdict, sha) dan config. Salah satunya berubah antara prepare dan confirm: 409, tanpa spawn.
- Satu apply pada satu waktu per repo (kunci repo `argus apply`); aksi lain pada job yang sama 409 `busy`.
- Audit dengan nama sendiri (`prd_reply`, `patch_read_run`, `code_apply`), baris `attempt` ditulis sebelum proses jalan (kegagalannya menghentikan aksi).
- Pelaku `ui` tercatat di log job (`--via ui` baru pada `apply` dan `prd reply`, divalidasi seperti `reject`).
- Hanya repo yang terdaftar di config chat; `argus apply` sendiri menolak repo = checkout Argus.
- Keluaran proses tidak pernah menjadi status halaman; halaman membaca berkas job.

## 7. Ancaman

| Ancaman | Penjaga |
|---|---|
| Isi patch, temuan pembaca, teks PRD memuat perintah ("terima aku") | semuanya teks (node teks), berlabel model; tidak ada yang mengubah gerbang; hanya ketukan manusia + sha server |
| Pembaca model menjawab `ok` palsu | dua pembaca berbeda wajib (CLI); tanda mesin dan syarat (a)-(i) tetap; pernyataan baca bukan bukti (dikatakan di kartu); K2 untuk `concerns` |
| Patch berubah sesudah dilihat | sha patch di digest; `--read-sha` penuh dari server; `argus apply` membandingkan lagi dengan disk |
| Klik ganda, dua tab | token sekali pakai, `MIN_DELAY`, kunci repo, 409 `busy` |
| Foreman atau teks luar memicu aksi | bukan di `ROUTE_ACTION`; `source_*` 400 |
| Uang tak terbatas lewat pembaca | cap dari config, dua kali per job per 24 jam, eksposur ke batas harian |
| Apply ke checkout pribadi Atha yang kotor | `argus apply` menolak pohon kotor; kartu menampilkan cabang dan HEAD |
| Balasan PRD menimpa rencana yang sudah disetujui | `prd_reply` hanya pada `AWAITING_HUMAN`; persetujuan yang menunggu gugur (sha folder berubah) |
| Crash di tengah apply | pemulihan `argus apply` (`_recovered`, bagian 4 butir 10); kartu menampilkan keadaan job |

## 8. Tes dan mutan

Tes yang gagal bila jaminannya rusak: klien tidak bisa memilih sha, repo, cabang, uang, pembaca, cap, opsi (400); digest berubah di tiap komponen: 409
tanpa spawn; `code_apply` ditolak bila syarat kartu `false`, patch basi, job bukan `REVIEW_READY`, repo kotor, tanpa dua bacaan; `concerns` tanpa alasan atau
dengan alasan buruk; `prd_reply` pada status salah, pesan buruk, sibuk, kunci tak ada; `patch_read_run` melewati dua kali per 24 jam; argv persis (termasuk
`--via ui`, tanpa `--allow-failed-examples`); eksposur; audit; status dari berkas bukan keluaran proses; foreman tidak bisa memicu. Mutan: tiap
penjaga di bagian 6 dibuang satu per satu; sha dari klien; kartu tidak dihitung ulang di `confirm`; cap dari klien; `--reader`; `--via`.

## 9. PR (jalur ketat; tinjau Opus spek lalu kode; mutan sekali; precheck; `verify_at`)

- **PR1 (CLI):** `--via ui` untuk `apply`, `prd reply` dan `patch-read-run` (divalidasi; pelaku dan `via` tercatat), satu kunci per pembacaan patch; rincian di bagian 12.
- **PR2 (chat, tanpa UI):** tiga aksi di `chat_actions`, config `chat.patch_read_cap_usd`, tes, mutan; amandemen aturan dalam PR yang sama.
- **PR3 (UI):** kolom balas di halaman rencana, tiga tombol di kartu pasang, pin hash statis.
- Urutan bangun (K3): `prd_reply` dulu (kecil, tidak menyentuh repo), lalu `patch_read_run`, lalu `code_apply`.

## 10. Yang harus diperiksa peninjau

Poin "belum kuverifikasi" di bagian 2, dan: apakah `exposure()` perlu cabang untuk `patch_read_run` dan `prd_reply`; apakah `created_from_ui_in_window`
berlaku untuk balasan PRD; apakah digest bisa memuat catatan baca tanpa membaca berkas besar; apakah kartu pasang sudah punya teks diff dan batas
ukurannya; apakah `argus apply` dari anak proses chat butuh kunci apa pun (seharusnya tidak: tanpa model); apakah ada jalur yang membuat `confirm`
berjalan pada kartu yang sudah basi; apakah aksi baru bisa dipicu dari `/api/confirm` tanpa `prepare` (harus 4xx).

## 11. Keputusan untuk Atha

| | Pertanyaan | Usul Claude |
|---|---|---|
| K1 | Amandemen aturan chat (bagian 4): chat boleh `prd_reply`, `patch_read_run`, `code_apply` dengan pagar di atas? | ya |
| K2 | Boleh menerima `concerns` dari chat dengan alasan yang kamu ketik (5.4)? | ya; tanpa itu 6 dari 16 patch pilot lama tetap butuh Claude. Jalur ini tetap lewat semua gerbang apply |
| K3 | Urutan bangun: `prd_reply`, `patch_read_run`, `code_apply` | ya |
| K4 | Apply memasang commit ke repo di mesin ini (checkout kamu, mis. `~/bulking-app`), cabang `argus/<job>` bila garis utama; push dan PR tetap di luar (G5) | ya |
| K5 | Dua kali `patch_read_run` per job per 24 jam | ya |

## 12. Rev 1: perubahan yang mengikat (tinjauan Opus atas rev 0; tiap butir dicek ulang terhadap kode)

Dicek ulang sendiri sebelum menulis ini: F1 (`router/job.py:427-431`: tanpa `--key-file` perintah hidup menolak "needs a terminal"; anak proses chat memakai
`stdin=DEVNULL`, `control_issues.py:108`), F2 (`router/job.py:1847` memanggil `actor()` tanpa `via`), F4 (`router/chat.py:426`: kunci `sha` lolos untuk
nama aksi berawalan `job_`), F5 (`router/patch_read.py:212`: tanpa `raw_pair` bacaan kedua menimpa yang pertama).

**Nama aksi:** `job_apply` diganti **`code_apply`** (F4), dan tiap pembangun memeriksa himpunan kunci miliknya (`set(params) - {"job","reason"}` memberi 400,
pola `chat_plan.py:179`). Aturan `job_*` di `chat.py:426` tidak diperlebar.

**F1 (dikoreksi 2026-11-27 saat membangun PR1) `patch_read_run`:** tinjauan menyebut `patch-read-run` tidak punya `--key-file` dan `--yes`; itu **keliru**:
keduanya ditambahkan lewat loop perintah hidup di `scripts/argus.py:376-381` (`argus patch-read-run --help` menunjukkannya), jadi anak proses chat bisa
menjalankannya. Yang kurang hanya `--via ui` (PR1, dicatat sebagai catatan `patch_read_run` di log job, dengan pelaku) dan slot kunci chat
`ARGUS_CHAT_READER_KEY_FILE` + cabang `_need_key` (PR2). Kedua pembaca memakai OpenRouter (`router/patch_trial.py:36-40`), jadi satu berkas kunci cukup.
Argv: `argus patch-read-run JOB --cap-usd C --via ui --key-file openrouter=K --yes`. Kunci hanya dari slot, bentuk yang diizinkan hook.

**F2 (penghalang) pelaku `ui`:** PR1 meneruskan `via` ke `_record_applied` (`job.py:1847`), ke catatan `apply_started` (`apply.py:285`) dan ke `_recovered`, dan
`prd reply` mencatat pelaku saat pindah ke WRITING (`prd_job.py:197`). Tes: `actor == "ui"`; `CLAUDECODE` tetap menang (`job.py:1736`).

**F3 batas harian:** uang yang belum terhitung hanya hidup di `self.pending` selama `PENDING_S` = 600 detik (`chat_actions.py:62,1027`), jadi setelah 10 menit
jatuh dari eksposur 24 jam. `patch_read_run` dan `prd_reply` **dihitung dari baris audit `attempt` dengan field `usd` selama 24 jam** (pola
`steps.audited`, `chat_t4b.py:360-376`), bukan dari `pending`. `exposure_of` mengembalikan 0.0 untuk aksi yang tidak dikenal (`:1208`): kedua aksi
mendapat cabang eksplisit, dan sebuah tes memeriksa bahwa aksi berbayar tanpa cabang gagal keras. `issue_reply` punya celah yang sama: diperbaiki dengan cara
itu atau dicatat sebagai celah yang diketahui di PENDING. Audit hanya dibaca 1 MiB terakhir (`audited_jobs`): dikatakan di sini.

**F5 dua bacaan:** kartu dan `code_apply` memuat catatan dengan `raw_pair=True`, supaya **kedua** bacaan tampil apa adanya. Jalur menerima `concerns`
ditentukan `pr.require_concerns_pair` (`patch_read.py:307`), bukan jenis di kartu. Bacaan pertama `concerns` tanpa bacaan kedua: jalur terima tetap tertutup.

**F6 kartu basi:** klien mengirim **sha12 yang ia lihat sebagai pemeriksaan kesamaan, bukan pemilih** (pola draf sha `job_reject`, `chat_actions.py:639`);
bagian 6 "tanpa sha dari klien" dibaca begitu. Digest memuat seluruh kartu yang dihitung ulang ditambah sha penuh dari disk, dan `read_sha` yang diteruskan
adalah sha dari disk itu. Kartu yang mengembalikan `None` atau melempar (`approve_code.py:46-50`) menjadi **409, tidak pernah lolos**.

**F7 diff:** kartu pasang tidak membawa teks diff (hanya `files[{path,marks}]`, `approve_code.py:244-254`). PR3 menambah **rute GET baca-saja untuk diff**
(aturan fd yang sama, batas byte, simpul teks saja). Tombol pasang **tertutup** bila diff yang ditampilkan terpotong atau `scrub(diff) != diff`
(karakter tersembunyi atau bidi, pola kunci), seperti aturan `issue_start` (`chat_actions.py:525-527`). Tes mengunci ini.

**F8 aturan tombol:** tombol terbuka bila setiap syarat kartu selain (f) tidak `false` **dan** (jenis (f) `ok` atau `nit` (`nit` berlaku seperti `ok`,
`apply.py:165`), atau `require_concerns_pair` lolos dan alasan diberikan). Bagian 5.3 "semua syarat benar dan ..." diganti ini.

**F9 argv:** alasan `--accept-concerns` bisa berawalan `-` (`router/reason.py:13-22`) dan argv terlihat di `ps`: dipakai satu token `--accept-concerns=R`
(atau berkas, `--accept-concerns-file`, pilihan PR1); `prd_reply` memakai `--message-file` lewat `spawner.message_file` (0600, dihapus saat reap;
`control_issues.py:93-100`, pola `issue_reply`); id job harus `fullmatch UI_ID` dan ditaruh sesudah `--`.

**F10 kata-kata:** "kartu dan apply tidak bisa tidak sepakat" (5.3) diganti: **kartu menutup berdasarkan apa yang diketahuinya; selebihnya adalah penolakan CLI,
ditampilkan apa adanya.** `argus apply` juga memeriksa `--reader argus` terhadap catatan tulisan Claude, konfigurasi git lokal, pohon bersih, HEAD,
identitas git dari `HOME` dan kesegaran pembaca domain. Unit layanan `argus-chat` harus punya `HOME` (diperiksa di mesin saat PR2).

**F11 daftar repo:** `realpath(job.inputs.repo) == realpath(issue_writer.repos[inputs.repo_name].path)` dan bukan checkout Argus.

**F12 `prd_reply`:** status yang boleh `REPLYABLE = (AWAITING_HUMAN, WRITE_FAILED)` (`prd_job.py:38`; bagian 5.1 yang hanya `AWAITING_HUMAN` diganti);
aturan pesan `pj.message_problem` (`prd_writer.reply_max`), bukan `ri.message_problem`; tolak 409 bila antrean repo itu belum selesai
(`unfinished_on`, pola `chat_plan.py:182-191`) dan bila sisa uang kurang dari batas giliran (`prd_job.py:186-189`). Rute halaman: `/api/cards/prd/<job>`.
Eksposur balasan pada job PRD yang dibuat lewat ui: 0 tambahan (pemindai menghitung `max(max_usd, pcap)`); butuh versi PRD dari `created_from_ui_in_window`.

**F13 pembaca:** batas uang adalah **total per job** (`patch_read_run.py:5-7,120-122`) dan bacaan final tidak dibaca ulang (`:94-97`): "membeli ok" dengan
putaran ulang tidak mungkin, dan batas dua kali per 24 jam hanya sabuk tambahan. Kartu menampilkan sisa `C - sudah ditagih`; `prepare` menolak bila sisa
tidak cukup untuk dua panggilan terburuk. `chat.patch_read_cap_usd` dijepit ≤ 2 (`run()` menolak di atas 2).

**F14 balapan dan restart:** `spawner.busy` hilang saat restart dan `patch-read-run` tidak memegang kunci job selama panggilan model: pembaca mengambil
satu `flock` sendiri per job (`.patch_read_run.lock`; bukan `job.lock()`, yang diambil `patch_read.record` pada tiap tulisan) agar chat dan terminal tidak berlomba. Sesudah crash: kartu memperingatkan "apply_started tanpa APPLIED"; confirm baru
menjalankan ulang apply yang sembuh lewat `_recovered` (`apply.py:344-357`); pohon kotor sesudah pemulihan gagal tampil dan tombol tidak ditawarkan lagi.

**F15 ancaman tambahan:** apply memindahkan checkout Atha ke `argus/<job>` dan membiarkannya di sana (kartu mengatakannya sebelum konfirmasi); karakter
tersembunyi di patch (F7); jaring uang (F3); argv bocor (F9); restart menghilangkan `busy` (F14); halaman **tidak pernah mengisi kolom balasan atau alasan dari
teks model atau foreman** (tes pada `app.js`).

**Amandemen yang kurang di bagian 4:** `AGENTS.md:66-72` ("The chat's only approvals are...", "applies a patch"), `SPEC_CHAT_APP.md:194,196`,
`SPEC_CHAT_MANAGER.md:9`, `SPEC_CHAT_T4B.md:13` dan K3 (:56). Tes yang mengunci aturan lama diubah di PR2: `tests/test_chat_t4b.py:492-496` (daftar yang
mengharapkan 404 untuk `job_apply`), `:499-503` (tidak ada nama aksi berisi "apply"), `tests/test_chat_ui2.py:64-65` (`prd_reply` bukan aksi); di PR3:
`tests/test_chat_t4b.py:570` dan teks `app.js` "apply is still done from the terminal".

**PR1 (CLI) jadi:** `apply --via ui`, `prd reply --via ui`, `patch-read-run --via ui` (`--key-file` dan `--yes` sudah ada), tiga tempat pelaku di atas, dan satu kunci `flock` per job untuk pembacaan patch (F14; berkas `.patch_read_run.lock`, bukan `job.lock()`, karena `patch_read.record` mengambil `job.lock()` sendiri pada tiap tulisan dan akan menolak), dengan tes.

**Mutan wajib (tulis dan jalankan sekali sesudah tinjauan kode):** (1) `exposure_of` tanpa cabang untuk dua aksi berbayar; (2) jaring audit dibuang, hanya
`pending` (tes melewati 600 detik); (3) `code_apply` menerima sha, repo, cap, cabang, pembaca atau `allow` dari klien; (4) awalan `job_` membiarkan sha
lewat; (5) `read_sha` dari klien atau sha12; (6) kartu tidak dihitung ulang di `confirm`; (7) digest tanpa catatan baca, syarat, sid atau sha disk (satu mutan
tiap komponen); (8) kartu `None` atau pengecualian dianggap terbuka; (9) aturan (f): `concerns` tanpa alasan, satu bacaan diterima, `nit` ditolak;
(10) `raw_pair=False`; (11) alasan dicek dengan `reason_problem`, atau alasan dua token argv; (12) `--allow-failed-examples`, `--note`, `--reader claude`
ditambahkan, atau `--via ui` dibuang; (13) `--cap-usd` dari klien atau tanpa jepitan 2; (14) batas dua kali per 24 jam salah satu, atau dihitung per aksi
bukan per job; (15) `prd_reply`: cek status dibuang, gerbang `WRITE_FAILED` dibalik, aturan pesan ditukar, cek sibuk atau antrean belum selesai dibuang;
(16) slot kunci salah untuk pembaca, atau `--key-file` pada apply; (17) daftar repo membandingkan nama, bukan realpath, atau checkout Argus lolos;
(18) baris `attempt` ditulis sesudah spawn atau kegagalannya diabaikan; (19) apply dijalankan sinkron di `confirm` atau status dibaca dari keluaran proses;
(20) `source_*` diterima untuk aksi baru, atau aksi baru masuk `ROUTE_ACTION`; (21) tombol terbuka walau diff terpotong atau berubah oleh `scrub`;
(22) `_record_applied` mengabaikan `via`, atau prioritas `CLAUDECODE` dibalik; (23) token `prd_approve` tidak ditolak sesudah `prd_reply` jalan.

## 13. Rev 2: apa yang PR2 membangun dan menyimpang dari rev 1 (2026-11-27)

PR2 = `router/chat_apply.py` (kelas `ApplyReply`), kabelnya di `chat_actions.py` dan `chat.py`, dua tambahan kecil di `approve_code.py`, tes `tests/test_chat_apply_reply.py`. Sama dengan bagian 12 kecuali:

- **Sisa uang pembaca (F13):** `prepare` hanya menolak bila batas total job sudah habis atau ledgernya tidak lengkap, dan menampilkan sisa `C - sudah ditagih`. Penolakan "tidak cukup untuk dua panggilan terburuk" **tidak** dibangun: itu menuntut menghitung ulang konteks dan tarif model di dalam permintaan HTTP (git dan tabel harga). Batas uangnya tetap utuh karena `patch-read-run` berhenti sendiri bila satu panggilan tidak muat dan tidak menulis apa pun; yang mungkin terjadi hanya satu bacaan tunggal (`one`) yang dilanjutkan pembaca kedua pada putaran berikutnya (kode `resume` yang ada). Eksposur yang dihitung = sisa itu.
- **Kartu pasang (F5):** `approve_code` memuat catatan dengan `raw_pair=True` dan menambah `patch_sha256` (penuh) serta `patch_read_kind`; `code_with_patch` memberi satu bacaan yang sama untuk kartu, hash dan teks diff.
- **Tombol (F8):** `GET /api/approve/code/<job>` menambah `apply` = `{action, why[, needs_reason]}` dari pembangun yang sama; `GET /api/diff/<job>` memberi teks patch utuh atau alasan ia tidak boleh ditampilkan (terlalu besar, bukan teks, karakter tersembunyi atau mirip kunci); tombol pasang tertutup bila diff tidak bisa ditampilkan utuh.
- **Nama aksi (F4):** `code_apply`; satu-satunya aksi yang boleh membawa `sha` (pemeriksaan kesamaan).
- **Kunci pembaca:** slot `ARGUS_CHAT_READER_KEY_FILE`, cadangannya `ARGUS_CHAT_KEY_FILE` (kunci OpenRouter yang sudah ada di unit layanan).
- **Jaring uang (F3):** `audited()` menjumlah baris audit `attempt=confirm` 24 jam untuk `prd_reply` dan `patch_read_run` (field `usd`); `issue_reply` masih memakai daftar `pending` 10 menit: celah yang diketahui, dicatat di PENDING.
- **Belum di PR2 (PR3, tampilan):** tombol dan kolom di halaman, rute diff di UI, teks `app.js` "apply is still done from the terminal" dan `tests/test_chat_t4b.py:570`.
