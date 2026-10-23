# Spec Router v0: satu perintah `argus` untuk sebuah job

Status: **dikoding di #163** (2026-10-23; implementasi: `REVIEW_ROUTER_V0.md`); celah yang tersisa: `SPEC_ROUTER_STATUS.md`. Spec ditulis 2026-10-23. Ditulis Claude untuk review Atha/GPT. Keputusan (bagian 9): **K2–K7
disetujui, K1 ditunda** (Atha 2026-10-23). Tiga tambahan sebelum ngoding, juga dari review itu: kunci per job (bagian
1a), cap tahap dicatat saat mulai (bagian 2), dan approve terikat ke draf yang dilihat (bagian 4).
Latar: diskusi 2026-10-23 ("orchestrator yang memilih Alur A atau B"). Usul yang disepakati: v0 **tanpa model**; jalur
dipilih manusia lewat subperintah. Router dengan model baru dibuat setelah kedua alur punya banyak tujuan.

## 0. Masalah yang diselesaikan

W2b-2 membuktikan alur penuh Alur B, tetapi Atha (dengan Claude) harus menjalankan tiap tahap sendiri: intake,
`draft_task.py`, `approve_draft.py`, membuat gerbang `go_live` per pilot, `run_code_task.py`, `build_review.py`, lalu
menerapkan patch. Jumlahnya sekitar 17 keputusan untuk satu task kecil (`pilots/m6_w2b/w2b2/RESULT.md`), dan sebagian
besar adalah langkah mekanis, bukan penilaian.

Router v0 menggabungkan tahap-tahap itu menjadi satu **job** dengan state yang bisa dilanjutkan. Hanya tiga hal yang
tetap meminta manusia: **memulai** (dengan melihat batasnya), **approve draf**, dan **menerapkan patch**.

```
argus code --repo <path> --commit <rev> --issue-file issue.txt      (atau --issue "...")
  job baru  ─▶ intake ─▶ drafter (live: konfirmasi + kunci) ─▶ AWAITING_APPROVAL   [proses berhenti]
argus status <job>                                            ringkasan DRAFT_REVIEW + biaya sejauh ini
argus approve <job>            ─▶ approve --no-reference ─▶ agen (live: konfirmasi + kunci) ─▶ paket review
                                                              ─▶ REVIEW_READY      [proses berhenti]
argus reject <job> "alasan"    ─▶ REJECTED
```

Router v0 **hanya alur `code`** (K1). `argus research` ditunda sampai Alur A bisa menerima prompt bebas; saat itu bentuk
job dan ledger-nya diseragamkan.

## 1. Job

- Direktori `jobs/<job_id>/` berisi `job.json` (state, input, keputusan manusia beserta waktunya, run per tahap) dan
  root kerja job (K5).
- **State:** `NEW → INTAKEN → DRAFTING → AWAITING_APPROVAL → (APPROVED → AGENT_RUNNING → REVIEW_READY | AGENT_FAILED) |
  REJECTED | DRAFT_FAILED | BLOCKED`. Transisi yang sah ditulis seperti `codetask/status.py`. `job.json` ditulis secara
  atomik.
- **Run per tahap punya id yang ditentukan dari job:** `<job>-d1`, `<job>-d2`, …, `<job>-a1`. Perintah yang diulang
  setelah crash akan **me-resume** run yang ada (`--resume` milik drafter dan agen), bukan memulai run baru.
- Drafter yang gagal (`NO_DRAFT`) tidak diulang otomatis. `argus redraft <job>` menjalankan `d2` atas keputusan
  manusia, karena itu juga keputusan uang.
- **`jobs/` masuk `.gitignore`.** Isinya snapshot repo target, yang bisa saja kode privat.

## 1a. Kunci per job

Setiap perintah yang mengubah state job (`code`, `approve`, `reject`, `redraft`, dan resume tahap mana pun) mengambil
`flock` eksklusif tanpa menunggu (`LOCK_EX | LOCK_NB`) pada `jobs/<id>/.lock` selama perintah berjalan, termasuk selama
run tahapnya. Perintah kedua yang datang selama kunci dipegang **ditolak** dengan pesan "job sedang dipakai oleh
perintah lain", **tanpa mengubah apa pun dan tanpa memanggil model**. Tujuannya: `argus approve` yang terpencet dua kali
di dua terminal tidak menjalankan dua agen yang sama-sama menghitung sisa cap dari ledger yang sama.

`argus status` hanya membaca, jadi tidak mengambil kunci. Kunci dilepas oleh sistem operasi saat proses mati, sehingga
job yang crash bisa dilanjutkan.

## 2. Uang: cap per job (baru)

- `--max-usd` per job, dengan bawaan dari config `router.job_max_usd` = **$1,00**. **Ledger job** adalah gabungan ledger
  semua run tahapnya (`reconcile_ledger` atas setiap `events.jsonl`).
- **Dasar angka $1,00 (ledger W2b):** run drafter tercatat $0,16, $0,22, $0,29 (W2b-1) dan $0,09, $0,19, $0,18 (W2b-2),
  jadi terburuk **$0,29** dan median ±$0,19. Satu attempt agen dengan profil `large` dicadangkan **$0,45** (45.000 token ×
  $10/M); `large_usd` juga $0,45. Drafter terburuk ditambah satu attempt `large` = **$0,74**. Sisa $0,26 cukup untuk satu
  redraft dengan biaya median (total ±$0,93). Dua redraft terburuk (2 × $0,29 + $0,45 = $1,03) **tidak** muat, dan agen
  akan `BLOCKED budget`; kasus itu memang sebaiknya kembali ke manusia. Cap agen untuk `large_usd` ($0,75 di W2b-2) di
  bawah cap job ini menjadi `min(0,75, sisa)`, misalnya $0,71 setelah drafter $0,29: cukup untuk satu attempt, dan attempt
  kedua hanya bila yang pertama ≤ $0,26.
- Sebelum memulai tahap baru, router menghitung **sisa = cap job − yang tercatat sudah terpakai (kasus terburuk untuk
  panggilan yang terputus)**. Cap run tahap itu = `min(cap tahap, sisa)`. Bila sisa tidak cukup untuk satu attempt tahap
  itu, tahap **tidak dimulai** (`BLOCKED budget`).
- **Cap tahap dicatat saat tahap mulai, dan resume memakai angka itu.** `job.json` menyimpan `cap_usd` setiap tahap pada
  saat tahap itu pertama dimulai, sebelum run-nya dibuat. Resume tahap (`--resume` milik drafter atau agen) memakai
  angka tercatat itu, **tidak dihitung ulang**. Bila dihitung ulang dari sisa job, uang yang sudah dipakai tahap itu
  terpotong dua kali (dari sisa job dan dari ledger run-nya sendiri), atau capnya malah bisa naik bila cap job diubah.
  Run sendiri sudah menghitung pengeluarannya dari ledger-nya (`reservation_from_ledger`).
- Tidak ada jalur uang baru: setiap panggilan model tetap lewat `run_drafter` dan `run_code_task`, dengan reservasi dan
  ledger yang sama. Router sendiri **tidak memanggil model** di v0.

## 3. Live: konfirmasi dan kunci

Gerbang `go_live` per pilot diganti satu langkah umum sebelum setiap tahap live:
1. tampilkan **batas efektif**, dihitung oleh fungsi yang sama dengan yang dipakai run: model, profil, attempt, cap
   tahap, sisa cap job, dan selisih config terhadap `config.yaml` bila memakai `--config`;
2. tanya `Lanjut? [y/N]`;
3. minta kunci dengan prompt tersembunyi, dengan cek bentuk yang sama (`sk-ant-`, tanpa spasi, tidak ganda). Kunci
   **tidak pernah** menjadi argumen, ditulis ke file, atau ditampilkan, dan di-unset setelah tahap selesai;
4. catat waktu (konfirmasi, kunci, selesai) ke `job.json` untuk ukuran supervisi.

Tanpa terminal interaktif (stdin bukan tty), tahap live ditolak.

## 4. Approve

`argus approve <job> [--max-usd X] [--max-iterations N] [--task <nama>]`:
- **terikat ke draf yang dilihat:** `argus status` menampilkan **sha256 draf** (12 karakter pertama), seperti `draft_sha256`
  milik W2a. Layar konfirmasi `approve` menampilkan ulang sha itu, **berkas writable**, dan **perintah validasi beserta node
  wajibnya**, sebelum `[y/N]`. Bila draf di disk tidak lagi sama dengan yang dihitung saat konfirmasi, approve ditolak.
  Sha draf dan sha kontrak hasil approve dicatat di `job.json`. Sebelum tahap agen mulai (dan saat resume), router
  memastikan sha kontrak yang akan dijalankan agen **sama** dengan yang tercatat saat approve. Bila tidak, agen tidak
  mulai (`BLOCKED contract_changed`). Alasannya: di v0 approve berjalan tanpa patch referensi, jadi tesnya buatan drafter
  dan belum terbukti; manusia harus menyetujui isi yang persis ia baca;
- membaca draf `DRAFTED` terakhir; nama task bawaan diturunkan dari job;
- cap agen bawaan dari profil yang dipilih drafter (`large_usd` → $0,75, lainnya → $0,50; sama dengan W2b-2), tetapi
  dibatasi sisa cap job;
- menjalankan `dr.check` + `dr.approve` dengan `--no-reference` (K1 W2b). Dengan `--reference-patch P`, task menjadi
  `proven`;
- mencatat waktu approve dan siapa (`$USER`), lalu langsung lanjut ke tahap agen (konfirmasi dan kunci, bagian 3).

## 5. Selesai

`REVIEW_READY`: router mencetak `PR.md`, letak `changes.patch`, dan perintah untuk menerapkannya. **Menerapkan patch
ke repo target tetap dilakukan manusia di v0** (K6). Agen gagal (`FAILED_ACCEPTANCE`, `BLOCKED`) membuat job
`AGENT_FAILED` dengan ringkasan verdict, tanpa percobaan ulang otomatis.

## 6. Alur A (K1: ditunda)

Tidak ada `argus research` di v0. Alasannya (Atha): pembungkus demo CSV dengan kontrak tetap belum akan dipakai,
tetapi tetap menambah kode, tes, dan mutan yang harus dirawat. Dicatat di `PENDING.md`; dibuat bersama Alur A yang
menerima prompt bebas.

## 7. Perubahan kode yang dibutuhkan

- `scripts/argus.py` (CLI) dan `router/job.py` (state, ledger job, langkah tahap). Tidak menyentuh loop agen atau
  drafter.
- **Root kerja per job (K5).** `run_code_task` dan `approve_draft` sekarang memakai `ROOT` (checkout Argus) untuk
  `fixtures/`, jadi setiap job akan mengotori repo dengan record intake dan task. Usul: keduanya menerima `root=`, sama
  seperti `run_drafter` dan `dr.check`/`dr.approve`, dan job memakai `jobs/<id>/root/fixtures/...`. Refactor kecil
  dengan tes bahwa perilaku bawaan (`root=ROOT`) tidak berubah.
- Intake job memakai `acceptance/intake.py` apa adanya (repo dan commit eksplisit, exclude bawaan
  `verification`, `pilots` bila ada, atau dari `--exclude`).

## 8. Tes (fake model, fake validate; setiap tes harus gagal di kode lama)

1. Job end-to-end dengan model palsu: intake, drafter `DRAFTED`, `AWAITING_APPROVAL` (proses berhenti, **agen tidak
   jalan**), `approve`, agen `DONE`, `REVIEW_READY`, paket valid.
2. **Agen tidak pernah mulai tanpa `approve`**: perintah lain (`status`, mengulang `code`) tidak memajukan state.
3. `reject` membuat job tidak bisa di-approve lagi.
4. **Cap job:** drafter memakai X; cap agen = `min(cap tahap, cap job − X)`; bila sisa kurang dari satu attempt, agen tidak
   dimulai (`BLOCKED budget`) dan tidak ada panggilan model.
5. **Crash di setiap tahap:** mengulang perintah melanjutkan run yang sama (id sama), bukan membeli ulang. **Cap tahap
   yang di-resume sama dengan yang tercatat saat mulai**, walau ledger job sudah bertambah atau cap job diubah di config
   (tidak terpotong dua kali, tidak naik).
6. **Kunci:** tidak ada di argumen, `job.json`, log, atau lingkungan setelah tahap selesai. Tanpa tty, tahap live
   ditolak. Bentuk kunci yang salah membuat tahap tidak dimulai.
7. Konfirmasi "N" tidak memulai apa pun.
8. Root per job: tidak ada berkas baru di `fixtures/` checkout Argus. `run_code_task`/`approve` dengan `root` bawaan
   berperilaku sama (tes lama tetap lulus).
9. **Kunci per job:** saat satu perintah memegang kunci (misalnya agen sedang jalan), `approve`, `redraft`, atau `code`
   kedua pada job yang sama ditolak dengan "job sedang dipakai", tanpa mengubah `job.json` dan tanpa panggilan model.
   `status` tetap jalan. Setelah proses pemegang kunci mati (crash), perintah berikutnya bisa mengambil kunci.
10. **Approve terikat ke draf:** `status` dan layar konfirmasi `approve` menampilkan sha draf yang sama, writable, dan
    validasi. Draf yang berubah setelah `status` (atau di antara layar konfirmasi dan approve) ditolak. Kontrak yang
    diubah setelah approve membuat agen tidak mulai. Sha draf dan kontrak tercatat di `job.json`.
11. `jobs/` ada di `.gitignore` (tes membaca berkasnya).

Mutan untuk setiap jaminan di atas, dan `verify.sh` penuh di latar belakang.

## 9. Keputusan yang diminta

| | Pertanyaan | Usul |
|---|---|---|
| K1 | `argus research` di v0? | **Ditunda** (Atha). v0 hanya alur `code` |
| K2 | Cap gabungan per job | **Ya**, `--max-usd` per job, bawaan $1,00 (dasar: ledger W2b, bagian 2). Cap tahap dibatasi sisa dan dicatat saat mulai |
| K3 | Approve | **Perintah terpisah** `argus approve`; router berhenti setelah draf. Bawaan `--no-reference` dan cap dari profil |
| K4 | Kunci | **Diminta setiap tahap live**, tersembunyi, tidak pernah disimpan (seperti `go_live`). Konfirmasi `[y/N]` menggantikan gerbang per pilot |
| K5 | Root per job | **Ya**: refactor kecil `root=` di `run_code_task` dan `approve_draft`; job tidak mengotori repo |
| K6 | Menerapkan patch | **Di luar v0.** Router mencetak perintahnya; `argus apply` (branch, `git apply`, `verify`) bisa menyusul |
| K7 | Ulang drafter | **Manual**, lewat `argus redraft <job>`; tidak ada pengulangan otomatis |

Perkiraan: satu PR kode (router, refactor root, tes, mutan), lalu satu pilot router dengan task kecil yang nyata. Pilot
itu sekaligus mengukur apakah jumlah keputusan turun dari ±17 menjadi sekitar 4 (mulai, approve, terapkan, ditambah
kunci).
