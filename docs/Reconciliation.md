# Rekonsiliasi: `FUTURE_ARCHITECTURE.md` terhadap kode (2026-10-24)

Status: **laporan terkini; satu-satunya tempat status milestone dan ADR.** Basis: `main` `00f7668`. Status di bawah berasal dari kode
(dicek langsung bila ditandai *dicek*), dari bukti di `verification/` dan `pilots/`, dan dari review di `docs/reviews/`. Laporan sebelumnya
diarsipkan: [`reviews/RECONCILIATION_2026-10-22.md`](reviews/RECONCILIATION_2026-10-22.md) dan
[`reviews/RECONCILIATION_2026-10-21.md`](reviews/RECONCILIATION_2026-10-21.md); keputusannya tetap berlaku. Daftar kerja ada di
[`PENDING.md`](../PENDING.md).

Yang berubah sejak 2026-10-22: drafter model (W2b) dipakai live; **router v0** (`argus code`: satu job, cap per job, kunci per job,
approve terikat ke sha draf) dengan `--key-file`/`--yes`, status (waktu keputusan, perintah apply, alasan gagal), konteks agen dan
`argus retry`, dan **environment per job** dengan image yang dipin; model bawaan pindah ke **DeepSeek V4.1 Flash** (thinking); pilot
pertama di **repositori selain Argus** (sympy, dinilai ala SWE-bench).

Legenda: `[x]` selesai dan terbukti · `[~]` sebagian (ada untuk jalur tertentu, sisanya belum) · `[ ]` belum dimulai.

## 1. Milestone

| Milestone | Status | Bukti | Gap yang belum tertutup |
|---|---|---|---|
| M1–M2 harness, LLM nyata, sandbox | `[x]` | `harness/`, `tools/sandbox.py`; arsip `PENDING` | – |
| M3 evaluasi | `[x]` | `docs/reviews/M3_CLOSING.md`; kalibrasi judge PASS | – |
| General-task agent (dulu "M4 slice 1") | `[x]` | `codetask/`, `acceptance/`; Eval Set v1 16/16 | Eval Set v1 jenuh: regresi saja, bukan ukuran kemampuan |
| **M4** multi-agent paralel dengan dependensi | `[ ]` | Graf riset (M1–M2) punya worker paralel lewat fan-out tanpa dependensi (`graph.py`); code task satu agen | Penjadwal dengan dependensi, batas sumber daya, multi-agent untuk code task. Belum ada bukti single-agent menjadi penghalang |
| **M5** observability dan benchmark | `[~]` | Ledger per panggilan; `audit_run.py` (juga membangun ulang feedback berhenti, peringatan konteks, dan carry retry), `failure_trace.py`, `pilot_report.py` (`success_rate` dan `success_rate_all`); **log keputusan manusia dengan waktunya di `job.json`** (`limits_shown`, `confirmed`/`confirmed_by_flag`, `key_typed`/`key_from_file`, `approved`, `retry`; #185); penilai ala SWE-bench `scripts/swe_grade.py` | Tracing/dashboard (*dicek*: tidak ada Langfuse/LangSmith/OTel); benchmark single vs multi; **menit kerja Atha** masih belum ditanyakan (yang terukur: jumlah keputusan dan waktu mesin); **eval set yang tidak jenuh**: kandidatnya instance SWE-bench, tapi terkontaminasi (bagian 4b) |
| **M6** repo → PR | `[x]` MVP | W0–W5; 10 run live pilot (bagian 4a); drafter model live (W2b-1/2/3); router (bagian 4b); **repo selain Argus**: sympy, `resolved` (bagian 4b) | Tingkat sukses umum: belum ada (sampel 1 di repo luar); PR tetap dibuka manusia (disengaja); `argus apply` belum ada (perintahnya dicetak `status`); pertanyaan B D5 (≥ 2 putaran perbaikan dalam satu attempt) belum terjawab |
| M7 registry dan policy, MCP | `[ ]` | – | Seluruhnya (ADR-001, sebagian ADR-007). Kandidat slice terkecil bila dibutuhkan: pencatatan keputusan policy (bagian 2, ADR-007) |
| M8 penemuan tool, memori prosedural | `[ ]` | – | Seluruhnya (ADR-003) |
| M9 deployment terkendali | `[ ]` | – | Seluruhnya |
| Capability pack (gambar, video/audio, game) | `[ ]` | – | Seluruhnya; gate non-kode ADR-006 |

M4, M7, M8, M9, dan capability pack tetap **ditunda sampai ada bukti kebutuhan** (keputusan 2026-10-21, ditegaskan 2026-10-24: tidak
ditutup lewat dokumen). Belum ada pilot yang tertahan karena tidak ada registry, policy engine, memori, atau multi-agent.

## 2. ADR

| ADR | Status | Yang ada di kode (code task kecuali disebut) | Gap |
|---|---|---|---|
| 001 registry dan policy | `[ ]` | Allowlist tool per role di config + `tools` kontrak yang hanya boleh menambah, dibekukan per run; versi tool dan image (termasuk image environment) masuk kunci memo | Registry formal (id/versi, schema, biaya, izin, trust, provenance), policy engine. Target M7 |
| 002 workflow bertipe | `[~]` (kuat) | State machine code task (`codetask/status.py`) dan **job router** (`router/job.py`, transisi legal); draf task bertipe dicek deterministik (W2a); **drafter model live**: setiap submit dicek harness (red karena assertion #179, cek setup yang sama di cek draf #180); draf model lolos dan dipakai di W2b-2, W2b-3, router #1–#3, SWE v0; di SWE v0 tes drafter **lulus 4/4 di atas patch resmi maintainer** | Planner dinamis; task dengan dependensi eksplisit |
| 003 memori berlapis | `[ ]` | Hanya state eksekusi (checkpoint, memo) | Knowledge dan project memory. Target M8 |
| 004 durable, idempotensi, budget | `[~]` (kuat) | Reservasi sebelum kirim, ledger, `durability="sync"`, memo per langkah, crash-resume, `reservation_from_ledger`; D1/D5; **cap per job** yang dihitung dari ledger semua tahap, cap tahap dicatat saat mulai dan tidak dihitung ulang saat resume; kunci per job (`flock`); `retry` membuat tahap baru dengan cap dari sisa job; `max_input_tokens` per model (DeepSeek 60.000, Sonnet 40.000); perkiraan token heuristik **tidak** dipangkas (est/tagihan DeepSeek minimum 0,89) | **Idempotency key sisi provider** (tidak ada). Cap USD untuk model non-Anthropic bertumpu pada perkiraan token heuristik, jadi bukan batas mutlak (`FAILED_BUDGET` dapat sedikit melewati cap) |
| 005 artifact dan workspace | `[~]` | Workspace per run (path jail, scope, digest); intake commit persis tanpa `.git` (dites: commit yang lebih baru tidak terlihat); paket review; **environment per job dengan id image yang dipin** di `job.json`, image berubah = tahap ditolak; build image deterministik per rootfs (`build_env_sandbox_image.sh`) | Artifact store terpisah (tidak ada); id image tidak bisa direproduksi (hanya rootfs), jadi job tidak bisa dilanjutkan setelah image dibangun ulang (disengaja, K1 SPEC_SWE_PILOT); data instance SWE di luar repo (`~/swe`) tidak di-versioning (sha-nya di `grade.json`) |
| 006 quality gate | `[~]` (kuat untuk kode) | Kontrak beku, validasi di sandbox, verdict dengan bukti, klaim dicek, validasi ulang independen; cek draf; **penilai luar dengan tes tersembunyi** (`swe_grade.py`: patch harus sha paket review, berkas tes resmi dikembalikan lalu `test_patch` diterapkan, hasil per node, `missing` = tidak lulus, hasil yang tidak sah ditolak) | Gate non-kode. Penilai SWE milik Argus (Python 3.12), bukan harness resmi |
| 007 keamanan dan approval | `[~]` | Sandbox Docker (tanpa jaringan, read-only, non-root, tanpa capability; dites bahwa host dan `.git` tidak terlihat); output sandbox berlabel data; **key dari file 0600 di luar repo** (`--key-file`, isinya tidak pernah ditampilkan atau ditulis); teks yang dicetak dibersihkan dari karakter kontrol | **Approval run pindah ke chat:** dengan `--yes` (hanya bersama `--key-file`), `[y/N]` tidak ditanyakan dan gerbang `go_live.sh` per pilot tidak dipakai lagi. Yang tersisa di kode: layar batas tetap dicetak dan dicatat (`confirmed_by_flag`), approve terikat ke sha draf, image dan kontrak terikat ke job. Persetujuan "go live"/"y" Atha hanya tercatat di riwayat chat, tidak di `job.json`. Layanan approval dan policy engine di kode tetap tidak ada. Kandidat slice M7 terkecil: mencatat siapa menyetujui apa (teks persetujuan) di log job |

## 3. Kriteria MVP M6 (`FUTURE_ARCHITECTURE.md` bagian 6)

| Kriteria | Status | Bukti |
|---|---|---|
| Issue dan repo target ber-scope | ✓ | kontrak, intake W4; repo luar (sympy) di commit persis |
| Rencana bertipe dan kriteria eksplisit | ✓ | drafter model live (W2b, router, SWE v0), dicek harness dan di-approve manusia terikat sha |
| Baca/tulis terbatas workspace | ✓ | path jail, scope tulis, protected |
| Kode dan tes terisolasi | ✓ | sandbox Docker; environment per job (`argus`, `sympy`) |
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
| **SWE v0** | `sympy__sympy-23534` (repo sympy) | DeepSeek thinking | **`resolved`** (`FAIL_TO_PASS` 1/1, `PASS_TO_PASS` 11/11) | **$0,0202** | patch agen identik dengan patch maintainer; 2 keputusan run |

**Terbukti (sampel kecil, bukan tingkat sukses):** alur penuh berjalan tanpa PC (VM, `--key-file`/`--yes`), dengan 2–3 keputusan
manusia per task (dulu ±17 di W2b-2); drafter model menulis tes yang dipakai; satu task di repositori luar dinilai `resolved` oleh tes
resmi yang tidak terlihat; biaya per task yang selesai $0,02–0,08 di DeepSeek.

**Batas klaim SWE v0:** "harness Argus menyelesaikan task SWE-bench dari ujung ke ujung", **bukan** kemampuan model pada bug yang belum
pernah dilihat. Instance SWE-bench Verified publik dan kemungkinan ada di data latih (patch agen identik dengan patch maintainer).
Penilaian ala SWE-bench (Python 3.12, penilai milik Argus), **tidak** dibandingkan dengan leaderboard.

**Belum terbukti:** tingkat sukses umum; ≥ 2 putaran perbaikan dalam satu attempt; menit kerja manusia; efek petunjuk konteks #188
terpisah dari variasi model (satu run; peringatan 70% belum pernah muncul di run live).

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
| Agen membaca tanpa menulis sampai konteks habis | ~ | router #3: feedback antar attempt dan antar tahap (carry), satu peringatan konteks; terbukti satu kali |
| Approval dicabut / parameter berubah | ~ | approve terikat sha draf, kontrak dan image terikat job; persetujuan run di chat tidak tercatat di job (ADR-007) |
| Tulis bersamaan ke berkas proyek | ✗ | satu agen per workspace; satu perintah per job |

## 6. Gap terbuka, diurutkan menurut nilai sekarang

1. **Tingkat sukses di repo luar** (M6, M5): satu instance. Batch 5 instance sympy SWE-bench Verified (sedang direncanakan), dengan
   catatan kontaminasi; angka yang bersih butuh sumber yang lebih baru (SWE-rebench/Live).
2. **Eval set yang tidak jenuh** (M5): instance SWE sebagai eval regresi harness; bukan ukuran model selama terkontaminasi.
3. **Menit kerja manusia** (M5): jumlah keputusan dan waktu mesin sudah terukur; menit Atha belum ditanyakan di pilot mana pun.
4. **Persetujuan run di chat tidak tercatat di job** (ADR-007): slice terkecil bila dibutuhkan.
5. **Pertanyaan B D5** (≥ 2 putaran perbaikan dalam satu attempt).
6. **`argus apply`** (K6 router v0): belum ada bukti kebutuhan (apply 4 baris dari `status`).
7. **Idempotency key provider** (ADR-004): dampak rendah selama tidak ada aksi eksternal selain panggilan model.
8. **M4, M7, M8, M9, capability pack**: ditunda sampai ada bukti kebutuhan.

Kecil, dicatat di `PENDING.md`: layar batas tahap drafter tidak menyebut environment dan image (preflight chat menghitungnya dengan
fungsi yang sama); baris bit executable dari patch agen #189; cek key manual router #3.

## 7. Keputusan yang diminta

1. Batch 5 instance sympy sebagai langkah berikutnya, dengan persetujuan per batch untuk tahap `code` (approve tetap per draf)?
2. Gap 4 (mencatat persetujuan chat di job) sebagai slice ADR-007 sekarang, atau tunggu sampai ada aksi berisiko di dalam run?
