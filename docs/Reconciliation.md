# Rekonsiliasi: `FUTURE_ARCHITECTURE.md` terhadap kode (2026-10-27)

Status: **laporan terkini; satu-satunya tempat status milestone dan ADR.** Basis: `main` `7fd5130` (#204). Status di bawah berasal dari kode
(dicek langsung bila ditandai *dicek*), dari bukti di `verification/` dan `pilots/`, dan dari review di `docs/reviews/`. Laporan sebelumnya
diarsipkan: [`reviews/RECONCILIATION_2026-10-24.md`](reviews/RECONCILIATION_2026-10-24.md),
[`reviews/RECONCILIATION_2026-10-22.md`](reviews/RECONCILIATION_2026-10-22.md) dan
[`reviews/RECONCILIATION_2026-10-21.md`](reviews/RECONCILIATION_2026-10-21.md); keputusannya tetap berlaku. Daftar kerja ada di
[`PENDING.md`](../PENDING.md).

Yang berubah sejak 2026-10-24: **tiga batch SWE sympy** (10 instance lagi, bagian 4b), batch 3 yang pertama **tanpa bocoran
jawaban** (approve hanya dari isi draf; batch 1, 2, dan `23534` ditandai oracle-informed/oracle-assisted, review Atha 2026-10-27);
**environment dari image Python resmi** (`sympy_py39`, Python 3.9.25, #201/#202); **anggaran output per model** untuk agen (#200,
DeepSeek 32.000, plus petunjuk setelah `output_truncated`) dan untuk drafter (#204); petunjuk setelah `max_steps` tanpa menulis dan
profil efektif untuk drafter (#204). Perubahan sebelumnya (router v0, DeepSeek bawaan, environment per job, SWE v0) di arsip 2026-10-24.

**Tambahan 2026-10-28 sore:** batch 4 **3/5** tanpa bocoran (#214); alat baca agen (#215: `ReadFile` per rentang baris, `ListFiles`
dibatasi, issue 8.000, `max_steps` 30), timeout validasi 120 s (#216), margin input heuristik per model (#217); dev set 1 (#218):
dua instance yang dulu tidak pernah menulis sekarang `resolved`. **Arah baru** (bagian 7): coding agent untuk production, SWE-bench
jadi alat regresi.

Legenda: `[x]` selesai dan terbukti · `[~]` sebagian (ada untuk jalur tertentu, sisanya belum) · `[ ]` belum dimulai.

## 1. Milestone

| Milestone | Status | Bukti | Gap yang belum tertutup |
|---|---|---|---|
| M1–M2 harness, LLM nyata, sandbox | `[x]` | `harness/`, `tools/sandbox.py`; arsip `PENDING` | – |
| M3 evaluasi | `[x]` | `docs/reviews/M3_CLOSING.md`; kalibrasi judge PASS | – |
| General-task agent (dulu "M4 slice 1") | `[x]` | `codetask/`, `acceptance/`; Eval Set v1 16/16 | Eval Set v1 jenuh: regresi saja, bukan ukuran kemampuan |
| **M4** multi-agent paralel dengan dependensi | `[ ]` | Graf riset (M1–M2) punya worker paralel lewat fan-out tanpa dependensi (`graph.py`); code task satu agen | Penjadwal dengan dependensi, batas sumber daya, multi-agent untuk code task. Belum ada bukti single-agent menjadi penghalang |
| **M5** observability dan benchmark | `[~]` | Ledger per panggilan; `audit_run.py` (juga membangun ulang feedback berhenti, peringatan konteks, dan carry retry), `failure_trace.py`, `pilot_report.py` (`success_rate` dan `success_rate_all`); **log keputusan manusia dengan waktunya di `job.json`** (`limits_shown`, `confirmed`/`confirmed_by_flag`, `key_typed`/`key_from_file`, `approved`, `retry`; #185); penilai ala SWE-bench `scripts/swe_grade.py`; waktu ringkasan → "y" per draf (`review_times.txt`, batch 1–3) | Tracing/dashboard (*dicek*: tidak ada Langfuse/LangSmith/OTel); benchmark single vs multi; **menit kerja Atha** masih belum ditanyakan (yang terukur: jumlah keputusan, waktu mesin, waktu ringkasan → "y"); **eval set yang tidak jenuh**: 11 instance SWE sympy sudah dinilai, tapi terkontaminasi dan hanya 4 tanpa bocoran (bagian 4b) |
| **M6** repo → PR | `[x]` MVP | W0–W5; 10 run live pilot (bagian 4a); drafter model live (W2b-1/2/3); router (bagian 4b); **repo selain Argus**: sympy, 11 instance dinilai, **3/4 `resolved` tanpa bocoran** (batch 3) dan 7/7 dengan bocoran (bagian 4b) | Tingkat sukses umum: belum ada (sampel tanpa bocoran 4); PR tetap dibuka manusia (disengaja); `argus apply` belum ada (perintahnya dicetak `status`); pertanyaan B D5 (≥ 2 putaran perbaikan dalam satu attempt) belum terjawab |
| M7 registry dan policy, MCP | `[ ]` | – | Seluruhnya (ADR-001, sebagian ADR-007). Kandidat slice terkecil bila dibutuhkan: pencatatan keputusan policy (bagian 2, ADR-007) |
| M8 penemuan tool, memori prosedural | `[ ]` | – | Seluruhnya (ADR-003) |
| M9 deployment terkendali | `[~]` (staging) | **Staging v0** (#244): `argus stage deploy\|rollback\|status`, hanya commit job `APPLIED` apa adanya, container tanpa jaringan/read-only/tanpa capability/non-root di Unix socket, isolasi dicek `docker inspect`, smoke dari host, rollback dites; **upgrade dependency v0** (#246): rilis = commit di satu runtime dengan image tercatat, `argus stage check` sebelum runtime baru, rollback antar image; **hardening** (#249). Pilot: staging #1 (deploy/deploy/rollback/deploy, #245), upgrade #1 (check → up1 → rollback ke image v0 → up1, satu "go live", #248) | Production sungguhan (DNS/TLS, pengguna, kredensial, jaringan) belum ada dan butuh persetujuan terpisah Atha; data staging sintetis; satu aplikasi (argus-ledger); tidak ada monitoring setelah deploy selain smoke |
| Capability pack (gambar, video/audio, game) | `[ ]` | – | Seluruhnya; gate non-kode ADR-006 |

M4, M7, M8, M9, dan capability pack tetap **ditunda sampai ada bukti kebutuhan** (keputusan 2026-10-21, ditegaskan 2026-10-24: tidak
ditutup lewat dokumen). Belum ada pilot yang tertahan karena tidak ada registry, policy engine, memori, atau multi-agent.

## 2. ADR

| ADR | Status | Yang ada di kode (code task kecuali disebut) | Gap |
|---|---|---|---|
| 001 registry dan policy | `[ ]` | Allowlist tool per role di config + `tools` kontrak yang hanya boleh menambah, dibekukan per run; versi tool dan image (termasuk image environment) masuk kunci memo | Registry formal (id/versi, schema, biaya, izin, trust, provenance), policy engine. Target M7 |
| 002 workflow bertipe | `[~]` (kuat) | State machine code task (`codetask/status.py`) dan **job router** (`router/job.py`, transisi legal); draf task bertipe dicek deterministik (W2a); **drafter model live**: setiap submit dicek harness (red karena assertion #179, cek setup yang sama di cek draf #180); draf model lolos dan dipakai di W2b-2, W2b-3, router #1–#3, SWE v0; di SWE v0 tes drafter **lulus 4/4 di atas patch resmi maintainer**; di batch 3 (tanpa bocoran) keempat draf yang di-approve hijau di atas patch maintainer (dibuka setelah grading); drafter melihat profil **efektif** coder (#204) | Planner dinamis; task dengan dependensi eksplisit; draf yang salah paham issue tanpa oracle baru tertangkap setelah grading (belum terjadi di batch 3) |
| 003 memori berlapis | `[ ]` | Hanya state eksekusi (checkpoint, memo) | Knowledge dan project memory. Target M8 |
| 004 durable, idempotensi, budget | `[~]` (kuat) | Reservasi sebelum kirim, ledger, `durability="sync"`, memo per langkah, crash-resume, `reservation_from_ledger`; D1/D5; **cap per job** yang dihitung dari ledger semua tahap, cap tahap dicatat saat mulai dan tidak dihitung ulang saat resume; kunci per job (`flock`); `retry` membuat tahap baru dengan cap dari sisa job; `max_input_tokens` per model (DeepSeek 60.000, Sonnet 40.000); `max_output_tokens` per model untuk agen (#200) dan drafter (#204) (DeepSeek 32.000), `max_tokens` tiap panggilan = min(batas, yang muat di sisa reservasi); perkiraan token heuristik **tidak** dipangkas (est/tagihan DeepSeek minimum 0,89) | **Idempotency key sisi provider** (tidak ada). Cap USD untuk model non-Anthropic bertumpu pada perkiraan token heuristik, jadi bukan batas mutlak (`FAILED_BUDGET` dapat sedikit melewati cap) |
| 005 artifact dan workspace | `[~]` | Workspace per run (path jail, scope, digest); intake commit persis tanpa `.git` (dites: commit yang lebih baru tidak terlihat); paket review; **environment per job dengan id image yang dipin** di `job.json`, image berubah = tahap ditolak; build image deterministik per rootfs (`build_env_sandbox_image.sh`); **environment dari image Python resmi** dipin digest dengan requirements ber-hash dan cek environment wajib sebelum dipakai (`sympy_py39`, #202); `ledger_py312`, `ledger_staging` dan upgrade `*_up1` (#246); **rilis staging** = `git archive` commit applied (dicek terhadap tree), read-only, dengan runtime dan image tercatat | Artifact store terpisah (tidak ada); id image tidak bisa direproduksi (hanya rootfs), jadi job tidak bisa dilanjutkan setelah image dibangun ulang (disengaja, K1 SPEC_SWE_PILOT); data instance SWE di luar repo (`~/swe`) tidak di-versioning (sha-nya di `grade.json`) |
| 006 quality gate | `[~]` (kuat untuk kode) | Kontrak beku, validasi di sandbox, verdict dengan bukti, klaim dicek, validasi ulang independen; cek draf; **penilai luar dengan tes tersembunyi** (`swe_grade.py`: patch harus sha paket review, berkas tes resmi dikembalikan lalu `test_patch` diterapkan, hasil per node, `missing` = tidak lulus, hasil yang tidak sah ditolak) | Gate non-kode. Penilai SWE milik Argus (Python 3.12), bukan harness resmi |
| 007 keamanan dan approval | `[~]` | Sandbox Docker (tanpa jaringan, read-only, non-root, tanpa capability; dites bahwa host dan `.git` tidak terlihat); output sandbox berlabel data; **key dari file 0600 di luar repo** (`--key-file`, isinya tidak pernah ditampilkan atau ditulis); teks yang dicetak dibersihkan dari karakter kontrol | **Approval run pindah ke chat:** dengan `--yes` (hanya bersama `--key-file`), `[y/N]` tidak ditanyakan dan gerbang `go_live.sh` per pilot tidak dipakai lagi. Yang tersisa di kode: layar batas tetap dicetak dan dicatat (`confirmed_by_flag`), approve terikat ke sha draf, image dan kontrak terikat ke job. Persetujuan "go live"/"y" Atha hanya tercatat di riwayat chat, tidak di `job.json`. Layanan approval dan policy engine di kode tetap tidak ada. Kandidat slice M7 terkecil: mencatat siapa menyetujui apa (teks persetujuan) di log job. **Staging:** satu "go live" per `PLAN.md` yang ter-commit (U4, SPEC_DEP_UPGRADE_V0), berhenti di langkah pertama yang meleset; tetap hanya di chat |

## 3. Kriteria MVP M6 (`FUTURE_ARCHITECTURE.md` bagian 6)

| Kriteria | Status | Bukti |
|---|---|---|
| Issue dan repo target ber-scope | ✓ | kontrak, intake W4; repo luar (sympy, 11 instance) di commit persis |
| Rencana bertipe dan kriteria eksplisit | ✓ | drafter model live (W2b, router, SWE v0), dicek harness dan di-approve manusia terikat sha |
| Baca/tulis terbatas workspace | ✓ | path jail, scope tulis, protected |
| Kode dan tes terisolasi | ✓ | sandbox Docker; environment per job (`argus`, `sympy`, `sympy_py39`) |
| Batas biaya per task dan per run | ✓ | reservasi attempt, cap run, **cap per job** |
| Simpan state dan resume | ✓ | checkpoint `sync`, memo, tes crash lintas proses; `argus resume` |
| Tanpa panggilan berbayar ganda bila bisa direkonsiliasi | ✓ | memo per langkah, `reservation_from_ledger`; idempotency key provider tidak ada |
| Artefak, diff, log, provenance | ✓ | run dir, ledger, paket review, `job.json` |
| Tolak tool dan akses di luar scope | ✓ | allowlist, scope, sandbox tanpa jaringan |
| Lulus/gagal per kriteria dengan bukti | ✓ | verdict, `status` (`why:`, attempt per tahap) |
| Diff/PR yang bisa direview, tanpa merge otomatis | ✓ | paket review; PR dibuka manusia; merge hanya atas perintah Atha |
| Tes deterministik untuk mode kegagalan | ✓ | W0, suite code task dan router (model palsu) |

## 4a. Pilot M6 sampai 2026-10-22 (repo Argus, Sonnet 5.5)

10 run live di 6 task (pilot 1, 2, 3a, 3b, 4, 5), 6 task `agent-completed`, **$1,29** total. Rinciannya di arsip
[`reviews/RECONCILIATION_2026-10-22.md`](reviews/RECONCILIATION_2026-10-22.md) bagian 4.

## 4b. Pilot sejak 2026-10-22 (drafter, router, repo luar)

| Pilot | Task | Model | Hasil | Biaya job | Catatan |
|---|---|---|---|---|---|
| W2b-2 | `pr_title2` | Sonnet 5.5 | `agent-completed` tanpa patch referensi | $0,5429 | drafter 3 run |
| Router #1 | `argus list` | DeepSeek | `REVIEW_READY`, patch diterapkan | $0,0792 | 4 PR perbaikan harness di tengah job |
| Router #2 | sama, thinking | DeepSeek thinking | `REVIEW_READY` | $0,0696 | 2 perintah live, 8 menit |
| W2b-3 | `success_rate_all` (mengubah tes lama) | DeepSeek thinking | run 3 `REVIEW_READY`, patch diterapkan | $0,0355 + $0,0156 + $0,0216 | run 1–2 menemukan dua celah harness (#179, #180) |
| Router #3 | `intake_repo --check` record task | DeepSeek thinking | `a1` gagal (`context_limit` tanpa menulis), **`retry` `a2` `DONE`**, patch diterapkan (#189) | $0,0349 | pemicu #188 (konteks agen, retry); 3 keputusan run |
| **SWE v0** | `sympy__sympy-23534` (repo sympy) | DeepSeek thinking | **`resolved`** (`FAIL_TO_PASS` 1/1, `PASS_TO_PASS` 11/11) | **$0,0202** | patch agen identik dengan patch maintainer; 2 keputusan run; *oracle-informed* |
| SWE batch 1 | 5 instance sympy (Python 3.12) | DeepSeek thinking | **5/5 `resolved`** (satu, `22914`, dengan usulan kode di issue) | $0,1378 | 6 keputusan; 2 patch berbeda dari maintainer; *oracle-informed* (hasil tes drafter di atas patch maintainer terlihat sebelum approve) |
| SWE batch 2 | `24443` (Python 3.12) | DeepSeek thinking | `resolved` setelah redraft, #200, dan `retry` | $0,0606 | `a1` gagal `output_truncated` (thinking memakai seluruh 8.192); *oracle-assisted* (`d1` ditolak karena gagal di atas patch maintainer) |
| **SWE batch 3** | 4 instance sympy, **`sympy_py39`** | DeepSeek thinking | **3/4 `resolved` tanpa bocoran** | $0,2127 | 7 keputusan; `21847`, `21612` lolos di attempt 2 berkat feedback #188; **`21379` gagal**: 4 attempt tanpa menulis (`max_steps` ×2, `context_limit` ×2); `21612` `d1` drafter `output_truncated`; pemicu #204 |

SWE sympy sejauh ini: **11 instance, $0,4313**. Hasil **tidak dicampur**: tanpa bocoran 3/4 (batch 3); dengan bocoran 7/7
(`23534`, batch 1, batch 2). Ringkasan per batch: `pilots/swe_v0/batch{1,2,3}/RESULT.md`.

**Terbukti (sampel kecil, bukan tingkat sukses):** alur penuh berjalan tanpa PC (VM, `--key-file`/`--yes`), dengan 2–3 keputusan
manusia per task (dulu ±17 di W2b-2); satu "go live" per batch; drafter model menulis tes yang dipakai, dan tanpa oracle keempat draf
batch 3 yang di-approve hijau di atas patch maintainer; task di repositori luar dinilai `resolved` oleh tes resmi yang tidak terlihat,
di dua environment (Python 3.12 dan 3.9); biaya per task yang selesai $0,02–0,09 di DeepSeek; **feedback #188 menyelamatkan dua
instance** batch 3 (attempt 1 `context_limit` tanpa menulis → attempt 2 selesai).

**Batas klaim SWE:** "harness Argus menyelesaikan task SWE-bench dari ujung ke ujung", **bukan** kemampuan model pada bug yang belum
pernah dilihat. Instance SWE-bench Verified publik 2021–2023 dan kemungkinan ada di data latih (sebagian patch agen identik dengan
patch maintainer). Penilaian ala SWE-bench (penilai milik Argus), **tidak** dibandingkan dengan leaderboard.

**Supervisi:** tanpa hasil patch maintainer, waktu ringkasan → "y" naik dari median 45 detik (batch 1) ke ±5–7 menit (batch 3): Atha
menilai isi tes sendiri. Itu biaya nyata dari approve tanpa oracle.

**Belum terbukti:** tingkat sukses umum (tanpa bocoran baru 4 instance); ≥ 2 putaran perbaikan dalam satu attempt; menit kerja
manusia; **efek tiga petunjuk berhenti** (`context_limit` #188, `output_truncated` #200, `max_steps` tanpa menulis #204) terpisah dari
variasi model; petunjuk #204 dan output drafter 32.000 belum pernah dipakai di run live; peringatan konteks 70% belum pernah muncul.

## 5. Mode kegagalan (`FUTURE_ARCHITECTURE.md` bagian 8)

| Mode | Status | Bukti / gap |
|---|---|---|
| Crash sebelum/sesudah request | ✓ | ledger, `unknown_after_crash`, tes crash lintas proses; `argus resume` |
| Timeout, rate limit, hasil berbayar ambigu | ✓ | retry transien, tagih kasus terburuk; tanpa idempotency key provider |
| Konflik/overrun budget | ✓ | reservasi sebelum kirim, `FAILED_BUDGET` durable; cap per job; dua perintah pada satu job ditolak (`flock`) |
| Workflow tidak valid atau siklik | ~ | transisi legal job dan code task; tidak ada workflow dengan dependensi |
| Perubahan schema/versi tool | ~ | versi tool dan image di kunci memo; image environment dipin per job; tanpa registry |
| Dokumen berbahaya, prompt injection | ~ | output sandbox berlabel data; teks yang dicetak dibersihkan dari karakter kontrol/ANSI; belum diukur untuk code task |
| Lolos sandbox, jaringan tak sah | ✓ | hardening Docker diuji; host dan `.git` tidak terlihat dari dalam (dites) |
| Artefak hilang/rusak | ~ | log rusak ditoleransi, cek intake dan digest; tanpa artifact store |
| Memori/prosedur basi | n/a | belum ada memori |
| Evaluator berselisih / verdict rusak | ✓ | judge gagal tertutup; penilai SWE menolak hasil yang tidak sah alih-alih mencatatnya sebagai gagal |
| Retry loop / planner berosilasi | ✓ | aturan stagnan, `max_iterations`, `max_steps`; `retry` hanya atas perintah manusia |
| Agen membaca tanpa menulis sampai konteks habis | ~ | feedback antar attempt dan carry (#188); **penyebab utamanya alat baca** (`read_file` menolak berkas > 100 KB, `list_files` ±25k token): sesudah #215, `21379` dan `23824` selesai dalam 5–14 langkah (dev set 1). `24562` kini menulis tapi merusak berkasnya (mutu patch) |
| Thinking menghabiskan output | ~ | balasan terpotong tidak dijalankan; output per model dan petunjuk untuk agen (#200) dan drafter (#204); `a2` batch 2 lolos, tapi bukan karena batas baru (balasan terbesar 5.519) |
| Approval dicabut / parameter berubah | ~ | approve terikat sha draf, kontrak dan image terikat job; persetujuan run di chat tidak tercatat di job (ADR-007) |
| Tulis bersamaan ke berkas proyek | ✗ | satu agen per workspace; satu perintah per job |

## 6. Gap terbuka, diurutkan menurut nilai sekarang

1. **Task fitur di aplikasi nyata** (arah 2026-10-28): `argus-ledger` tahap 0–9 selesai, **11 task di `main`, $0,5366** (agen 9/11 di attempt
   pertama; 010 tidak di-merge karena uji serangan menemukan 2 cacat yang lolos dari tesnya; 010b lewat retry sesudah 4
   `context_limit`, ditangani #227) (CLI, biaya dari ledger, API FastAPI di environment baru `ledger_py312` #221, halaman HTML, SQLite, login, hardening
   login), semuanya dicek di data ledger asli; login dan hardening juga dengan uji serangan. Satu kegagalan drafter karena pesan
   error harness (#223). Dogfooding juga menemukan celah gate: ekor output yang tidak memuat satu pun tes membuat cek "tes
   menelan traceback" lolos tanpa menilai (#225). Mode fitur drafter tidak perlu. ReadDocs (akses web tahap 1, #229) di `main`; pilot
   K7 (tahap 9): agen tidak memakainya pada fitur yang umum, manfaat belum terbukti. Berikutnya: JS + Playwright (3b) bila perlu;
   mesin pencari hanya bila ReadDocs terbukti kurang. Issue 001–011 ditulis Claude atas delegasi; argus-ledger jalur cepat.
2. **Tingkat sukses di repo luar tanpa bocoran** (M6, M5): batch 3 3/4, batch 4 3/5, batch 5 2/5 (1/4 tanpa campur tangan;
   sympy 1.6–1.8). Sekarang alat regresi (±20% usaha), bukan tujuan. Batch 5: dua kegagalan agen (`max_steps`/`context_limit` di
   berkas besar, #227 tidak mencegahnya) dan satu kontrak yang terlalu sempit.
3. **Efek petunjuk #204** (`max_steps` tanpa menulis) dan output drafter 32.000: ada di kode, belum di run live.
4. **Eval set yang tidak jenuh** (M5): instance SWE sebagai eval regresi harness; bukan ukuran model selama terkontaminasi.
5. **Menit kerja manusia** (M5): jumlah keputusan, waktu mesin, dan waktu ringkasan → "y" terukur; menit Atha belum ditanyakan.
6. **Persetujuan run di chat tidak tercatat di job** (ADR-007): ditunda sampai ada aksi berisiko di dalam run (bagian 7).
7. **Pertanyaan B D5** (≥ 2 putaran perbaikan dalam satu attempt).
8. **`argus apply`** (K6 router v0): belum ada bukti kebutuhan (apply 4 baris dari `status`).
9. **Idempotency key provider** (ADR-004): dampak rendah selama tidak ada aksi eksternal selain panggilan model.
10. **M4, M7, M8, M9, capability pack**: ditunda sampai ada bukti kebutuhan. Web search dan deep research bukan bagian capability
   pack (gambar, video/audio, game); keduanya kandidat sesudah tahap awal `argus-ledger` (bagian 7).

Kecil, dicatat di `PENDING.md`: layar batas tahap drafter tidak menyebut environment dan image (preflight chat menghitungnya dengan
fungsi yang sama); baris bit executable dari patch agen #189; cek key manual router #3.

## 7. Keputusan yang diminta

1. **Batch 4** (usul di `PENDING.md`), sesudah spek `docs/reviews/SPEC_LOCATE_FROM_TRACEBACK.md` (#206, dari penelusuran `21379`): lima instance sympy yang layak di Python 3.12 tetapi tidak dipilih di batch 1 (`24562`,
   `24066`, `23824`, `22456`, `23262`), tanpa bocoran seperti batch 3, di `main` dengan #204; `21379` diulang sebagai job baru dan
   dilaporkan terpisah (instance yang sudah gagal, dipilih ulang).
Diputuskan 2026-10-27 (Atha): gap 5 (mencatat persetujuan chat di job, ADR-007) **ditunda**; dibuka bersama aksi berisiko di dalam
run (`argus apply`, git push/PR). Catatan teks persetujuan yang ditulis Claude bukan bukti persetujuan; saat itu yang dibutuhkan
adalah sesuatu yang hanya bisa diberikan Atha.

Diputuskan 2026-10-28 (Atha):
- **Batch 4 selesai** (#214, 3/5). Sesudahnya: dua jalur kerja (ketat: AGENTS.md, spek + mutants + `verify.sh` + "merge" Atha;
  cepat: kemampuan agen, Claude merge sendiri, `verify.sh` penuh tidak per PR tapi wajib sebelum setiap batch).
- **Arah:** Argus sebagai coding agent untuk membangun aplikasi production. SWE-bench ±20% usaha (dev set regresi, batch baru
  sesekali untuk klaim); ±80% dogfooding. Aplikasi latihan pertama: **`argus-ledger`** (dashboard ledger Argus, repo terpisah,
  bertahap CLI → filter → API → HTML → SQLite → login). Mode fitur di drafter hanya bila tahap 0 membuktikan perlu.
- **M7/M8 di parkiran** (belum diputuskan), selain yang dibutuhkan task nyata. Web search lalu deep research sesudah tahap awal
  `argus-ledger`. Tawaran marketplace skill (Agensi.io) **nanti**.
- (sore) Urutan: blok "Why they fail now" per tes (#225, jalur ketat, di-merge Atha) → hardening login argus-ledger (008 selesai,
  009–010 satu batch berurutan) → `verify.sh` + batch SWE 5 → web search ditunda sampai ada task yang butuh dokumentasi.
  **argus-ledger jalur cepat:** Claude approve draf, review, dan commit; dari Atha hanya "go live" per job.

Diputuskan 2026-10-29/30 (Atha):
- **Staging v0** (#244, "merge") dan pilotnya (#245, satu "go live" per deploy, 4 total). Production sungguhan tetap butuh
  persetujuan terpisah.
- **Upgrade dependency v0** (#246): cek awal Claude menunjukkan stack terbaru tidak butuh perubahan kode di argus-ledger, jadi
  task agen dua lengan **ditunda** sampai ada upgrade/issue yang butuh API rilis baru. Versi: `up1` sekarang (httpx2 + fastapi
  0.143.2, aturan 2 minggu tetap), `up2` (starlette 1.10.0, fastapi 0.162.0) mulai 2026-11-07. `ledger_py312_up1` tidak masuk
  `web.environments`.
- **"Go live" per rencana:** satu "go live" untuk satu `PLAN.md` yang ter-commit (dipakai pertama di #248: 1 keputusan untuk 4
  perintah staging).
- **Staging hardening** sebagai PR terpisah (#249, "merge" langsung).
