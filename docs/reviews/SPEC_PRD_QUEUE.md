# SPEC antrean PRD: issue berurutan pada satu repo, lalu tahap PRD yang membuat antreannya

Status: **rev 1, 2026-11-15; tinjauan Fable GO WITH FIXES (dua blocker, semua temuan diterapkan di bagian 4.3, 5 dan 6); menunggu tiga keputusan Atha (bagian 3)** (jalur ketat: memulai job dan membelanjakan uang tanpa
perintah per job). Langkah ketiga urutan inti (Atha 2026-11-15) sesudah VF O1 (#550) dan `argus apply` (#552, #553). Bahan: `pilots/prd_probe_v0/`
(`RESULT.md`, `GLUE_LOG.md`), `router/job.py`, `router/issue.py`, `router/apply.py`, `router/stage_viewer.py`, `docs/Reconciliation.md` 0 dan 7.

## 1. Apa yang dibuktikan probe dan apa yang tidak

Probe (n = 1, tiga irisan kecil, aplikasi yang tesnya dikenal agen, Claude menjadi perekat) menemukan: tiga apply dengan tangan (kini `argus apply`),
dua ketergantungan tersembunyi di sisi Argus (snapshot tanpa nama repo dan `as_is`; proxy viewer hanya meneruskan jalur tetap), dan bahwa mengurutkan
tiga irisan dengan tangan **murah** (penilaian probe untuk antrean: "rendah"). Jadi antrean bukan jawaban atas rasa sakit yang terukur; ia dikerjakan
karena Atha menerima urutannya, dan **ukurannya** (bagian 8) harus menunjukkan apakah ia berguna. Angka yang harus diingat: delapan issue berantai
masing-masing sekitar 57% sampai staging tanpa Claude (PENDING "Ukuran") kira-kira 1% untuk semuanya; antrean **tidak** menaikkan angka per issue.

## 2. Yang dihapus dan yang tidak dihapus antrean

Satu issue punya dua gerbang manusia yang tetap: `approve --sha` pada draf (`router/job.py:906`) dan `apply --read-sha` pada patch (K1 SPEC_ARGUS_APPLY).
Antrean v0 **tidak menyentuh keduanya** dan tidak pernah memanggil `approve` atau `apply`. Yang diambilnya dari perekat probe: memilih commit dasar issue
berikutnya, memulai job, membukukan biaya per antrean, dan berhenti di kegagalan. Maka antrean v0 **bukan "tinggalkan"**: tiap issue tetap butuh dua
tindakan manusia. Itu dikatakan di sini supaya angka "tanpa campur tangan Claude" tidak dihitung dari antrean sebelum keputusan D3 diambil.

## 3. Tiga keputusan Atha (usulan Claude di muka; spek ini bekerja dengan usulan sampai Atha mengubahnya)

- **D1 berhenti di kegagalan pertama atau lanjut yang mandiri.** Usul: **berhenti** untuk seluruh antrean. Issue berikutnya berjalan di atas commit hasil
  issue sebelumnya (bagian 4), jadi "mandiri" butuh deklarasi ketergantungan yang belum ada; ditunda ke v1 bila diukur perlu.
- **D2 batas biaya dan "go live".** Usul: batas **per antrean** (`--max-usd`, tertutup di atas konstanta `QUEUE_MAX_USD`; usulan nilai Atha yang menentukan,
  bagian 4.3) ditambah batas per job yang sudah ada (`issue_writer.code_max_usd`, `router/issue.py:38`). "Go live" **tidak** masuk antrean: antrean
  berakhir di `APPLIED`; deploy ke staging tetap perintah tersendiri dan kata Atha per aksi, seperti `stage deploy`. Persetujuan antrean (`queue go`) adalah
  persetujuan **jumlah uang** itu.
- **D3 siapa menyetujui tiap draf.** Usul untuk v0: **orang, per draf, lewat `approve --sha` yang ada** (CLI; kartu chat tertahan `via=ui`), dan per patch lewat `apply --read-sha`.
  Alternatif yang tidak diusulkan: (b) Claude dengan izin tetap, seperti probe untuk job viewer kecil (sah, tetapi Claude di tengah, jadi angka "tanpa Claude" tidak boleh
  menghitungnya); (c) satu persetujuan PRD yang mencakup semua draf: ia memindahkan penilaian "tes sehat" (masih manusia, `GLUE_LOG.md`) ke momen yang
  draf belum ada; ditinjau lagi sesudah angka v0.

## 4. Bagian A: antrean berurutan (PR 1)

### 4.1 Bentuk
`queues/<id>/queue.json` (di luar `jobs/`, di `.gitignore`; kunci `queues/<id>/.lock` `flock` tak-memblokir, seperti `Job.lock`, `router/job.py:163`):
`{id, repo, base_commit (40 heksa, sudah di-resolve), max_usd, items: [{n, issue_sha256, job (id, dicatat SEBELUM job dimulai), at}], approved: {sha, at} | null, closed: {at, note} | null, created_at}`.
Teks issue disimpan di `queues/<id>/issue-<n>.md` dan **tidak pernah** dibaca ulang dari tempat lain; job menerima teks itu persis (sha dicek sebelum dipakai).
Status antrean **diturunkan** setiap kali dari `job.json` tiap item, tidak disimpan (satu hal yang bisa basi lebih sedikit): `PENDING` (belum `go`), `WAITING <apa yang manusia harus lakukan>`,
`STOPPED <alasan>`, `DONE`, `CLOSED`.

### 4.2 Perintah
- `argus queue new --repo <nama> --commit <sha> --max-usd <usd> --issue f1.md --issue f2.md ...`: repo dari daftar `issue_writer.repos` (K2: tidak pernah Argus-agent); commit di-resolve ke 40 heksa;
  paling banyak `QUEUE_MAX_ITEMS` item (usul 8); satu antrean tidak-`CLOSED`/tidak-`DONE` per repo (dua antrean pada satu repo berebut HEAD). Mencetak daftar, sha tiap issue, dan **sha daftar** (sha256 dari repo, commit, batas biaya, dan sha issue berurutan).
- `argus queue go <id> --sha <sha daftar, 12+>`: persetujuan manusia atas daftar dan jumlah uangnya. Tanpa ini `step` menolak.
- `argus queue step <id>`: **paling banyak satu jalan model per panggilan** (drafter item berikutnya) dan hanya bila syaratnya terpenuhi; selain itu hanya mencetak apa yang menunggu (perintah `approve --sha ...` atau `apply --read-sha ...` lengkap dengan sha dari `status`).
  Idempoten: dipanggil dua kali, yang kedua tidak memulai apa pun.
- `argus queue status <id>` (baca saja), `argus queue close <id> --note T` (manusia menutup antrean yang macet; tanpa menghapus job).

### 4.3 Aturan `step`
1. Kunci antrean dipegang; `approved` ada dan sha daftar yang dihitung ulang dari `queue.json` dan berkas issue (repo, commit, `max_usd`, urutan, sha issue, cap per job, environment) sama dengan `approved.sha`; belum `CLOSED`. `queue new` menolak repo yang `realpath`-nya checkout Argus (`repo_of` hanya memeriksa nama; `apply.py:137`), memeriksa `--commit` terhadap HEAD, id antrean berpola tetap, dan aturan "satu antrean aktif per repo" dikunci per `realpath` di bawah kunci global (`apply.py:63`). `start_code` dipanggil dengan `environment=` dari `repo_of` (`issue.py:314`). Item 2 dan seterusnya juga menolak bila entri `APPLIED` sebelumnya `as_is` bukan `True` (jalur manual `argus applied` mencatat commit apa saja). `queue close` tidak menyentuh job yang hidup; antrean `CLOSED` tidak pernah `step`.
2. Turunkan keadaan tiap item dari `job.json` (hanya `step` yang melupakan; `status` tidak menulis apa pun). **Item belum dimulai** bila id tercatat tetapi jobnya hilang, atau jobnya tanpa tahap (`stages` kosong) berstatus `NEW`, `ABANDONED` atau `BLOCKED` (konfirmasi ditolak, tanpa kunci, atau potong di antara pembuatan `job.json` dan `DRAFTING`: `resume` dan `redraft` menolak job `NEW` tanpa tahap, temuan Fable B1): `NEW` di-`abandon` lebih dulu, id dilupakan, id baru dibuat. Seperti `issue._handed` (`router/issue.py:327-345`) id yang tercatat hanya dianggap milik item bila sha issue, commit dan repo di job sama dengan yang di antrean. `step` membangun `Deps` seperti `scripts/argus.py:283-290` (`--key-file`, `--yes`); tanpa tty dan tanpa `--yes` ia menolak sebelum membuat job.
3. **Berhenti (`STOPPED`)** bila ada item berstatus gagal: `DRAFT_FAILED`, `AGENT_FAILED`, `REVIEW_INVALID`, `BLOCKED`, `REJECTED`, `ABANDONED` (juga `RESEARCH_*`; antrean tidak memakai `--research`). Item sesudahnya tidak dimulai.
   Keadaan yang bisa pulih (`DRAFT_FAILED` sesudah `redraft`, `AGENT_FAILED` sesudah `retry`) membuat panggilan `step` berikutnya menurunkan ulang tanpa keadaan tersimpan; yang final (`REJECTED`, `ABANDONED`) hanya selesai dengan `queue close`.
4. **Menunggu** bila ada item yang belum `APPLIED` dan jobnya hidup (`DRAFTING`, `AWAITING_APPROVAL`, `AGENT_RUNNING`, `REVIEW_READY`): mencetak aksi manusianya, tidak memulai apa pun.
5. **Item berikutnya** (semua sebelumnya `APPLIED`) dimulai hanya bila: (a) commit dasarnya = `commit` pada entri `APPLIED` terakhir di log job sebelumnya (item 1: `base_commit`); (b) `HEAD` repo target sama dengan commit itu (jika tidak, `STOPPED "HEAD bergeser"`, karena `argus apply` menolak HEAD yang lain,
   `router/apply.py`); (c) biaya: untuk tiap item yang sudah dimulai, **komitmen** = yang sudah dibelanjakan (`spent_nano`) **hanya** bila jobnya `ABANDONED`, `BLOCKED` atau `REVIEW_INVALID` (tidak bisa membelanjakan lagi, `LEGAL` di `router/job.py:66-79`); selain itu `job.data["max_usd"]` penuh, termasuk `APPLIED` dan `REJECTED` karena `argus judge` masih bisa membelanjakan (`JUDGEABLE`, `job.py:1049`; `judge_max_usd` 0,30), dan `DRAFT_FAILED`/`AGENT_FAILED` yang bisa pulih; dihitung dalam nano (`to_nano`), bukan float; `Σ komitmen + cap item baru <= max_usd`, sehingga **total tidak pernah melebihi `max_usd`
   sekalipun semua job membelanjakan capnya**; jika tidak, `STOPPED "batas biaya"`. Cap item = `issue_writer.code_max_usd` (diperiksa seperti K3). Lalu `rj.start_code(..., job_id=<id yang dicatat dulu>)`.
6. `QUEUE_MAX_USD` adalah konstanta di kode (bukan config), perintah `new` menolak yang lebih besar; **nilainya Atha yang menetapkan** (usul awal $5,00; tiga item pada $1,00 per job = $3,00 sudah di bawahnya).

### 4.4 Yang sengaja tidak ada
Tanpa `approve` dan `apply` otomatis, tanpa daemon (dijalankan tangan atau `/loop`), tanpa push, merge, deploy, tanpa `--research`, tanpa lewati-item (melompati item merusak kontrak urutan), tanpa antrean lintas repo (satu repo), tanpa notifikasi (di luar jatah; `status` cukup).

## 5. Bagian B: tahap PRD (dibuka sesudah pilot bagian A; PR 2 dan 3 dengan spek ringkas sendiri)
- `argus prd new`: obrolan memakai mesin penulis issue (`router/issue.py`; mode baru, biaya model) menghasilkan `PRD.md` dan `issues.json` berurutan (`n`, `repo`, `teks`, `paths`: jalur API yang dibekukan kontrak). `argus prd approve --sha`: satu persetujuan manusia atas dua berkas itu; hasilnya antrean `PENDING` (tetap perlu `queue go` untuk uang).
- **Pemeriksaan jalur Argus** (tanpa model; temuan probe 2): `issues.json` memuat `paths` (dengan sisi: viewer `/api/x` atau ledger `/x`, lengkap dengan query) dan `fields` (nama field yang dibaca viewer dari snapshot). Dicocokkan dengan **kode yang berjalan**, bukan salinan: `router/stage_viewer.API` (daftar putih proxy, `stage_viewer.py:76`, jangkar penuh, dicocokkan dengan jalur beserta query, `:530`) dan tabel nama field `JOB_FIELDS`, `STAGE_FIELDS`, `LOG_FIELDS` di `router/stage_data.py:93-98` (itu nama field, bukan jalur). Jalur yang tidak diteruskan atau data yang tidak diterbitkan membuat PRD **ditolak** dengan butir "perubahan Argus jalur ketat dulu"; antrean tidak pernah memuat item untuk Argus-agent.
- Tidak membuat `PLAN.md` staging (itu aksi Claude/Atha di luar antrean).

## 6. Tes (PR 1, sebelum kode, merah di kode lama)
Baru `tests/test_queue.py` (tanpa sandbox, model dipalsukan seperti `tests/test_apply_cmd.py`): `step` sebelum `go` ditolak; `go` dengan sha salah ditolak; `step` dua kali memulai satu job; commit item 2 = commit `APPLIED` item 1; `HEAD` bergeser berhenti; kegagalan menghentikan dan tidak memulai item berikutnya; pemulihan `redraft` melanjutkan; komitmen biaya sebagai fungsi murni (`APPLIED` dan `REJECTED` dihitung cap penuh, `ABANDONED`/`BLOCKED`/`REVIEW_INVALID` dihitung terpakai, penolakan tepat di batas, nano) dan lewat `step`; `argus judge` pada item `APPLIED` tidak membuat total melebihi `max_usd`; konfirmasi ditolak atau tanpa kunci pada `step` lalu `step` berikutnya memulai ulang item; potong dengan job `NEW` tanpa tahap; id tercatat menunjuk job dengan issue atau commit lain; `queue.json` diubah sesudah `go` (`max_usd`, urutan) ditolak; `step` tidak pernah memanggil `approve` atau `apply` (mata-mata); `status` tidak menulis; repo yang sama dengan dua nama; `environment` diteruskan; `step` sesudah `close`; `as_is` False berhenti; potong di tengah mulai (id tercatat, job tidak ada) tidak memulai dua; dua antrean aktif pada satu repo ditolak; `new` menolak Argus-agent, repo di luar daftar, `max_usd` di atas konstanta, item di atas `QUEUE_MAX_ITEMS`; teks issue yang berubah di disk sesudah `go` ditolak. Mutan: daftar di `verification/queue_mutants.py`, dijalankan sesudah tinjauan diff.

## 7. Urutan kerja (alur jalur ketat, Atha 2026-11-15)
Spek, tinjauan Fable atas spek, perbaikan, **tiga keputusan Atha**, tes merah, kode, tinjauan Fable atas diff, perbaikan, mutan, `precheck`, satu `verify_at`, merge hanya bila Atha bilang. Pilot hidup (bagian 8) butuh jumlah uang dari Atha.

## 8. Ukuran dan pilot
Pilot v0: satu antrean 3 issue kecil pada satu repo latihan, `--max-usd` yang Atha sebut. Dicatat: item yang sampai `APPLIED`, jumlah tindakan manusia per item, menit sampai `APPLIED`, biaya, di mana antrean berhenti dan mengapa. Dilaporkan sebagai **n = 1**, terpisah dari data lama dan dari papan skor (`verification/scoreboard-*.json`),
dan tidak dipakai untuk menjual "tinggalkan" sebelum angka per-issue-nya diukur pada banyak antrean (titik cek 2026-11-29).

## 9. Risiko dan yang tidak dibuktikan
- Dua gerbang manusia per item bertahan; manfaat antrean mungkin kecil (penilaian probe "rendah"). Pilot menjawab, bukan spek ini.
- Antrean menganggap repo target tepercaya dan hanya Argus yang mengubahnya selama antrean hidup; `HEAD` bergeser dideteksi saat item berikutnya mulai, tidak saat item sedang berjalan.
- `max_usd` membatasi uang model Argus; ia tidak membatasi uang di luar (staging, VM).
- Pemeriksaan jalur Argus (bagian B) hanya menangkap jalur yang ditulis di `issues.json`; PRD yang lupa menulis `paths` lolos. Ia membantu, tidak menjamin.
