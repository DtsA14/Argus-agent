# Pending

Daftar kerja Argus yang **masih terbuka**. Status milestone dan ADR beserta buktinya ada di [`docs/Reconciliation.md`](docs/Reconciliation.md)
(satu-satunya tempat status); riwayat semua butir yang sudah selesai (bukti, angka, PR) ada di
[`docs/reviews/PENDING_ARCHIVE_2026-10-22.md`](docs/reviews/PENDING_ARCHIVE_2026-10-22.md) dan `docs/reviews/`.

Terakhir diperbarui: 2026-10-28 sore (batch 4 3/5, #214; jalur cepat #215/#216, margin input #217, dev set 1 #218; arah baru:
coding agent untuk production, latihan `argus-ledger`); malam: #220, #221, `argus-ledger` tahap 0–3a.

Legenda: `[ ]` belum dimulai · `[~]` sebagian · `[x]` selesai (dipindah ke arsip saat daftar ini dirapikan berikutnya).

## Ringkasan

| | Status | Rinci |
|---|---|---|
| M1–M3, general-task agent | `[x]` | Reconciliation bagian 1 |
| M6 repo → PR | `[x]` MVP | repo Argus: 6 task `agent-completed`; sympy: 11 instance, 3/4 `resolved` tanpa bocoran (Reconciliation bagian 4) |
| M5 observability | `[~]` | ledger, inspektor, `pilot_report.py`; belum: tracing, supervisi, benchmark tidak jenuh |
| M4, M7, M8, M9, capability pack | `[ ]` | ditunda sampai ada bukti kebutuhan (keputusan 2026-10-21) |
| ADR-002, 004, 005, 006, 007 | `[~]` | ada untuk code task (Reconciliation bagian 2) |
| ADR-001, 003 | `[ ]` | target M7 dan M8 |

## Arah sejak 2026-10-28: coding agent untuk production

Diputuskan Atha 2026-10-28 (Reconciliation bagian 7). SWE-bench turun jadi **±20% usaha** (dev set regresi + batch baru sesekali untuk
angka yang boleh diklaim); **±80% ke task nyata** lewat dogfooding.

- [~] **Aplikasi latihan `argus-ledger`** (repo terpisah, `~/argus-ledger`, lokal): dashboard ledger Argus dari folder `jobs/`.
  Setiap fitur = satu job Argus. Issue `~/argus-ledger-issues/` (001–010 **ditulis Claude atas delegasi Atha**). Sejak tahap 6
  **jalur cepat** (Atha 2026-10-28): Claude approve draf, review patch, cek, dan commit sendiri; dari Atha hanya "go live" per job.
  **12 task di `main` (tahap 0–10), total $0,5688, 0 tes lama dilonggarkan, 0 patch ditulis ulang.** Agen 10/12 di attempt
  pertama; 010b butuh retry (5 attempt, 4 `context_limit`); 010 ($0,0575) DONE tapi **tidak di-merge** (2 cacat yang lolos
  dari tesnya, ditemukan uji serangan). Drafter gagal sekali
  (tahap 4 d1: batas 500 karakter item rencana tidak disebut di pesan error → #223), redraft lolos 1 submit.

  | Tahap | Fitur | Job | Agen | Biaya | Cek di data asli |
  |---|---|---|---|---|---|
  | 0 `c564aee` | CLI `ledger summary` | `j20261028_082955_aea9` | 6 langkah | $0,0317 | angka cocok ledger |
  | 1 `0720b43` | biaya dari ledger (nano, worst case), kolom rata | `…091419_915f` | 16 | $0,0529 | 32 job = `spent_nano` Argus, 0 selisih |
  | 2 `cb5d55a` | API JSON FastAPI (`ledger_py312`) | `…103452_6a83` | 18 | $0,0289 | `/summary` = CLI; traversal 404 |
  | 3a `8b7312f` | halaman HTML (filter state, escape) | `…105608_9d7a` | 15 | $0,0481 | crawl 39 halaman, semua 200 |
  | fix `e3ce976` | "running" hanya untuk DRAFTING/AGENT_RUNNING | `…111834_0ac4` | 23 | $0,0418 | 0 job running (benar) |
  | 4 `a4d6cc1` | SQLite `import`/`history`, skema v1, SQL berparameter | `…113909_2235` | 5 | $0,0620 | folder dihapus, history = summary |
  | 5 `a503bdb` | login: PBKDF2, cookie HMAC 12 jam, middleware | `…121336_0231` | 14 | $0,0344 | uji serangan sandbox: semua ditolak |
  | 6 `54fd0e0` | hardening 008: cookie `Secure` default, key ≥ 32, body login ≤ 4096 (413) | `…143850_e07b` | 11 | $0,0473 | 74 tes; 17 uji serangan + data asli 38 job |
  | 7 `ae66c31` | 009: batas login gagal per alamat (429 + `Retry-After`, tanpa PBKDF2 saat diblokir) | `…145520_0b94` | 8 | $0,0338 | brute force 20 tebakan: 5 hash, 15× 429 |
  | – | 010: sesi bisa dicabut, **tidak di-merge** (logout palsu tersimpan tanpa batas; login di detik yang sama memberi nilai yang dicabut) | `…150342_8c2b` | 6+18 | $0,0575 | uji serangan: 2 gagal |
  | 9 `a72135c` | 011: trusted hosts, gzip ≥ 1000, `/jobs.csv`, API docs mati bawaan (pilot ReadDocs K7, lengan A `--web`) | `…173015_9964` | 24 | $0,0272 | 125 tes; CSV = CLI di 38 job; uji tahap 6–8 |
  | 10 `324012a` | 012: `ledger report` (tabel Markdown per stage: calls, token, attempts, `max_in/est`, biaya; dari kebutuhan RESULT batch) | `…054325_6606` | 15 | $0,0322 | 5 job asli: total $0,4910 = `spent_nano`, 236 calls, token input sama; id path/symlink ditolak; **cacat:** `Infinity`/`1e400` di token → crash (`OverflowError`) → 012b |
  | 8 `759c59c` | 010b: logout mencabut sesi valid (SHA-256), `revoke-sessions` SQLite, fail-closed | `…152604_5fde` | retry, 5 attempt | $0,0810 | 103 tes; uji tahap 6–8 + data asli |

  - Temuan dogfooding: tahap 0 kurang hitung job yang dihentikan (`usd` null di `job.json`) → tahap 1. Mode fitur drafter **tidak
    perlu**: drafter menulis tes fitur yang merah karena assertion (impor di dalam tes, CLI lewat subprocess).
  - [x] **Hardening login selesai** (tahap 6–8). Pelajaran 010: tes draf bisa menghindari kasus sulit (`_next_second()`); uji
    serangan Claude di luar tes yang menangkapnya. Issue yang mengunci format (cookie `<expiry>.<HMAC>`) ikut menyebabkan cacat
  - [x] **Context agen** (#227, jalur cepat): `ReadFile` tanpa rentang pada `.py` > 12.000 karakter memberi outline (kelas/fungsi
    + baris), berkas lain 12.000 karakter pertama; petunjuk sesudah `context_limit` juga untuk attempt yang sudah menulis. Bacaan
    010b a1 attempt 1: 135.665 → 37.767 karakter. Efek live belum diukur
  - Riwayat hardening (Atha 2026-10-28): `Secure`, panjang `secret_key`, batas body, docstring "running":
    **selesai di tahap 6** (008: draf pertama dengan blok "Why they fail now" per tes dari #225, 11 alasan terlihat; drafter 3 submit).
    Sisa, satu "go live" untuk dua job berurutan: **009** batas percobaan login per alamat (429 + `Retry-After`, tanpa PBKDF2 saat
    diblokir) dan **010** sesi yang bisa dicabut (logout mencabut di server; `revoke-sessions` lewat SQLite; format cookie tetap,
    jadi tes lama tidak berubah)
  - [ ] **Gate "tes menelan traceback" salah tolak** (draf 008 submit 2 dari 3; submit 1 karena tes yang sudah hijau diwajibkan):
    pesan tes yang **mengharapkan** exception ("must raise ValueError", kode lama tidak me-raise apa pun) dan `TypeError` di titik
    panggilan (argumen tak dikenal: tidak mungkin ada frame repo) dianggap menelan. Drafter mengakali dengan mengganti kalimat;
    satu submit terbuang. Aturan lama punya celah yang sama (jarang kena karena ekor kosong). Usul jalur ketat: catat di red check
    exception yang benar-benar di-raise di kode repo selama tes (`sys.monitoring` RAISE, Python ≥ 3.12; aturan nama untuk 3.9),
    tolak hanya bila nama di pesan = exception yang di-raise lalu tertangkap tanpa rantai
  - [ ] Tahap 3b: interaksi JavaScript + tes Playwright (image dengan Chromium; ±2–3 PR jalur ketat), bila ada kebutuhan JS
  - Ukuran: PR di-merge tanpa ditulis ulang, menit review Atha per PR, biaya per PR yang di-merge, insiden (scope, tes dilonggarkan,
    error ditelan). Bukan resolve rate.
  - [x] **Hasil review job tercatat** (jalur cepat): `argus applied <job> --commit <sha>` (→ `APPLIED`: commit, sha256 patch,
    `as_is` = patch-id commit sama dengan `changes.patch`) dan `argus reject` juga untuk paket review (→ `REJECTED` + alasan).
    `by` = user OS yang menjalankan perintah, bukan bukti persetujuan Atha (ADR-007 tetap ditunda)
- [x] **Environment `ledger_py312`** (#221, jalur ketat): Python 3.12 + FastAPI 0.143.0, httpx 0.28.1, pytest 9.1.1, wheel ber-hash
  (rilis < 2026-10-14); `check_env_image.py` PASS; satu wheel terkompilasi (`pydantic-core`, aarch64)
- [x] **Pesan error rencana draf menyebut item, panjang, dan batasnya** (#223, jalur cepat; dari `argus-ledger` tahap 4)
- [x] **Umpan balik tulis dan validasi** (#220, jalur cepat, dari dev `24562` dan Replit): stderr ditampilkan bila pytest tanpa ringkasan
  (exit 4: `ImportError` saat memuat conftest tidak pernah terlihat agen); peringatan bila `WriteFile` membuang sebagian besar berkas
  besar; cek parse Python (`compile`, tanpa eksekusi) sesudah tulis/edit `.py`
- [ ] Dari Replit, **ditunda sampai ada bukti:** ringkasan validasi untuk agen (subagen penguji versi ringan; dibuka bila sebuah run
  `context_limit` karena output validasi); tes browser dengan kode Playwright (tahap 3b `argus-ledger`: image dengan Chromium, server di
  localhost dalam sandbox, pola aksi → cek hasil melawan "Potemkin interface"). Tahap 3a memakai pola anti-Potemkin tanpa
  browser: tes mengikuti setiap link
- [x] **ReadDocs, akses web tahap 1** (#229, jalur ketat, `docs/reviews/SPEC_WEB_TOOLS.md`): halaman dokumentasi dari host persis di
  allowlist, diberikan manusia lewat `argus approve --web` (hanya env `argus`/`ledger_py312`), pengunduh di proses anak tanpa
  environment, IP dipin + TLS ke host asli, redirect dicek per hop, ledger unduhan, penolakan tanpa teks server. Review GPT,
  `/security-review` (tanpa temuan), `/code-review medium` (10 temuan diperbaiki); mutan 56/56; verify PASS (1947, sandbox 0)
  - **Pilot K7** (issue 011, dua job): A `--web` dan B tanpa web sama-sama DONE di attempt 1 dengan patch hampir identik (saling
    lulus tes, 125); **agen A tidak pernah memanggil ReadDocs** (fitur umum, model sudah tahu). A $0,0272 vs B $0,0411 (selisih dari
    drafter, 1 vs 3 submit). Manfaat belum terbukti; tunggu task dengan API langka/baru dari kebutuhan nyata, bukan dibuat-buat
  - [x] `www.starlette.io` mati, diganti `starlette.dev` (#231; tes penjaga daftar host, verify PASS 1948)
- [ ] **Mesin pencari (tahap 2)**: hanya bila ReadDocs terbukti kurang (agen tidak tahu halaman mana); spek sendiri, biaya per
  panggilan masuk ledger
- [ ] **Deep research** (sesudah web search): kerangka orchestrator → workers → synthesize → evaluator sudah ada; gate kutipan
  (klaim ↔ sumber yang benar-benar di-fetch) belum ada (gap ADR-006 non-kode)
- [ ] Email Agensi.io (marketplace skill, 2026-10-28): **nanti**. Nilai Argus ada di kode yang menegakkan jaminan, bukan di
  instruksi; bila dibuka, eksperimen dibatasi waktu
- Cara kerja (2026-10-28): **dua jalur.** Ketat (uang/ledger, crash-resume, sandbox, key, grader: spek, mutants, `verify.sh`, "merge"
  Atha) dan cepat (kemampuan agen: PR = spek, tes non-sandbox + modul sandbox terkait, Claude merge sendiri). `verify.sh` penuh
  wajib untuk jalur ketat dan **sekali sebelum setiap batch**. Run live tetap butuh "go live"; dev set: retry otomatis sekali

## Terbuka sekarang

Urutan menurut nilai (Reconciliation bagian 6); keputusan urutan berikutnya di Reconciliation bagian 7.

- [ ] **Supervisi manusia per pilot, versi ringan** (diputuskan Atha 2026-10-22; M5/M6), mulai pilot berikutnya:
  1. **jumlah titik keputusan manusia** (jawaban spesifikasi, approve, go live, merge, intervensi tak terduga), dihitung Claude dari PR dan
     alur pilot;
  2. **waktu terminal** dicatat otomatis oleh `go_live.sh` (mulai, kunci diketik, run selesai), ke log di luar repo;
  3. **menit kerja Atha opsional**: ditanya sekali di akhir pilot, satu angka kasar; "skip" dicatat `unknown`.
  Tujuannya: apakah Argus menghemat waktu manusia, bukan hanya biaya model. Pilot 3a–3b tetap `unknown`
- [ ] **Repo selain Argus** (M6): semua pilot di repo Argus. Athena butuh image sandbox per proyek; JS (bulking-app) belum bisa divalidasi
- [ ] **Pertanyaan B dari D5:** apakah ≥ 2 putaran perbaikan muat dalam satu attempt. `pilot3a5` dan `pilot3b1` tidak membutuhkannya; perlu
  task yang memang menuntut beberapa putaran
- [ ] **Eval set yang tidak jenuh** (M5): v1 16/16 hanya untuk regresi. Perluas dari kegagalan nyata (mis. 3a v1), lalu bekukan hash; eval set
  10–20 task dengan biaya per task yang lulus
- [ ] `scripts/audit_run.py` belum menyisipkan pesan `NUDGE` (balasan tanpa tool call) saat membangun ulang langkah; belum pernah terjadi di
  run live
- [x] `intake_repo.py --check <task> --repo` memberi mismatch palsu untuk record task: ditutup oleh patch agen router pilot #3
  (#189; repro git asli 7/7)
- [ ] `check_against_repo` untuk record task tidak membandingkan bit executable tes yang disetujui (baris dari patch agen #189,
  tidak diminta, tidak dites); bukan celah karena `intake.check` membandingkannya. Hapus atau tes, keputusan Atha
- [ ] Judul `PR.md` (paket review) dipotong 80 karakter di tengah kata; kosmetik
- [~] **W2b** drafter model (`docs/reviews/REVIEW_M6_W2B.md`): kode dan tes selesai, patch referensi opsional (K1). Berikutnya
  pilot **W2b-1** (ulang issue 3b di `argus_p6`, cek bocoran di preflight), lalu **W2b-2** end-to-end di task baru (spec bagian 7)
  - **W2b-1 `w2b1d1` gagal** (2026-10-22, $0,16): `SubmitDraft` terpotong di output 8.192, 6.108 di antaranya thinking; isi tes
    belum tertulis (`pilots/m6_w2b/w2b1/live/w2b1d1/RESULT.md`). Keputusan berikutnya menunggu Atha (output lebih besar, thinking
    dibatasi, atau tes lewat tool terpisah)
  - **W2b-1 `w2b1d2` gagal** ($0,22; output 16.384): submit 1 nyaris lolos (23 node merah karena assertion, satu tes gagal
    tanpa diwajibkan), lalu kirim ulang ditolak `input_limit` (45.035 > 40.000). Celah: penolakan tidak menyebut tes yang gagal di luar
    `must_pass` (`pilots/m6_w2b/w2b1/live/w2b1d2/RESULT.md`)
  - **W2b-1 `w2b1d3` berhasil** ($0,29; ReviseDraft, attempt $0,70, input 64k): `DRAFTED` dalam 2 submit. Tes drafter lulus terhadap
    `scripts/pilot_report.py` di `main` (20/20) dan menangkap 19/20 mutan referensi 3b (manusia 20/20; tanpa run BLOCKED). Draf tanpa
    `budget_profile` dan regresi longgar. W2b-1 total $0,67 untuk 3 run. Berikutnya: drafter memilih profil, lalu W2b-2
  - **W2b-2 selesai: `pr_title2` agent-completed tanpa patch referensi** (2026-10-23, PR #160): issue → drafter (3 run, $0,47) →
    approve `--no-reference` → agen (DONE, $0,08) → patch ke `main` tanpa perubahan → `verify.sh` lulus. Total $0,54, ±17 keputusan,
    5 menit Atha (`pilots/m6_w2b/w2b2/RESULT.md`). Perbaikan yang dipicu: profil wajib (#155), `edit_file` + cek tulis ulang (#157),
    batas sandbox, petunjuk, 5 submit (#158)
- [x] **W2a-ext: `changed_tests`** (`docs/reviews/SPEC_W2A_EXT_CHANGED_TESTS.md`, `acceptance/changed.py`): draf boleh mengubah tes
    lama. Tidak ada tes lama yang hilang (koleksi di sandbox) atau fungsi tes yang berubah (AST) tanpa `removed`/`modified` + alasan;
    tidak ada skip/xfail baru (kontrak `no_skip`); hanya `test_*.py`. 25 tes baru gagal di kode lama, mutan 26/26 (2026-10-23)
- [x] **Pilot W2b-3 `success_rate_all`** (2026-10-23): berhasil pada run 3 (job $0,0216, agen 1 attempt). Run 1 dan 2
    menemukan dua celah harness, ditutup oleh #179 (merah karena assertion) dan #180 (cek setup di cek draf).
    `pilots/m6_w2b/w2b3/RESULT.md`
- [ ] Drafter beberapa kali mengirim entri `changed_tests` duplikat atau kosong, dan file tes baru di `changed_tests`
    (W2b-3); penolakannya benar, tapi satu submit terbuang. Mungkin perlu contoh di prompt
- [x] **`pilot_report.py` `success_rate`**: ditambah `success_rate_all` (W2b-3)
- [ ] Drafter masih mencoba regresi yang butuh `git` (w2b2d3) walau prompt menyebut batas sandbox; satu submit terbuang
- [x] **Router v0** (`docs/reviews/SPEC_ROUTER_V0.md`, #163): `argus code` sebagai satu job (cap per job $1,00, kunci per job,
    cap tahap dicatat saat mulai, approve terikat ke sha draf); dipakai sejak router pilot #1. `--key-file`/`--yes` (#183)
- [x] **Router: waktu keputusan, perintah apply, alasan gagal di `status`** (`docs/reviews/SPEC_ROUTER_STATUS.md`, #185)
- [x] **Konteks agen dan `argus retry`** (`docs/reviews/SPEC_AGENT_CONTEXT_RETRY.md`, #188): cara attempt berhenti di feedback,
    peringatan konteks, `max_input` per model (DeepSeek 60.000), retry dengan carry. Router pilot #3: `a1` gagal
    (`context_limit` tanpa menulis), `a2` lewat retry `DONE` dalam 1 attempt; job $0,0349, 3 keputusan run
    (`pilots/router_v0/p3/RESULT.md`)
- [ ] Efek petunjuk berhenti belum terpisah dari variasi model: `context_limit` (#188, router #3 + dua instance batch 3),
    `output_truncated` (#200, batch 2 `a2` lolos tanpa butuh batas baru), `max_steps` tanpa menulis (#204, belum dipakai live);
    peringatan 70% belum pernah muncul di run live
- [ ] Router: `argus apply` (K6 v0): branch, `apply --check`, `apply`, verify; sekarang perintahnya dicetak `status`
- [ ] Cek key manual router pilot #3 (`grep -rlF -f ...`, kriteria 4) belum dijalankan; Atha, dari PC
- [x] **Pilot SWE v0** (`pilots/swe_v0/sympy__sympy-23534/`, #192–#196): repo luar pertama, `resolved` oleh tes resmi yang
    tersembunyi; job $0,0202; environment per job dengan image dipin, `swe_grade.py`
- [x] **SWE batch 1** (#198, 2026-10-24): 5/5 `resolved`, $0,1378, 6 keputusan; *oracle-informed* (`pilots/swe_v0/batch1/RESULT.md`)
- [x] **SWE batch 2** (#199): `24443` `resolved` setelah redraft, #200, dan `retry`, $0,0606; *oracle-assisted*
- [x] **Anggaran output agen** (#200, `docs/reviews/SPEC_AGENT_OUTPUT_BUDGET.md`): `max_output_tokens` per model (DeepSeek 32.000),
    petunjuk setelah `output_truncated`
- [x] **Environment dari image Python resmi** (#201/#202, `docs/reviews/SPEC_ENV_FROM_PYTHON_IMAGE.md`): `sympy_py39`
- [x] **SWE batch 3** (#203, 2026-10-27): **3/4 `resolved` tanpa bocoran** di `sympy_py39`, $0,2127, 7 keputusan; `21379` gagal
    (4 attempt tanpa menulis). `pilots/swe_v0/batch3/RESULT.md`
- [x] **Tiga celah batch 3** (#204, `docs/reviews/SPEC_AGENT_BUDGET_GAPS.md`): petunjuk setelah `max_steps` tanpa menulis, output
    drafter per model (DeepSeek 32.000), drafter melihat profil efektif coder (juga `rewrite_problems`). verify PASS (1690 passed,
    sandbox skipped 0), mutan 11/11
- [x] **Agen melihat jalur panggilan dari traceback** (#206): frame pemanggil di potongan error, baseline merah draf di attempt 1,
    `SearchFiles` per berkas
- [x] **Drafter menjaga traceback dan melihat jalur panggilan** (#208): tes yang menelan traceback ditolak, satu pertanyaan scope,
    daftar untuk manusia, `argus redraft --note` (job `human_steered`)
- [x] **Node skipped disebut, drafter 24 langkah** (#210); **langkah submit sesudah `max_steps`** (#211)
- [x] **Run ulang `21379`** (#207, #209, #212): `resolved` (1/1, 91/91), job $0,2773, seluruh run ulang $0,3288; dilaporkan terpisah.
    Agen hanya menyentuh `mod.py`, tangkapan sempit di sekitar `gcd` (`pilots/swe_v0/rerun_21379/RESULT.md`)
- [x] **SWE batch 4** (#214, `pilots/swe_v0/batch4/RESULT.md`): **3/5 `resolved`** (3/4 tanpa `23824` *harness-blocked*), tanpa bocoran,
    harness beku, $0,4260, 5 balasan Atha. `24562` gagal (agen tidak pernah menulis); `22456` d1 ditahan, redraft polos
- [x] **SWE batch 5** (`pilots/swe_v0/batch5/RESULT.md`, sympy 1.6–1.8 di `sympy_py39`, harness `aee6aef` beku): **2/5 `resolved`**
    (1/4 tanpa campur tangan; `18189` *human-steered*: d1 ditahan Atha karena tes mengunci pasangan bukan solusi, redraft `--note`
    atas izin eksplisit), $0,8746. `20428` unresolved: kontrak benar tapi tidak cukup (fix di konstruksi Poly, di luar writable).
    `20801`, `19954` gagal di agen dua kali (`max_steps` tanpa menulis, `context_limit`; #227 tidak mencegahnya); `19954` a1
    FAILED_BUDGET (token 0,8% di atas perkiraan). Gate menelan traceback: 1 tolak yang wajar, 0 salah tolak
- [x] **`EditFile` untuk berkas besar** (jalur cepat, dari identifikasi batch 5): `EditFile` membaca dengan batas 100.000 byte dan
    menolak `numbers.py`, `perm_groups.py`, `polytools.py`; 9 job SWE sejak 2026-10-24 (`21379` batch 3, `24562` batch 4 + dev set,
    `20801`/`19954` batch 5). Sekarang sampai 2 MB (`EDIT_MAX_FILE`). Diagnosis lama "agen tidak pernah menulis" dikoreksi di RESULT
- [x] **Dev set 2** sesudah perbaikan `EditFile` (`pilots/swe_v0/dev2/RESULT.md`, bukan klaim): `20801`, `19954`, `24562` **3/3
    `resolved`**, masing-masing 1 attempt, 3–7 langkah, $0,0615 total; patch setara dengan upstream
- [x] **Batas kerja `SearchFiles`** (jalur cepat, dari audit batas tool 2026-10-29): 500 berkas / 2 MB per pencarian berhenti di
    209 pencarian SWE (124 "No matches in the files searched"), berkas > 256 KB dilewati; sekarang 5.000 berkas / 64 MB, berkas
    sampai 2 MB (`= READ_MAX_FILE`); seluruh sympy ±1 s. Batas output (20 baris, 200 karakter) tidak berubah
- [x] **Counter heuristik menghitung reasoning yang dikirim** (jalur ketat, `docs/reviews/SPEC_ESTIMATE_REASONING.md`, PR #240;
    dari kandidat (c)): `reasoning_content` yang dikirim balik ke DeepSeek tidak dihitung, tagihan sampai 1,91× est di margin 2,5;
    dihitung, 0 dari 2.006 panggilan lewat. Margin DeepSeek 1,5, batas agen 150.000 / drafter 250.000 est, `estimate misses`
    di `status`. Audit: 0 USD lewat cap, 2 reservasi token lewat (dua FAILED_BUDGET, sekarang harness-affected). Merged #240
- [x] **Harga peak di batas jendela** (jalur ketat, `docs/reviews/SPEC_PEAK_EDGES.md`, PR #241): worst case sebelum kirim
    selalu ×peak (0 dari 1.182 panggilan agen dan 0 dari 837 drafter akan terhambat), biaya ledger = pengali tertinggi
    antara mulai dan selesai (field `peak`), baris peringatan peak di layar konfirmasi router. Mutants 14/14 + 9/9 (review),
    verify.sh PASS d6be15b. Merged #241
- [~] **Stage riset r1, Alur A → B** (jalur ketat, `docs/reviews/SPEC_RESEARCH_STAGE.md`, PR #242): `argus code --research`,
    tool baca-saja + ReadDocs, `SubmitHandoff` dengan gate harness (URL diambil di run, kutipan persis di halaman, versi
    terpasang), `INSUFFICIENT_EVIDENCE` sebagai hasil, `research-ok` sebelum drafter. Mutants 24/24. Menunggu review,
    `verify.sh`, "merge"; lalu pilot dua lengan issue 013 (argus-ledger, host www: 307 bukan 400), butuh "go live"
- [ ] **Sesudah batch 5 (kandidat, belum diputuskan):** (b) drafter: cari titik nilai salah
    pertama kali muncul, bukan hanya gejala di issue (`20428`); (c) → spek counter reasoning (#240)
- [x] **Jalur cepat #1** (#215): `ReadFile` per rentang baris (berkas > 100 KB tidak lagi ditolak), `ListFiles` per direktori dan maks
    300, issue 8.000 karakter, `max_steps` agen 30 (override router); audit run lama tetap memakai skema tool versi 1
- [x] **Timeout validasi router 120 s** (#216; 261 validasi: p99 59 s, maks 66 s)
- [x] **Margin input heuristik per model** (#217, `docs/reviews/SPEC_HEURISTIC_INPUT_MARGIN.md`): DeepSeek 2,5 (950 panggilan, tagihan
    sampai 1,77× perkiraan), batas input diskalakan, plafon `large_usd` 1,2 juta token (override router; eval tidak berubah)
- [x] **Dev set 1** (#218, `pilots/swe_v0/dev1/RESULT.md`, bukan klaim): `23824` dan `21379` `resolved`; `24562` gagal karena mutu patch
    (`numbers.py` rusak saat import), retry dihentikan Atha. $0,4968
- [x] **Blok "Why they fail now" per tes dari red check** (#225, jalur ketat, `docs/reviews/SPEC_RED_TESTS_PER_NODE.md`): ekor
    2.000 karakter di argus-ledger tahap 2–3a tidak memuat satu pun seksi kegagalan (19 tes merah), jadi blok review kosong dan gate
    "tes menelan traceback" **tidak menilai apa pun** (fail-open). Red check sekarang mencatat per tes pesan, nama exception dari
    kata-kata tes sendiri, dan berkas repo di traceback beserta rantainya; gate dinilai per tes, fail-closed. Review sesi sebelah dan
    `/code-review medium` (9 temuan, mis. `DID NOT RAISE` dan penjelasan `assert` pytest dihitung sebagai exception) ditutup.
    Mutan 27/27, `verify.sh` PASS (1797 passed, sandbox skipped 0)
- [ ] Jalur cepat berikutnya: `estimate_miss` per run di `status` (H3 spek margin); `swe_grade.py`
    mencatat nama tes draf yang gagal di atas patch maintainer; tes lama yang diubah drafter otomatis wajib (`22456` d1).
    (Exit code 4 sudah: #220 menampilkan stderr.)
- [x] **`verify.sh` penuh sesudah #220–#223**: lulus di #225 (`69df7b2`, 1797 passed, sandbox skipped 0); tetap wajib sebelum
    batch berikutnya bila ada PR jalur cepat sesudahnya
- [ ] Kandidat sisa dari 21379: gerbang writable glob/lebar vs regresi sempit (dev set `21379`: writable 4 berkas di 3 paket);
    drafter membaca sampai dipaksa berhenti
- [ ] Langkah submit (#211) dan pertanyaan scope (#208) belum pernah terpakai di run live
- [ ] Approve tanpa oracle lebih lama (batch 3: ±5–7 menit per draf, batch 1 median 45 detik); bila batch 4 sama, pertimbangkan
    ringkasan yang membantu menilai isi tes tanpa patch maintainer
- [ ] Layar batas tahap drafter (`code`, `redraft`, resume) dan layar `retry`/resume agen tidak menyebut environment dan image;
    prioritas rendah (Atha 2026-10-24: yang membaca layar adalah Claude, dan preflight chat menghitung id image dengan
    `environment_pin` sebelum run)
- [ ] Router: cek bentuk kunci DeepSeek (hanya Anthropic yang dicek prefiksnya); ditunda, Atha tidak lagi mengetik kunci
- [ ] `argus research` **ditunda** (K1 router v0): dibuat bersama Alur A yang menerima prompt bebas; saat itu bentuk job dan ledger
    diseragamkan
- [ ] **D4** batas ListFiles + daftar berkas di issue: **ditunda** (2026-10-22); dibuka bila ada task yang kehabisan anggaran dengan caching
  menyala
- Pengamatan, belum tindakan: di `pilot3b1` agen memanggil `RunValidation` di balasan yang sama dengan tulisannya, sebelum validasi otomatis
  jalan (validasi dijalankan dua kali, ±9 detik). Prompt sistem sengaja tidak menyebut validasi otomatis (D3 K4). Satu pengamatan

## Selesai, belum masuk arsip

- [x] **Pilot `argus_self_3`** (2026-10-17, PR #72; `pilots/argus_self_contract/README.md`, validasi `must_pass`, $0.1797): gagal jujur,
  workspace tidak berubah. Thinking memakai **100%** output di langkah ketiga (4.096 dan 2.954), tanpa tool call; batas output terkunci
  oleh sisa reservasi attempt (±4,5 ribu setelah input 15 ribu). Keputusan yang dibukanya ("profil task besar, batasi thinking, atau
  berhenti") terjawab oleh pekerjaan sesudahnya: profil `large` (M6 W5, keluaran 8.192) dan `large_usd` (D1)

## Pekerjaan operasional (Atha, di luar repo)

- [ ] Cabut kunci API yang dipakai untuk pilot 3a v2, D5, dan 3b di dashboard provider
- [ ] Bersihkan sisa kunci di riwayat shell dan berkas env di VM; hapus SSH key tambahan yang tidak dipakai lagi
- [ ] Deploy harness sebagai service (systemd): operasional, **bukan** M9

## Parking lot (roadmap `docs/FUTURE_ARCHITECTURE.md`)

Ditunda sampai ada bukti kebutuhan; status dan gap di Reconciliation bagian 1–2.

- [ ] M4 penjadwalan multi-agent dengan dependensi
- [ ] M5 sisanya: tracing/dashboard, benchmark single vs multi-agent, model kandidat worker (Haiku 5.5 vs DeepSeek) per biaya task yang lulus
- [ ] M7 registry kapabilitas dan policy (ADR-001), layanan approval di kode (ADR-007), adapter MCP
- [ ] M8 penemuan tool dan memori prosedural (ADR-003)
- [ ] M9 deployment terkendali
- [ ] Idempotency key sisi provider (ADR-004)
- [ ] Artifact store dengan versioning (ADR-005)
- [ ] Capability pack gambar, video/audio, game, dengan gate non-kode (ADR-006)
- [ ] **Git untuk agen otonom** (diskusi 2026-10-24): sandbox **tetap tanpa git** (tanpa history yang bisa membocorkan perbaikan,
  digest workspace tetap jelas, tidak ada kredensial atau `.git` untuk menyelundupkan perubahan). Git ditambah sebagai tool
  **harness**, bertahap, saat ada bukti kebutuhan:
  1. history read-only (`GitLog`/`GitShow`/`GitBlame`, sampai `base_commit`, dibatasi, tercatat);
  2. repo sintetis satu commit di sandbox (tanpa history, tanpa remote), per environment, untuk repo yang build atau tesnya
     butuh git (`setuptools_scm`, tes yang memanggil git); `.git` keluar dari snapshot dan scope, dengan spek dan mutan;
  3. branch/commit/push/PR hanya dari harness: idempoten per `(job, tahap)`, tercatat, push dan PR butuh persetujuan,
     kredensial tidak pernah masuk sandbox (lanjutan `argus apply`, K6)

## Batasan yang diterima

- `budget.max_seconds` hanya soft limit di graf riset; **code task tidak punya batas waktu dinding** (`DESIGN_AUTO_VALIDATION.md`)
- Tarif konteks panjang Haiku 5.5 (> 100.000 token) tidak dimodelkan; role Haiku yang panggilannya bisa melewatinya ditolak (`ConfigError`)
- Prompt caching hanya Anthropic, TTL 5 menit, mati bawaan; bukan untuk Haiku 5.5 (D5)
- Empat skrip eksperimen lama (`analyze_series.py`, `sim_admission.py`, `dry_feedback.py`, `measure_context.py`) masih membaca log dengan
  `json.loads` per baris; diarsipkan apa adanya (pilot 3 spesifikasi bagian 2)
