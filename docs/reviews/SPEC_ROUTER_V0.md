# Spec Router v0: satu perintah `argus` untuk sebuah job

Status: **spec, belum dikoding.** 2026-10-23. Ditulis Claude untuk review Atha/GPT. **Keputusan yang diminta: bagian 9.**
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
argus research ...             ─▶ Alur A apa adanya (lihat K1)
```

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

## 2. Uang: cap per job (baru)

- `--max-usd` per job, dengan bawaan dari config (`router.job_max_usd`, misalnya $1,00). **Ledger job** adalah gabungan
  ledger semua run tahapnya (`reconcile_ledger` atas setiap `events.jsonl`).
- Sebelum memulai tahap mana pun, router menghitung **sisa = cap job − yang tercatat sudah terpakai (kasus terburuk
  untuk panggilan yang terputus)**. Cap run tahap itu = `min(cap tahap, sisa)`. Bila sisa tidak cukup untuk satu attempt
  tahap itu, tahap **tidak dimulai** (`BLOCKED budget`).
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

## 6. Alur A di v0 (K1)

`argus research` hanyalah pembungkus `main.py` (kontrak `SALES_REPORT`, `penjualan.csv`) dengan job, cap job, dan
konfirmasi yang sama. Prompt bebas belum didukung, dan ini **ditulis jujur di help**. Gunanya agar bentuk router dan
ledger job sama untuk kedua alur sejak awal. Alur A yang umum adalah pekerjaan terpisah (kontrak riset dari prompt).

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
5. **Crash di setiap tahap:** mengulang perintah melanjutkan run yang sama (id sama), bukan membeli ulang.
6. **Kunci:** tidak ada di argumen, `job.json`, log, atau lingkungan setelah tahap selesai. Tanpa tty, tahap live
   ditolak. Bentuk kunci yang salah membuat tahap tidak dimulai.
7. Konfirmasi "N" tidak memulai apa pun.
8. Root per job: tidak ada berkas baru di `fixtures/` checkout Argus. `run_code_task`/`approve` dengan `root` bawaan
   berperilaku sama (tes lama tetap lulus).
9. `research`: pembungkus memakai cap job dan konfirmasi yang sama, dan prompt selain goal bawaan ditolak dengan pesan
   jelas.

Mutan untuk setiap jaminan di atas, dan `verify.sh` penuh di latar belakang.

## 9. Keputusan yang diminta

| | Pertanyaan | Usul |
|---|---|---|
| K1 | `argus research` di v0? | **Ya, sebagai pembungkus jujur** Alur A yang ada (bagian 6). Alternatif: tunda sampai Alur A umum |
| K2 | Cap gabungan per job | **Ya**, `--max-usd` per job, bawaan $1,00 dari config. Cap tahap dibatasi sisa |
| K3 | Approve | **Perintah terpisah** `argus approve`; router berhenti setelah draf. Bawaan `--no-reference` dan cap dari profil |
| K4 | Kunci | **Diminta setiap tahap live**, tersembunyi, tidak pernah disimpan (seperti `go_live`). Konfirmasi `[y/N]` menggantikan gerbang per pilot |
| K5 | Root per job | **Ya**: refactor kecil `root=` di `run_code_task` dan `approve_draft`; job tidak mengotori repo |
| K6 | Menerapkan patch | **Di luar v0.** Router mencetak perintahnya; `argus apply` (branch, `git apply`, `verify`) bisa menyusul |
| K7 | Ulang drafter | **Manual**, lewat `argus redraft <job>`; tidak ada pengulangan otomatis |

Perkiraan: satu PR kode (router, refactor root, tes, mutan), lalu satu pilot router dengan task kecil yang nyata. Pilot
itu sekaligus mengukur apakah jumlah keputusan turun dari ±17 menjadi sekitar 4 (mulai, approve, terapkan, ditambah
kunci).
