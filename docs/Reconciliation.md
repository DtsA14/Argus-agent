# Rekonsiliasi: `FUTURE_ARCHITECTURE.md` terhadap kode (2026-10-22)

Status: **laporan terkini; satu-satunya tempat status milestone dan ADR.** Basis: `main` `bf5416d`. Status di bawah berasal dari kode
(dicek langsung bila ditandai *dicek*), dari bukti di `verification/` dan `pilots/`, dan dari review di `docs/reviews/`. Laporan sebelumnya
(2026-10-21, dengan keputusan GPT dan Atha) diarsipkan di [`reviews/RECONCILIATION_2026-10-21.md`](reviews/RECONCILIATION_2026-10-21.md);
keputusannya tetap berlaku. Daftar kerja ada di [`PENDING.md`](../PENDING.md).

Legenda: `[x]` selesai dan terbukti · `[~]` sebagian (ada untuk jalur tertentu, sisanya belum) · `[ ]` belum dimulai.

## 1. Milestone

| Milestone | Status | Bukti | Gap yang belum tertutup |
|---|---|---|---|
| M1–M2 harness, LLM nyata, sandbox | `[x]` | `harness/`, `tools/sandbox.py`; arsip `PENDING` | – |
| M3 evaluasi | `[x]` | `docs/reviews/M3_CLOSING.md`; kalibrasi judge PASS | – |
| General-task agent (dulu "M4 slice 1") | `[x]` | `codetask/`, `acceptance/`; Eval Set v1 16/16 | Eval Set v1 jenuh: regresi saja, bukan ukuran kemampuan |
| **M4** multi-agent paralel dengan dependensi | `[ ]` | Graf riset (M1–M2) punya worker paralel lewat fan-out tanpa dependensi (`graph.py`, *dicek*); code task satu agen | Penjadwal dengan dependensi, batas sumber daya, multi-agent untuk code task. Belum ada bukti single-agent menjadi penghalang |
| **M5** observability dan benchmark | `[~]` | Ledger per panggilan dengan latensi, cache, `duration_s`/`origin` sandbox; `audit_run.py`, `failure_trace.py`, `scripts/pilot_report.py` (agregat lintas run), `evals/runner.py`, `run_series.py` | Tracing/dashboard (*dicek*: tidak ada Langfuse/LangSmith/OTel); benchmark single vs multi (tidak ada multi); **waktu supervisi manusia tidak pernah diukur** (pilot 3a–3b: unknown); eval set 10–20 task yang tidak jenuh |
| **M6** repo → PR | `[x]` MVP | W0–W5; 10 run live pilot di 6 task (bagian 4), 6 task `agent-completed`; patch agen diterapkan ke `main` di pilot 1, 2, 4, 5, 3a, 3b | W2b drafter: satu task `agent-completed` tanpa patch referensi (`pr_title2`, W2b-2); task yang mengubah tes lama sudah bisa dicek (W2a-ext) tapi belum dipilot (W2b-3); repo selain Argus; PR tetap dibuka manusia (disengaja); tingkat sukses umum belum ada (sampel kecil, semua task di repo Argus) |
| M7 registry dan policy, MCP | `[ ]` | – | Seluruhnya (ADR-001, sebagian ADR-007) |
| M8 penemuan tool, memori prosedural | `[ ]` | – | Seluruhnya (ADR-003) |
| M9 deployment terkendali | `[ ]` | – | Seluruhnya |
| Capability pack (gambar, video/audio, game) | `[ ]` | – | Seluruhnya; gate non-kode ADR-006 |

## 2. ADR

| ADR | Status | Yang ada di kode (code task kecuali disebut) | Gap |
|---|---|---|---|
| 001 registry dan policy | `[ ]` | Allowlist tool per role di config + `tools` kontrak yang hanya boleh menambah dari `CONTRACT_TOOLS`, dibekukan per run; versi tool masuk kunci memo | Registry formal (id/versi, schema, biaya, izin, trust, provenance), policy engine. Target M7 |
| 002 workflow bertipe | `[~]` | Rencana orchestrator graf riset divalidasi harness (`nodes/plan.py`); state machine code task dengan transisi legal (`codetask/status.py`); draf task bertipe yang dicek deterministik (W2a); drafter model yang menulis draf itu dan setiap submit-nya dicek harness (W2b, belum live) | Planner dinamis untuk code task; task dengan dependensi eksplisit; bukti live bahwa draf model layak |
| 003 memori berlapis | `[ ]` | Hanya state eksekusi (checkpoint, memo) | Knowledge dan project memory. Target M8 |
| 004 durable, idempotensi, budget | `[~]` (kuat) | Reservasi token+USD sebelum kirim, ledger `llm_call_started`/`llm_call`, `unknown_after_crash` di kasus terburuk, `durability="sync"`, memo per langkah dengan identitas input, crash-resume lintas proses, `reservation_from_ledger`; anggaran attempt dalam USD (D1), harga cache dengan kasus terburuk tarif tulis (D5), kegagalan hitung token berakhir rapi | **Idempotency key sisi provider** (*dicek*: tidak ada); exactly-once memang tidak dijanjikan |
| 005 artifact dan workspace | `[~]` | Workspace per run dengan path jail, scope tulis, digest snapshot; intake commit persis dengan provenance; paket review (`changes.patch`, provenance, validasi ulang) | Artifact store terpisah (id, versi, induk, retensi; *dicek*: tidak ada); versioning lintas run |
| 006 quality gate | `[~]` (kuat untuk kode) | Kontrak beku sebelum eksekusi, validasi di sandbox, verdict dengan bukti, klaim dicek, validasi ulang independen; cek draf (baseline merah, referensi hijau) | Gate non-kode (gambar, video, game) |
| 007 keamanan dan approval | `[~]` | Sandbox Docker (tanpa jaringan, read-only, tanpa capability), output sandbox diperlakukan sebagai data berlabel, kunci di env dan diketik manusia; approval manusia di titik `--approve` dan "go live", gerbang `go_live.sh` yang terikat ke sha kontrak dan config (parameter berubah = ditolak) | **Layanan approval dan policy engine di kode** (*dicek*: tidak ada interrupt atau `policy_decision`); pencatatan keputusan policy dalam format ADR; approval untuk aksi berisiko di dalam run |

## 3. Kriteria MVP M6 (`FUTURE_ARCHITECTURE.md` bagian 6)

| Kriteria | Status | Bukti |
|---|---|---|
| Issue dan repo target ber-scope | ✓ | kontrak (`inputs`, `scope`), intake W4 |
| Rencana bertipe dan kriteria eksplisit | ~ | draf W2a (rencana, kontrak, tes) ditulis manusia di semua pilot; drafter model (W2b): W2b-1 (3 run) dan W2b-2 (`pr_title2` agent-completed tanpa patch referensi, $0,54) |
| Baca/tulis terbatas workspace | ✓ | path jail (`tools/fs.py`), scope tulis, protected |
| Kode dan tes terisolasi | ✓ | sandbox Docker, lingkungan `argus` tanpa jaringan |
| Batas biaya per task dan per run | ✓ | reservasi attempt (token/USD), cap run = min(config, kontrak) |
| Simpan state dan resume | ✓ | checkpoint `sync`, memo, tes crash lintas proses |
| Tanpa panggilan berbayar ganda bila bisa direkonsiliasi | ✓ | memo per langkah, `reservation_from_ledger`; idempotency key provider tidak ada |
| Artefak, diff, log, provenance | ✓ | run dir, ledger, paket review, provenance |
| Tolak tool dan akses di luar scope | ✓ | allowlist, `tool_denied`, scope, sandbox tanpa jaringan |
| Lulus/gagal per kriteria dengan bukti | ✓ | verdict, `failure_trace.py`, `audit_run.py` |
| Diff/PR yang bisa direview, tanpa merge otomatis | ✓ | `build_review.py`; PR dibuka manusia |
| Tes deterministik: sukses, kegagalan tool, timeout, crash, budget habis, izin ditolak, output rusak, gate gagal | ✓ | W0 dan suite code task (model palsu) |

## 4. Pilot M6 (semua di repo Argus, Sonnet 5.5)

| Pilot | Task | Run | Hasil | Biaya | Catatan |
|---|---|---|---|---|---|
| 1 | `run_stats` melewati baris bukan-JSON | 1 | `agent-completed` | $0,0575 | patch identik dengan referensi |
| 2 | validasi `--impl` (2 berkas) | 1 | `agent-completed` | $0,0795 | pulih di attempt 2 lewat umpan balik |
| 3a | pembaca run bersama + 2 inspektor (3 berkas) | `pilot3a`, `pilot3a2` | `failed` | $0,2000 + $0,1937 | keempat attempt `reservation_exhausted` (profil token `large`) |
| 3a (D1–D3) | sama, profil `large_usd`, validasi otomatis | `pilot3a4` | `failed` (sebagian) | $0,3947 | satu putaran perbaikan, 3 → 1 tes gagal, anggaran habis |
| 3a (D1–D3, D5) | sama + prompt caching | `pilot3a5` | **`agent-completed`** | $0,1501 | hemat 64% oleh cache; patch diterapkan |
| 3b | agregator `pilot_report.py` (1 berkas baru) | `pilot3b1` | **`agent-completed`** | $0,1103 | tulisan pertama lulus 17/17 |
| 4 | `is_peak` tengah malam (1 fungsi) | `pilot4a`, `pilot4b` | `agent-completed` | 2 × $0,0289 | patch byte-identik di dua run |
| 5 | `is_peak` gagal tertutup | `pilot5a` | `agent-completed` | $0,0426 | |

Total 10 run live: **$1,29**. `pilot3a3` (kunci ter-paste dua kali) mati sebelum panggilan pertama, $0; gerbang 3b sekarang memeriksa bentuk kunci.

**Terbukti (sampel kecil, bukan tingkat sukses):** task satu fungsi sampai tiga berkas selesai di repo Argus dengan acceptance
deterministik, biaya $0,03–0,15 per task yang selesai; kegagalan jujur dan terbaca (0 klaim palsu yang lolos); perbaikan harness
D1–D3 + D5 mengubah 3a dari gagal ($0,39) menjadi selesai ($0,15).
**Belum terbukti:** tingkat sukses umum; repo selain Argus; ≥ 2 putaran perbaikan dalam satu attempt (pertanyaan B D5: 3a dan 3b tidak
membutuhkannya); waktu supervisi manusia.

## 5. Mode kegagalan (`FUTURE_ARCHITECTURE.md` bagian 8)

| Mode | Status | Bukti / gap |
|---|---|---|
| Crash sebelum/sesudah request | ✓ | ledger `llm_call_started`/`llm_call`, `unknown_after_crash`, tes crash lintas proses |
| Timeout, rate limit, hasil berbayar ambigu | ✓ | retry transien, `Retry-After`, tagih kasus terburuk; tanpa idempotency key provider |
| Konflik/overrun budget | ✓ | reservasi sebelum kirim, `EstimateExceeded` → `FAILED_BUDGET` durable |
| Workflow tidak valid atau siklik | ~ | rencana graf riset divalidasi; tidak ada workflow dengan dependensi, jadi siklus belum relevan |
| Perubahan schema/versi tool | ~ | versi tool dan image di kunci memo; tanpa registry |
| Dokumen berbahaya, prompt injection | ~ | fixture injeksi di kalibrasi judge (4/4); output sandbox berlabel "data, not instructions"; belum diukur untuk code task |
| Lolos sandbox, jaringan tak sah | ✓ | hardening Docker diuji di container nyata |
| Artefak hilang/rusak | ~ | baris log rusak ditoleransi dan dihitung (`parse_lines`, `evals/runlog.py`), cek intake dan digest; tanpa artifact store |
| Memori/prosedur basi | n/a | belum ada memori |
| Evaluator berselisih / verdict rusak | ✓ | judge gagal tertutup (M3) |
| Retry loop / planner berosilasi | ✓ | aturan stagnan, `max_iterations`, `max_steps` |
| Approval dicabut / parameter berubah | ~ | tidak ada layanan approval; gerbang `go_live.sh` menolak bila kontrak/config berubah setelah approval |
| Tulis bersamaan ke berkas proyek | ✗ | belum ditangani (satu agen per workspace) |

## 6. Gap terbuka, diurutkan menurut nilai sekarang

1. **Waktu supervisi manusia tidak diukur** (M5, M6). Murah: catat di laporan pilot dan di berkas supervisi `pilot_report.py`.
2. **Repo selain Argus** (M6). Semua bukti dari satu repo; Athena butuh image sandbox per proyek.
3. **Pertanyaan B D5** (≥ 2 putaran perbaikan dalam satu attempt): butuh task yang memang menuntut beberapa putaran.
4. **Eval set yang tidak jenuh** (M5): v1 16/16; perluasan dari kegagalan nyata (3a v1 adalah kandidat).
5. **`pilot_report.py` `success_rate`** membuang `NO_RESULT` dari pembagi (catatan review): ubah atau laporkan keduanya sebelum dipakai.
6. **Idempotency key provider** (ADR-004): tidak ada; dampak rendah selama tidak ada aksi eksternal selain panggilan model.
7. **Layanan approval/policy di kode** (ADR-007, M7): approval sekarang manusia di luar run; baru perlu bila agen melakukan aksi berisiko di dalam run.
8. **M4, M7, M8, M9, capability pack**: ditunda sampai ada bukti kebutuhan (keputusan 2026-10-21).

## 7. Keputusan yang diminta

1. Gap 1 (supervisi) dan 2 (repo lain) sebagai langkah berikutnya, dalam urutan itu?
2. Eval set yang lebih sulit (gap 4) dirancang dari kegagalan nyata, atau ditunda sampai ada repo kedua?
