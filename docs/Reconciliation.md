# Rekonsiliasi: `FUTURE_ARCHITECTURE.md` terhadap kode (2026-10-30)

Status: **laporan terkini; satu-satunya tempat status milestone dan ADR.** Basis: `main` sesudah #266. Status di bawah berasal
dari kode, dari bukti di `verification/` dan `pilots/`, dan dari review di `docs/reviews/`. Laporan sebelumnya diarsipkan:
[`reviews/RECONCILIATION_2026-10-27.md`](reviews/RECONCILIATION_2026-10-27.md) (dengan tambahan sampai 2026-10-30),
[`reviews/RECONCILIATION_2026-10-24.md`](reviews/RECONCILIATION_2026-10-24.md),
[`reviews/RECONCILIATION_2026-10-22.md`](reviews/RECONCILIATION_2026-10-22.md) dan
[`reviews/RECONCILIATION_2026-10-21.md`](reviews/RECONCILIATION_2026-10-21.md); keputusannya tetap berlaku. Daftar kerja ada di
[`PENDING.md`](../PENDING.md).

Yang berubah sejak 2026-10-27: **arah coding agent untuk production** (2026-10-28) dengan dua aplikasi latihan; **`argus-ledger`**
14 task di `main`; batch SWE 4 dan 5 serta dev set 1–2 (regresi); ReadDocs (#229), stage riset (#242), counter reasoning (#240),
harga peak (#241); **staging** (#244, #246, #249, #251, #258) dengan monitor dan notifikasi (#259, #260); **aplikasi kedua
`argus-viewer`** (React PWA, JS divalidasi dengan vitest di `pwa_node22`, #256, #257, #261, #263): dua issue ditulis agen,
dirilis ke staging dan **dipakai Atha di HP** lewat SSH port forwarding.

Legenda: `[x]` selesai dan terbukti · `[~]` sebagian (ada untuk jalur tertentu, sisanya belum) · `[ ]` belum dimulai.

## 1. Milestone

| Milestone | Status | Bukti | Gap yang belum tertutup |
|---|---|---|---|
| M1–M2 harness, LLM nyata, sandbox | `[x]` | `harness/`, `tools/sandbox.py`; arsip `PENDING` | – |
| M3 evaluasi | `[x]` | `docs/reviews/M3_CLOSING.md`; kalibrasi judge PASS | – |
| General-task agent | `[x]` | `codetask/`, `acceptance/`; Eval Set v1 16/16 | Eval Set v1 jenuh: regresi saja |
| **M4** multi-agent dengan dependensi | `[ ]` | Graf riset punya fan-out tanpa dependensi; code task satu agen | Belum ada bukti single-agent menjadi penghalang |
| **M5** observability dan benchmark | `[~]` | Ledger per panggilan; `audit_run.py`, `failure_trace.py`, `pilot_report.py`; keputusan manusia dengan waktunya di `job.json` (#185; `argus-ledger` 014 menampilkannya); `swe_grade.py`; `argus-ledger report` (biaya per stage); jumlah keputusan per pilot di setiap `RESULT.md` | Tracing/dashboard; benchmark single vs multi; **menit kerja Atha** belum ditanyakan; **eval set yang tidak jenuh** |
| **M6** repo → PR | `[x]` MVP | Repo Argus (pilot M6, W2b, router); **sympy** (SWE, bagian 4b); **`argus-ledger`** Python/FastAPI, 14 task (bagian 4c); **`argus-viewer`** JS/React, 2 task, vitest di `pwa_node22` (bagian 4c) | Tingkat sukses umum (SWE tanpa bocoran sampel kecil); PR/apply tetap oleh manusia/Claude (disengaja); `argus apply` belum ada; berkas yang dilindungi di repo JS dicek skrip di luar harness; vitest: tes lama belum bisa diubah, tanpa Playwright |
| M7 registry dan policy, MCP | `[ ]` | – | Seluruhnya (ADR-001, sebagian ADR-007). Kandidat: layanan approval bersama UI kontrol (bagian 7) |
| M8 penemuan tool, memori prosedural | `[ ]` | – | Seluruhnya (ADR-003) |
| M9 deployment terkendali | `[~]` (staging) | `argus stage deploy\|rollback\|restart\|check\|status\|monitor\|report` (#244, #246, #249, #251, #258): hanya commit job `APPLIED` apa adanya, container tanpa jaringan/read-only/non-root di Unix socket, peer = pid container, data asli lewat snapshot allowlist, monitor 15 menit, **notifikasi ntfy** sesudah 3 gagal (#259, #260), namespace per direktori staging (#258). **Aplikasi statis** (#257, #261, #263): build tanpa jaringan di `pwa_node22`, cek artifact (A4), `sw.js` dipin, swap `current` atomik sesudah smoke kandidat, proxy `127.0.0.1:8710` GET/HEAD (Host, CSP, `no-store` untuk API, hanya `/sw.js` boleh jadi service worker), unit `systemd --user`. Dua aplikasi, pilot staging #1, upgrade #1, data asli #1, viewer #1–#2 | **Production** (DNS/TLS, pengguna, kredensial): ditunda (keputusan 2026-10-30, pemicu di bagian 7); smoke kandidat tidak menguji lingkungan unit systemd |
| Capability pack (gambar, video/audio, game) | `[ ]` | – | Seluruhnya; gate non-kode ADR-006 |

M4, M7, M8, dan capability pack tetap **ditunda sampai ada bukti kebutuhan** (keputusan 2026-10-21, ditegaskan 2026-10-24).

## 2. ADR

| ADR | Status | Yang ada di kode | Gap |
|---|---|---|---|
| 001 registry dan policy | `[ ]` | Allowlist tool per role + `tools` kontrak yang hanya menambah; versi tool dan image di kunci memo | Registry formal, policy engine. Target M7 |
| 002 workflow bertipe | `[~]` (kuat) | State machine code task dan job router; drafter model dicek harness per submit (red karena assertion, untuk pytest dan **vitest**: hanya `AssertionError` lewat frame/`cause`); stage riset dengan gate (#242) | Planner dinamis; dependensi eksplisit |
| 003 memori berlapis | `[ ]` | Hanya state eksekusi | Target M8 |
| 004 durable, idempotensi, budget | `[~]` (kuat) | Reservasi sebelum kirim, ledger, `durability="sync"`, memo per langkah, crash-resume, `reservation_from_ledger`; cap per job; `max_input`/`max_output` per model; counter heuristik menghitung reasoning yang dikirim (#240); worst case selalu ×peak (#241) | Idempotency key provider; cap USD non-Anthropic bertumpu pada perkiraan heuristik |
| 005 artifact dan workspace | `[~]` | Workspace per run (jail, scope, digest); environment per job dengan image dipin (Python dan **Node `pwa_node22`** distroless dari lock sha512); rilis staging = `git archive` commit applied, read-only, image/runtime/hash dist tercatat | Artifact store; id image tidak reproducible (hanya rootfs); **pin image per checkout disalin manual** |
| 006 quality gate | `[~]` (kuat untuk kode) | Kontrak beku, validasi di sandbox, verdict dengan bukti, validasi ulang; penilai SWE dengan tes tersembunyi; staging: smoke dari host, cek artifact, pin service worker | Gate non-kode |
| 007 keamanan dan approval | `[~]` | Sandbox Docker; key dari file 0600 (`--key-file`); output sandbox berlabel data; staging tanpa jaringan; proxy viewer hanya `127.0.0.1`, akses HP lewat kunci SSH yang dibatasi `permitopen` ke 8710 | Persetujuan "go live" hanya di chat (satu per `PLAN.md` untuk staging); layanan approval di kode tidak ada; dibuka bersama UI kontrol fase 2–3 atau `argus apply` |

## 3. Kriteria MVP M6

Semua kriteria `FUTURE_ARCHITECTURE.md` bagian 6 terpenuhi sejak 2026-10-27 (tabel di arsip 2026-10-27); bukti tambahan:
repo JS (`argus-viewer`) dengan validasi vitest dan red check yang sama ketatnya dengan pytest.

## 4a. Pilot M6 sampai 2026-10-22

10 run live di 6 task, 6 `agent-completed`, $1,29 (arsip [`reviews/RECONCILIATION_2026-10-22.md`](reviews/RECONCILIATION_2026-10-22.md)).

## 4b. SWE-bench (sympy), alat regresi sejak 2026-10-28

| Kelompok | Hasil | Biaya | Catatan |
|---|---|---|---|
| `23534`, batch 1, batch 2 | 7/7 `resolved` | – | *oracle-informed/assisted*, tidak dicampur |
| Batch 3 (`sympy_py39`) | **3/4** tanpa bocoran | $0,2127 | `RESULT.md` di `pilots/swe_v0/batch3/` |
| Batch 4 | **3/5** (3/4 tanpa yang *harness-blocked*) | $0,4260 | #214 |
| Batch 5 (sympy 1.6–1.8) | **2/5** (1/4 tanpa campur tangan) | $0,8746 | dua kegagalan agen di berkas besar → `EditFile` 2 MB |
| Dev set 1–2 (bukan klaim) | 2/3 lalu 3/3 | $0,4968 + $0,0615 | sesudah perbaikan alat baca/tulis |

**Batas klaim:** harness menyelesaikan task SWE-bench ujung ke ujung, bukan kemampuan model pada bug baru (instance publik,
kemungkinan terkontaminasi); penilai milik Argus, tidak dibandingkan dengan leaderboard.

## 4c. Dogfooding: aplikasi latihan

| Aplikasi | Task di `main` | Biaya job | Catatan |
|---|---|---|---|
| **`argus-ledger`** (Python, FastAPI, SQLite) | 14 (tahap 0–12 + satu fix) | tahap 0–10 $0,5688; 013 $0,0179; 014 $0,0800 | CLI, API, HTML, login + hardening, report, keputusan manusia; 010 tidak di-merge (2 cacat ditemukan uji serangan); 0 tes lama dilonggarkan, 0 patch ditulis ulang; di staging dengan data asli |
| **`argus-viewer`** (React 19 PWA, vitest) | 2 (issue 001 daftar job, 002 halaman job) + kerangka Claude | $0,0198 + $0,0243 | drafter dan agen berhasil di percobaan pertama; 23 tes baru, semua merah karena assertion; review Claude tidak mengubah hasil apa pun (sampel 2); live di staging, dipakai Atha di HP |

**Terbukti (sampel kecil):** fitur nyata dari issue ke rilis staging dengan 1–2 keputusan Atha per job ("go live"), biaya
$0,02–0,08 per fitur; repo JS dengan jaminan red check yang sama.
**Belum terbukti:** task yang tidak dijelaskan rinci oleh Claude (semua issue ditulis Claude); tanpa review Claude (shadow
mode diusulkan).

## 5. Mode kegagalan (`FUTURE_ARCHITECTURE.md` bagian 8)

| Mode | Status | Bukti / gap |
|---|---|---|
| Crash sebelum/sesudah request | ✓ | ledger, `unknown_after_crash`, tes crash lintas proses; `argus resume` |
| Timeout, rate limit, hasil berbayar ambigu | ✓ | retry transien, tagih kasus terburuk; tanpa idempotency key provider |
| Konflik/overrun budget | ✓ | reservasi sebelum kirim, `FAILED_BUDGET` durable; cap per job; `flock` per job |
| Workflow tidak valid atau siklik | ~ | transisi legal job dan code task; tanpa workflow dengan dependensi |
| Perubahan schema/versi tool | ~ | versi tool dan image di kunci memo; image dipin per job; tanpa registry |
| Dokumen berbahaya, prompt injection | ~ | output sandbox berlabel data; teks dibersihkan dari karakter kontrol; belum diukur untuk code task |
| Lolos sandbox, jaringan tak sah | ✓ | hardening Docker diuji; build rilis viewer tanpa jaringan dites |
| Artefak hilang/rusak | ~ | cek intake dan digest; rilis staging read-only dengan hash tercatat; tanpa artifact store |
| Memori/prosedur basi | n/a | belum ada memori |
| Evaluator berselisih / verdict rusak | ✓ | judge gagal tertutup; penilai SWE menolak hasil tidak sah |
| Retry loop / planner berosilasi | ✓ | `max_iterations`, `max_steps`; `retry` hanya atas perintah manusia |
| Agen membaca tanpa menulis sampai konteks habis | ~ | feedback dan carry (#188); alat baca (#215, #227) dan `EditFile` 2 MB menutup penyebab utama di dev set 2 |
| Thinking menghabiskan output | ~ | output per model dan petunjuk (#200, #204) |
| Approval dicabut / parameter berubah | ~ | approve terikat sha draf; persetujuan run di chat tidak tercatat di job (ADR-007) |
| Tulis bersamaan ke berkas proyek | ✗ | satu agen per workspace; satu perintah per job |
| **Tes merusak staging live** | ✓ | ditemukan 2026-10-30 (reconcile menghapus container live); label `argus.staging.base` per direktori (#258) |
| **Kegagalan staging tidak terlihat** | ✓ | notifikasi ntfy sesudah 3 gagal berturut-turut (#259, #260) |

## 6. Gap terbuka, diurutkan menurut nilai sekarang

1. **Supervisi dan "melepas" Argus:** di dua aplikasi latihan Claude masih menulis issue, mereview draf dan patch, dan
   men-deploy. Review Claude belum mengubah hasil di task viewer (sampel 2). Langkah: **shadow mode** per kelas task, dengan
   **berkas yang dilindungi dipaksa harness** sebagai prasyarat. Ukuran: jumlah blok yang akan terjadi, menit Atha.
2. **UI kontrol interaktif** (permintaan Atha 2026-10-30): menunggu keputusan scope (bagian 7). Menyentuh ADR-007 (approval
   tercatat), key, dan CSRF; fase 1 read-only bisa jalan lebih dulu.
3. **Operasional staging:** pin image per checkout disalin manual; smoke kandidat tidak menguji unit systemd; up2 mulai
   2026-11-07.
4. **Tingkat sukses di repo luar tanpa bocoran** (SWE, alat regresi ±20% usaha).
5. **Eval set yang tidak jenuh** dan **menit kerja manusia** (M5).
6. **Efek petunjuk berhenti** (#188, #200, #204) terpisah dari variasi model; **pertanyaan B D5**.
7. **`argus apply`**, **idempotency key provider**: dampak rendah selama apply dilakukan Claude dan tidak ada aksi eksternal
   selain panggilan model.
8. **M4, M7, M8, capability pack, production**: ditunda sampai ada bukti kebutuhan.

## 7. Keputusan

Keputusan sampai 2026-10-30 siang ada di arsip [`reviews/RECONCILIATION_2026-10-27.md`](reviews/RECONCILIATION_2026-10-27.md)
bagian 7 (dua jalur, arah production, staging, upgrade, "go live" per rencana, data asli). Sesudahnya:

Diputuskan 2026-10-30 (Atha):
- **Viewer PWA** (`docs/reviews/SPEC_PWA_VIEWER.md`): proxy selalu hidup, bind eksplisit `127.0.0.1`, port 8710, repo lokal, dua
  PR jalur ketat; kerangka Claude dengan `sw.js` **network-first** (pin membuat `sw.js` tidak pernah diperbarui browser);
  berkas yang dilindungi lewat skrip `check_protected.py` (bukan ingatan); tes deploy dengan pin default asli.
- **Pin `SW_SHA256`** (#261): "merge bila verify lulus". **Unit proxy** (#263): "merge" + "go live".
- **Akses HP:** Termius Local forward; kunci HP sendiri dengan `permitopen="127.0.0.1:8710"` tanpa shell.
- **Production ditunda:** viewer tetap di staging; production dibuka bila ada pengguna kedua, kebutuhan akses tanpa Termius,
  atau latihan deploy production, dengan spek dulu.
- Issue 003 (tampilan HP) tidak diperlukan.

Menunggu keputusan Atha:
1. **UI kontrol** (scope di `PENDING.md`): siapa yang approve, batas biaya lewat UI, "go live" lewat tombol, port 8711 +
   `permitopen` kedua, waktunya terhadap up2.
2. **Shadow mode** untuk issue viewer read-only, sesudah berkas yang dilindungi dipaksa harness.
