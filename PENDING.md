# Pending

Daftar kerja Argus yang **masih terbuka**. Status milestone dan ADR beserta buktinya ada di [`docs/Reconciliation.md`](docs/Reconciliation.md)
(satu-satunya tempat status); riwayat semua butir yang sudah selesai (bukti, angka, PR) ada di
[`docs/reviews/PENDING_ARCHIVE_2026-10-22.md`](docs/reviews/PENDING_ARCHIVE_2026-10-22.md) dan `docs/reviews/`.

Terakhir diperbarui: 2026-10-28 (run ulang 21379 `resolved`, #206–#212; batch 4 preflight).

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
- [ ] **SWE batch 4** (`pilots/swe_v0/batch4/PREFLIGHT.md`): lima instance sympy (`24562`, `24066`, `23824`, `22456`, `23262`),
    environment `sympy` (3.12), tanpa bocoran, **harness tidak diubah selama batch**, izin di muka 1 redraft + 1 retry per instance.
    Menunggu "go live". SWE-rebench ditunda (Atha 2026-10-28: beban environment per repo)
- [ ] Kandidat spek sesudah batch 4 (dari 21379): `ReadFile` per rentang baris (agen `a1` habis konteks membaca 3 berkas besar utuh;
    K4 #206); gerbang writable glob/lebar vs regresi sempit (catatan Atha: `sympy/core/*.py` dijaga 16 tes); drafter membaca sampai
    dipaksa berhenti (16/16/24/23 langkah)
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
