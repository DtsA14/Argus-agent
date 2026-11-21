# Rekonsiliasi: `FUTURE_ARCHITECTURE.md` terhadap kode (2026-10-30, isi diperbarui sampai 2026-11-11; arah diperbarui 2026-11-15; status kerja diperbarui 2026-11-16)

Status: **laporan terkini; satu-satunya tempat status milestone dan ADR.** Basis: `main` sesudah #444 (2026-11-11); angka kerja nyata dikutip dari `verification/scoreboard-2026-11-11.json` (`scripts/scoreboard.py`). Status di bawah berasal
dari kode, dari bukti di `verification/` dan `pilots/`, dan dari review di `docs/reviews/`. **Pembaruan 2026-11-15 hanya menyangkut arah**
(bagian 0, 6 dan 7) dan butir yang sudah usang karenanya; **pembaruan 2026-11-16 menyangkut status "bisa ditinggal" dan keputusan hari itu** (bagian 0, 6 dan 7, dari `PENDING.md` dan `pilots/`, bukan dari pembacaan kode); tabel milestone, ADR dan mode kegagalan **belum direkonsiliasi ulang terhadap
kode sesudah #444**, dan yang terjadi sesudahnya (#446–#545) dirangkum di bagian 0 dari `PENDING.md` dan `pilots/`, bukan dari pembacaan
kode. Laporan sebelumnya diarsipkan: [`reviews/RECONCILIATION_2026-11-11.md`](reviews/RECONCILIATION_2026-11-11.md) (salinan utuh sebelum arah diperbarui),
[`reviews/RECONCILIATION_2026-10-27.md`](reviews/RECONCILIATION_2026-10-27.md) (dengan tambahan sampai 2026-10-30),
[`reviews/RECONCILIATION_2026-10-24.md`](reviews/RECONCILIATION_2026-10-24.md),
[`reviews/RECONCILIATION_2026-10-22.md`](reviews/RECONCILIATION_2026-10-22.md) dan
[`reviews/RECONCILIATION_2026-10-21.md`](reviews/RECONCILIATION_2026-10-21.md); keputusannya tetap berlaku. Daftar kerja ada di
[`PENDING.md`](../PENDING.md).

Yang berubah sejak 2026-10-27: **arah coding agent untuk production** (2026-10-28) dengan dua aplikasi latihan; **`argus-ledger`**
14 task di `main`; batch SWE 4 dan 5 serta dev set 1–2 (regresi); ReadDocs (#229), stage riset (#242), counter reasoning (#240),
harga peak (#241); **staging** (#244, #246, #249, #251, #258) dengan monitor dan notifikasi (#259, #260); **aplikasi kedua
`argus-viewer`** (React PWA, JS divalidasi dengan vitest di `pwa_node22`, #256, #257, #261, #263): dua issue ditulis agen,
dirilis ke staging dan **dipakai Atha di HP** lewat SSH port forwarding. Tambahan sampai 2026-11-06: 21 issue viewer dikerjakan Argus (001-020 live; 021 di `main`, ikut rilis berikutnya), `argus judge` (#316) dan aturan review J9.

Yang berubah sejak 2026-11-06 (sampai 2026-11-11, #357-#437): **`argus judge`** (saran, #316) ada, tetapi dijalankan pada 10 dari 119 job kode (8,4%, scoreboard); aturan J9 disetujui 2026-11-06 untuk batch 4, sedangkan dari catatan tidak terbukti judge dijalankan pada batch 5; **UI kontrol**
fase 1-2 live di 8711 (baca, reject/abandon, chatbox penulis issue); **penulis issue** (`SPEC_ISSUE_WRITER`, Haiku 5.5 lewat
OpenRouter, pencarian bentrok oleh harness); **viewer PWA** sampai issue 044 (rilis 044 live), Tailwind di `pwa_node22` (#370);
**staging Stage 14-17** untuk `argus-ledger` (review draf, waktu stage, judul job, `max_usd`) dan snapshot yang menerbitkan
`title` (#421); **drafter**: validasi `old_tests_*` oleh harness (#429), perbaikan formulir (#431), petunjuk glob (#434);
**probe rantai lintas repo** (`pilots/chain_probe_v0`, bagian 4e) dengan dua pagar baru: gerbang `scope:no_test_detection` (#436)
dan peringatan tes lama bocor sebelum approve (#437); `verify_at.sh` (#400). Wewenang fast-lane didelegasikan ke Claude
(2026-11-08, bagian 7).

Legenda: `[x]` selesai dan terbukti · `[~]` sebagian (ada untuk jalur tertentu, sisanya belum) · `[ ]` belum dimulai.

## 0. Arah (Atha, 2026-11-15)

**"Spesialis di sifatnya, generalis di permukaannya."** Kekuatan: **"agen yang bisa ditinggal: kerjanya terbukti, biayanya terkunci."**

| Bagian arah | Artinya | Status | Yang belum |
|---|---|---|---|
| **Kerja terbukti** | setiap pekerjaan selesai dengan bukti yang bisa diperiksa: kontrak beku, gerbang, verdict dengan bukti | `[~]` kuat untuk kode (ADR-006) | verdict bisa dipalsukan kode di proses tes (terbukti 2026-11-12; kenari dan nonce belum ada); gerbang non-kode; riset: `SUPPORTED` hanya berarti kutipannya ada |
| **Biaya terkunci** | reservasi sebelum kirim, ledger, cap per job, crash-resume tanpa beli ulang | `[~]` kuat (ADR-004) | cap USD non-Anthropic bertumpu pada perkiraan heuristik; batas E1 (`AGENTS.md`); tanpa idempotency key provider |
| **Bisa ditinggal** | dari issue sampai staging tanpa manusia atau Claude di tengah, selain persetujuan yang disengaja | `[~]` lebih kuat, belum terukur | ada: kenari dan nonce, `argus apply`, antrean PRD bagian A, tahap PRD B1 (`prd check/approve`), penulis PRD B2 (`prd new/reply`), `argus queue`; terbukti n = 1 di dua repo (ledger, athena). Tetap dua gerbang manusia per issue (approve draf, apply patch) dan satu untuk uang (`queue go`); Claude masih menulis issue untuk antrean, memilih keinginan pilot, dan menangkap kesalahan contoh angka di issue (tidak ada gerbang mesin untuk itu); belum diukur (bagian 6 butir 1) |
| **Permukaan generalis** | satu pintu (chat, `127.0.0.1:8711`); kemampuan ditambah satu per satu, hanya bila bisa diberi gerbang atau kartu konfirmasi | `[~]` | chat C1–C4 live (Issue, Riset, Keputusan, Status); kemampuan sesudah kode dan riset belum dipilih |

Arah ini menggantikan "general-purpose agent, dimulai dari deep research" (2026-11-03) dan "coding agent untuk production" (2026-10-28);
keduanya tetap tercatat di bagian 7 sebagai riwayat. Jalur kode adalah tempat sifat itu dibuktikan lebih dulu; riset adalah kemampuan
permukaan, bukan pilar. M4, M7, M8, capability pack dan production tetap ditunda sampai ada bukti kebutuhan. Review arsitektur
2026-11-11 (`docs/reviews/ARCH_REVIEW_2026-11-11.md`) sudah menilai "inti benar, label salah"; arah ini mengganti labelnya.

Yang terjadi sesudah 2026-11-11 (dari `PENDING.md` dan `pilots/`, belum direkonsiliasi terhadap kode): rencana kerja dari review Fable
(`docs/reviews/FABLE_PLAN_2026-11-11.md`); papan skor (#444); FIX-A (#446), FIX-B E2 (#448), FIX-C (#472); eksperimen repo luar tiga
batch di boltons dan more-itertools (`pilots/outside_v0`, `outside_v1`, `outside_v2/batch3`; **vonis fase 2: ditutup 2026-11-15, garis diganti**, bagian 7);
`ReportConflict` MVP (#473), gerbang deteksi tes terminal (#474), verdict bisa dipalsukan TERBUKTI (#475) dan pola forger (#477);
probe "PRD sampai staging" (`pilots/prd_probe_v0`, Stage 18 live); pengerasan verifikasi dan dua grup sandbox (#508, #509); **aplikasi
chat** C1–C4 (`SPEC_CHAT_APP`, #533–#544) yang **menggantikan UI kontrol** di 8711 (`argus-control` dimatikan 2026-11-15).

Yang terjadi sesudah 2026-11-15 (dari `PENDING.md`, `pilots/` dan `verification/`, belum direkonsiliasi terhadap kode): VF O1 kenari dan nonce (#550), `argus apply` (#551-#553), angka papan skor (#554: dari issue sampai staging tanpa campur tangan, batas atas 23,8%, 30 dari 126); **antrean PRD bagian A** (#555, `argus queue`), pilot antrean ledger 3 issue (#556, `pilots/queue_pilot_v0`), Stage 19 live (#557-#558); **tahap PRD B1** (#559, `argus prd check/approve`), environment `athena_py312` (#560); **pilot kedua di repo luar** athena, 3 issue `APPLIED`, $0,1297 (#563, `pilots/queue_pilot_athena`); **penulis PRD B2** (`SPEC_PRD_WRITER` rev 1 #565; PR 1 #566; PR 2 #568, `argus prd new/reply`, `verify_at` PASS 5420, mutan 64/64), PRD pilot 1 (#570, $0,0527), research -> issue -> kode dengan tangan untuk lantai harga Rp1 (#572, $0,2252). Ketiga pilot athena n = 1 dan tidak masuk angka papan skor.

## 1. Milestone

| Milestone | Status | Bukti | Gap yang belum tertutup |
|---|---|---|---|
| M1–M2 harness, LLM nyata, sandbox | `[x]` | `harness/`, `tools/sandbox.py`; arsip `PENDING` | – |
| M3 evaluasi | `[x]` | `docs/reviews/M3_CLOSING.md`; kalibrasi judge (set 3d): baseline #2 2026-10-15 PASS (deteksi 25/25, injeksi 4/4, karangan 6/6, false reject 0, 1 run, belum diuji kestabilan antar run), `docs/reviews/GOOD5_DECISION.md` bagian 6, `docs/reviews/REVIEW_3D.md`, `verification/calibration-3d-*` | Stabilitas antar run kalibrasi (judge tidak deterministik) |
| General-task agent | `[x]` | `codetask/`, `acceptance/`; Eval Set v1 16/16 | Eval Set v1 jenuh: regresi saja |
| **M4** multi-agent dengan dependensi | `[ ]` | Graf riset punya fan-out tanpa dependensi; code task satu agen | Belum ada bukti single-agent menjadi penghalang |
| **M5** observability dan benchmark | `[~]` | Ledger per panggilan; `audit_run.py`, `failure_trace.py`, `pilot_report.py`; keputusan manusia dengan waktunya di `job.json` (#185; `argus-ledger` 014 menampilkannya); `swe_grade.py`; `argus-ledger report` (biaya per stage); jumlah keputusan per pilot di setiap `RESULT.md` | Tracing/dashboard; benchmark single vs multi; **menit kerja Atha** belum ditanyakan; **eval set yang tidak jenuh** |
| **M6** repo → PR | `[x]` MVP | Repo Argus (pilot M6, W2b, router); **sympy** (SWE, bagian 4b); **`argus-ledger`** Python/FastAPI, issue sampai 019 (Stage 17 live, bagian 4c); **`argus-viewer`** JS/React, issue sampai 044 (044 live), vitest di `pwa_node22` (bagian 4c) | Tingkat sukses umum (SWE tanpa bocoran sampel kecil); PR/apply tetap oleh manusia/Claude (disengaja); `argus apply` belum ada; berkas yang dilindungi ditegakkan harness (`.argus/protected`, #270); tes lama tidak bisa diubah agen, tanpa Playwright |
| M7 registry dan policy, MCP | `[ ]` | – | Seluruhnya (ADR-001, sebagian ADR-007). Kandidat: layanan approval bersama `argus apply` atau approve lewat chat (bagian 7) |
| M8 penemuan tool, memori prosedural | `[ ]` | – | Seluruhnya (ADR-003) |
| M9 deployment terkendali | `[~]` (staging) | `argus stage deploy\|rollback\|restart\|check\|status\|monitor\|report` (#244, #246, #249, #251, #258): hanya commit job `APPLIED` apa adanya, container tanpa jaringan/read-only/non-root di Unix socket, peer = pid container, data asli lewat snapshot allowlist, monitor 15 menit, **notifikasi ntfy** sesudah 3 gagal (#259, #260), namespace per direktori staging (#258). **Aplikasi statis** (#257, #261, #263): build tanpa jaringan di `pwa_node22`, cek artifact (A4), `sw.js` dipin, swap `current` atomik sesudah smoke kandidat, proxy `127.0.0.1:8710` GET/HEAD (Host, CSP, `no-store` untuk API, hanya `/sw.js` boleh jadi service worker), unit `systemd --user`. Dua aplikasi, pilot staging #1, upgrade #1, data asli #1, viewer #1–#2; sampai 2026-11-11 ledger Stage 17 (`max_usd`) dan viewer rilis 044 live, snapshot menerbitkan `title` | **Production** (DNS/TLS, pengguna, kredensial): ditunda (keputusan 2026-10-30, pemicu di bagian 7); smoke kandidat tidak menguji lingkungan unit systemd |
| **`argus research`** (deep research, di luar M3–M9) | `[~]` | Planner, worker web berurutan (paralel belum, PENDING), sintesis s1, checker e1, gate G1/G2/G4; DeepSeek Search/Fetch via gateway OpenRouter (#285-#294); eval v0 `deepinfra` 8/8; `argus code --from-research` (#297). Arah resmi 2026-11-03 sampai 2026-11-15; kini kemampuan permukaan, pekerjaan baru menunggu urutan inti (bagian 0, 7) | Ambang v1: job nyata pertama (bagian 4d) lolos sesudah #307-#309 dan #311 (e1 selesai, 0 UNSUPPORTED, 17/17 SUPPORTED); baru satu pertanyaan; pipeline berhirarki (butuh M4, ADR-005) belum dibenarkan oleh bukti |
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
| 006 quality gate | `[~]` (kuat untuk kode) | Kontrak beku, validasi di sandbox, verdict dengan bukti, validasi ulang; penilai SWE dengan tes tersembunyi; staging: smoke dari host, cek artifact, pin service worker; **gerbang `scope:no_test_detection`** (kode produksi yang mengenali pytest/vitest gagal di acceptance, #436; enam regex per baris: pagar, bukan bukti, pola lain lolos); **peringatan tes lama bocor** sebelum approve (penasihat, Python, #437); `argus judge` (saran) | Gate non-kode; peringatan tes lama bocor belum untuk JS |
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
| **`argus-ledger`** (Python, FastAPI, SQLite) | issue 001-019 (Stage 17 live); 25 job kode di scoreboard | $1,0992 untuk 25 job (ledger, job gagal ikut): 19 di-apply, $0,058 per perubahan | 19 applied (as_is), 4 ditolak, 1 ditinggalkan, 1 terbuka; CLI, API, HTML, login + hardening, report, keputusan manusia; di staging dengan data asli; sejak issue 015 draf boleh mengubah tes lama lewat `changed_tests` (K3) |
| **`argus-viewer`** (React 19 PWA, vitest) | issue 001-044 (044 live) + kerangka Claude; 56 job kode di scoreboard | $2,5711 untuk 56 job: 43 di-apply, $0,060 per perubahan | 43 applied (42 sesuai patch yang direview, 1 diubah), 6 ditolak, 7 ditinggalkan; Claude memblok dan memperbaiki beberapa draf dan tes lama sepanjang jalan (shadow batch 1 memblok 2 dari 2; 021 t1; 030/031 `NO_DRAFT`); live di staging, dipakai Atha di HP |

Sejak 2026-11-07 issue ditulis lewat chatbox di HP (penulis Haiku, UI kontrol 8711) dan Claude mereview, meng-apply dan merilis
(jalur cepat didelegasikan, bagian 7). Tiga rilis ledger berturut-turut (Stage 15-17) dan viewer 041-044 memakai rantai ledger → viewer.

**Terbukti (sampel kecil):** fitur nyata dari issue ke rilis staging; per perubahan yang di-apply $0,058 (ledger) dan $0,060 (viewer), job gagal ikut
dihitung (scoreboard); sejak 2026-11-08 approve dilakukan Claude dan "go live" per job tetap dari Atha; jeda tunggu manusia, batas atas,
median 2 menit per tahap; repo JS dengan jaminan red check yang sama.
**Belum terbukti:** task yang tidak dijelaskan rinci oleh Claude (issue ditulis Claude, atau Atha lewat chatbox sejak 2026-11-07; belum ada penulis luar); tanpa review Claude (shadow
mode diusulkan).

## 4d. Riset nyata pertama tahap 1: "Agentic AI" (2026-11-05)

Profil `deepinfra`, cap $1,00 per job. Tiga job, tiap kegagalan dijadikan perbaikan harness di jalur cepat.

| Job | Hasil | Biaya | Penyebab dan perbaikan |
|---|---|---|---|
| `j20261105_104714_120f` | SYNTHESIS_FAILED | $0,0729 | s1: gate URL membaca "Memory berbasis **file:** …" (prosa Indonesia) sebagai skema `file:` di ketiga submit. Fix #307 (`file: x` dengan spasi = prosa; `SubmitReport` v2; verify.sh PASS d99b48d). w1 LangGraph INSUFFICIENT_EVIDENCE: halaman `docs.langchain.com` = satu baris konfigurasi Mintlify 334.421 karakter lalu 3.814 karakter artikel; jatah 48.000 habis di konfigurasi. Fix #308 (baris JSON ≥20.000 karakter dibuang saat fetch; halaman konfigurasi saja disimpan sebagai "no article text"; petunjuk worker: dua part tanpa artikel → cari docs teks) |
| `j20261105_114525_582c` | REPORT_READY, e1 NOT_CHECKED | $0,0737 | w1 kini ANSWERED (artikel 3.847 karakter disajikan). e1: alasan S 360/343/341 karakter (batas 300) membuang semua verdict. Fix #309 (submit terakhir memotong alasan di batas kata; `SubmitCheck` v2) |
| `j20261105_121107_718e` | **REPORT_READY, e1 CHECKED** (submit 1) | $0,0732 | e1: 8 SUPPORTED, 9 PARTIAL, 0 UNSUPPORTED |
| `j20261105_123505_b1d4` | **REPORT_READY, e1 CHECKED** (submit 3, alasan dipotong oleh #309) | $0,0742 | Sesudah #311 (s1 hanya melihat kutipan, bukan klaim worker): e1 **17 SUPPORTED**, 0 PARTIAL, 0 UNSUPPORTED |

**Terhadap ambang v1** (job 3): e1 selesai ✓; tidak ada UNSUPPORTED ✓; SUPPORTED 8/17 = **47%, di bawah 60%** ✗. Claude
mencocokkan alasan PARTIAL e1 dengan sumber: nama yang ada di laporan tetapi di kutipan mana pun tidak (PostgresSaver,
`/memories`, SQLiteSession, `retry_policy=`, "research preview", MCPServerStdio, `interrupt()`) — e1 benar. Penyebab:
s1 menulis detail dari *klaim* temuan (ringkasan worker) atau dari pengetahuannya sendiri, sedangkan e1 menilai hanya dari
kutipan. Job 2 juga punya satu sumber sekunder yang kemungkinan keliru (blog pihak ketiga: rename Claude Agent SDK "awal
2026"); gate tidak bisa menangkapnya karena kutipannya memang ada. "7/8 benar" belum bisa dinilai dari satu pertanyaan.

**Eksperimen #311** (Atha memilih "s1 hanya kutipan" sebelum "model s1 lebih kuat"): job 4, pertanyaan sama, 17/17
SUPPORTED. Cek Claude yang tidak bergantung pada e1: identifier teknis di laporan yang tidak ada di kutipan mana pun turun
dari 27 (job 3: PostgresSaver, SqliteSaver, RedisSession, MongoDBSession, `add_node`, ...) ke 0 (sisanya kata bergaris
miring seperti "read/write"). Penyebab 47% di job 3 adalah klaim worker yang melebihi kutipannya dan disalin s1, bukan
kemampuan model s1 saja. Batas: n = 1 per lengan, worker juga dijalankan ulang (temuan tidak sama persis). Catatan isi:
bagian Claude memakai dokumentasi Claude Code (CLAUDE.md, MEMORY.md), tidak khusus Agent SDK (soal cakupan, bukan
klaim tanpa bukti). Ambang v1 untuk job ini: e1 selesai ✓, 0 UNSUPPORTED ✓, SUPPORTED 100% ✓.

**Dua topik lain** (Atha 2026-11-05: ekonomi dan geopolitik; dipersempit Claude agar bisa dicek), sesudah #311:

| Job | Pertanyaan | Hasil | Biaya |
|---|---|---|---|
| `j20261105_125836_ebbd` | Suku bunga BI dan The Fed sepanjang 2026, kurs rupiah sampai November 2026 | e1 11 SUPPORTED, 2 PARTIAL, 0 UNSUPPORTED (85%); w1 (BI) INSUFFICIENT_EVIDENCE: 4 keputusan BI terverifikasi dari halaman, sisanya hanya di ringkasan pencarian | $0,0601 |
| `j20261105_125836_eca9` | Keanggotaan Indonesia di BRICS Januari 2025 - November 2026 | e1 13 SUPPORTED, 1 PARTIAL, 0 UNSUPPORTED (93%) | $0,0905 |

Cek Claude: semua angka di laporan ada di kutipan (ekonomi 28/28, BRICS 3/3). PARTIAL ekonomi: fakta ada di temuan lain
yang tidak dikutip paragraf itu (salah rujuk, bukan karangan). PARTIAL BRICS: s1 mengambil klaim dari **judul di URL**
sumber (URL tampil di samping kutipan untuk s1). Catatan worker ekonomi: tidak mau mengutip kalimat yang terpotong baris
baru di halaman, padahal G2 menerima kutipan lintas baris. Kebenaran faktual per November 2026 tidak dicek terhadap
sumber independen; "7/8 benar" belum dinilai.

## 4e. Probe rantai lintas repo (2026-11-11, `pilots/chain_probe_v0`)

Pertanyaan (SPEC_CHAIN_PROBE): apa yang dikerjakan manusia sebagai perekat saat satu perubahan melewati dua repo, tanpa planner?
Rantai: T1 ledger meneruskan `max_usd` (Stage 17) → S staging → T2 viewer menampilkan "$X of $Y" (rilis 044). Biaya $0,1987.

| Langkah | Hasil |
|---|---|
| T1 | tiga job: job 1 patch ditolak (agen menaruh `_relax_stale_key_lists()` di kode produksi, bila `pytest` ada di `sys.modules` ia membutakan tes lama yang terkunci; drafter melewatkan `test_title_in_jobs.py`); job 2 `FAILED_ACCEPTANCE` (drafter melewatkan `test_api.py`); job 3 lolos sesudah issue menyebut ketiga file tes. $0,1820 |
| S | Stage 17, tujuh langkah sesuai harapan, 149/149 job nyata punya `max_usd` |
| T2 | draf pertama lolos, 11 langkah agen, tanpa retry; kontrak diambil dari patch T1 yang ter-apply. $0,0167 |

**Temuan:** oper hasil antar repo hampir tanpa gesekan; gesekan ada di tes lama yang bocor oleh fitur baru, dan di agen yang tergoda
mengakali tes terkunci. Dua pagar dibangun: `scope:no_test_detection` (#436, 24/24 mutan) dan peringatan tes lama bocor
(#437, 25/25 mutan; penasihat, Python). Planner berhirarki **tetap tidak dibenarkan**; kandidat berikutnya, bila rantai kedua
menunjukkan pola sama, adalah operator rantai tetap (T1 → apply → S → T2).

## 5. Mode kegagalan (`FUTURE_ARCHITECTURE.md` bagian 8)

| Mode | Status | Bukti / gap |
|---|---|---|
| Crash sebelum/sesudah request | ✓ | ledger, `unknown_after_crash`, tes crash lintas proses; `argus resume` |
| Timeout, rate limit, hasil berbayar ambigu | ✓ | retry transien, tagih kasus terburuk; tanpa idempotency key provider |
| Konflik/overrun budget | ✓ | reservasi sebelum kirim, `FAILED_BUDGET` durable; cap per job; `flock` per job |
| Workflow tidak valid atau siklik | ~ | transisi legal job dan code task; tanpa workflow dengan dependensi |
| Perubahan schema/versi tool | ~ | versi tool dan image di kunci memo; image dipin per job; tanpa registry |
| Dokumen berbahaya, prompt injection | ~ | output sandbox berlabel data; teks dibersihkan dari karakter kontrol; uji v0: empat varian komentar di kutipan riset, n = 1 tiap varian, halaman simulasi, tidak ada yang tembus (#339); 16 rancangan lain di `FABLE_INJECTION_ATTACKS.md` belum dijalankan |
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

1. **Supervisi dan "melepas" Argus** (inti arah 2026-11-15, "bisa ditinggal"; urutan kerja di `PENDING.md`: kenari dan nonce,
   `argus apply`, approve atas patch akhir; angka yang belum ada: persen issue yang sampai staging tanpa campur tangan Claude; **kenari, nonce, `argus apply`, antrean dan penulis PRD sudah ada sejak 2026-11-16**, yang tersisa: angka itu sendiri, gerbang mesin untuk contoh angka di issue, dan penyambung satu-prompt di parkiran): di dua aplikasi latihan Atha menulis issue dari HP (chatbox, Haiku) dan Claude masih
   mereview draf dan patch, meng-apply dan men-deploy (didelegasikan 2026-11-08). Berkas yang dilindungi dipaksa harness
   (#270), `argus judge` memberi saran (J9). Terukur sejak 2026-11-11 (scoreboard): 1,9 keputusan per job kode, jeda tunggu
   manusia batas atas median 2 menit; belum terukur: menit perhatian sebenarnya dan token Claude. Pantau penolakan formulir drafter sesudah #431/#434 dan false positive `leaks` (#437).
2. **Chat sebagai pintu depan** (dulu "UI kontrol interaktif", permintaan Atha 2026-10-30): UI kontrol fase 1-2 diserap aplikasi chat
   (C4, 2026-11-15); approve dari HP (dulu fase 3) dan tombol staging (dulu fase 4) **ditahan**
   (rencana Fable 2026-11-11: dibuka bila Atha menolak 4 dari 5 draf buruk yang ditanam, lewat ringkasan di HP). Terbuka: C5, lalu
   kemampuan permukaan berikutnya (`PENDING.md`).
3. **Operasional staging:** pin image per checkout disalin manual; smoke kandidat tidak menguji unit systemd; up2 selesai
   2026-11-07.
4. **Tingkat sukses di repo luar tanpa bocoran** (SWE, alat regresi ±20% usaha).
5. **Eval set yang tidak jenuh** dan **menit kerja manusia** (M5).
6. **Efek petunjuk berhenti** (#188, #200, #204) terpisah dari variasi model; **pertanyaan B D5**.
7. *(`argus apply` ada sejak 2026-11-15, #553)* **Idempotency key provider**: dampak rendah selama tidak ada aksi eksternal
   selain panggilan model.
8. **M4, M7, M8, capability pack, production**: ditunda sampai ada bukti kebutuhan.
9. **Tes lama bocor oleh fitur baru** (probe rantai, bagian 4e): gerbang `scope:no_test_detection` dan peringatan `leaks` sudah ada;
   sisa: pesan "terjepit tes lama" saat `FAILED_ACCEPTANCE` karena tes terkunci (retry tak menolong), `leaks` untuk JS/vitest,
   ukuran false positive di job nyata (bila tepat: tolak draf dengan jalan keluar), pola deteksi tes yang belum dikenal gerbang.

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

Diputuskan 2026-11-03 (Atha, sesudah membahas "SPEC-001 Router v1, Guarded Autonomy" dengan GPT):
- **Arah berubah ke general-purpose agent**, dimulai dari **deep research**. Menggantikan arah "coding agent untuk production"
  (2026-10-28) sebagai tujuan; aplikasi latihan dan jalur kode tetap berjalan. Usulan Router v1 (planner, policy engine,
  registry worker, replanning) **bukan** spek untuk dikoding: ia menyatakan ulang ADR-001/002/007, M4 dan M7.
- **Planner adalah stage run** (seperti `run_drafter`: `LLMCaller`, reservasi, ledger, memo); router tetap tidak memanggil model.
- **"Go live" tetap ada, satu per job**, mencakup semua stage di dalam cap job (planner, worker, retry, replan). Jatah harian
  tanpa "go live" baru diputuskan sesudah ada data.
- **Plan deep research tanpa `approve`**: dicatat di `job.json`, bisa di-`abandon`. Code task tetap `approve <sha>`. Tindakan
  dengan efek ke luar (kirim pesan, deploy production, transaksi, hapus data) selalu butuh persetujuan manusia.
- **Mulai dari job kind `argus research`** (rencana, worker riset paralel, sintesis dengan sumber, evaluator); Router v1
  lengkap belakangan. Gap menurut urutan:
  - *Sekarang (deep research):* job tanpa repo; tool web search (provider, key, biaya per query masuk cap job, jalur ketat);
    baca web umum (bukan hanya allowlist ReadDocs); isi web sebagai data, worker riset tanpa tool berefek ke luar; gate
    non-kode (klaim menunjuk ke sumber yang benar-benar dibaca, judge); eval set riset kecil yang bisa dicek.
  - *Berikutnya:* planner dengan dependensi (ADR-002, M4); tempat artifact (ADR-005); job gabungan riset + kode.
  - *Ditunda sampai ada bukti kebutuhan:* registry dan policy engine formal (M7), layanan approval di kode (ADR-007,
    bersama UI kontrol), memori (M8), capability pack.

Diputuskan 2026-11-04 (Atha):
- **Provider web: DeepSeek Search/Fetch**; model lewat **gateway OpenRouter** (Vercel cadangan, nanti). Model gratis hanya
  di role tanpa tool yang membaca repo.
- **Eval v0 riset** selesai (#290). Fix yang disetujui ("Ok semua"): checker free di Nemotron (Gemma selalu 429), aturan
  kutipan kalimat utuh, submit terakhir menyimpan temuan yang lolos (#291, #292). Rerun R2/R5/R8 (#293).
- **Output e1 berbayar 32.000** (Atha "Ok 32k"), bukan reasoning `low` atau mati, agar mutu cek tidak turun; batas
  output per stage di `research_job.<stage>.max_output_tokens_by_model` (#294).
- **Ambang v1 `argus research`** (Atha "ambang v1 udah ok"), dinilai pada eval set R1-R8 di profil berbayar: minimal 7/8
  jawaban benar dan tidak ada yang salah; tidak ada item UNSUPPORTED; minimal 60% item SUPPORTED (nilai Claude); e1
  selesai mengecek minimal 7/8 laporan.
- **Batch v1 dilewati**; ambang dan output e1 32k dicek pada job riset berbayar berikutnya.
- **Pipeline saat ini:** alur A (`main.py`/`graph.py`: orchestrator, worker, synthesize, evaluator) hanya regresi; alur B
  `argus code` (r1 opsional, drafter, `approve`, agen, review, `applied`, staging); alur C `argus research` (p1, worker
  web, s1, e1). **Satu pipeline berhirarki** (job → planner → task riset/kode/deploy) dicatat sebagai arah; langkah
  pertama `--from-research` (urutan tetap, tanpa planner): spek disetujui Atha, diimplementasi (`SPEC_FROM_RESEARCH`).

Diputuskan 2026-11-05 (Atha, breakdown arah general-purpose; "1. Ok, 2. Tahap 2, 3. Agentic AI"):
- **Lapisan** (status per 2026-11-05): L0 fondasi (budget, ledger, crash-resume, sandbox, evaluator) `[x]`; L1 kode
  (`argus code`) `[x]` MVP; L2 riset (`argus research`) `[~]`; L3 gabungan (`--from-research`, urutan tetap) `[~]`;
  L4 hirarki (job → planner → task riset/kode/deploy dengan dependensi) `[ ]`; L5 kemampuan baru (gambar, video/audio,
  game, penemuan tool) `[ ]`.
- **Urutan tahap:** 1 → 2 → (3 hanya bila terbukti) → 4.
  - *Tahap 1, buktikan riset:* beberapa job riset berbayar nyata terhadap ambang v1; perbaiki worker free (NO_FINDINGS)
    dan kutipan terpotong; eksperimen e1 `reasoning.effort: low`. Keluaran: angka, bukan klaim.
  - *Tahap 2, kurangi supervisi* (dipilih Atha sebelum UI kontrol): berkas yang dilindungi sudah dipaksa harness (#270);
    sisa: **Reviewer Argus** (model murah menilai draf + patch + hasil tes, berdampingan dengan Claude yang menilai tanpa
    melihat vonisnya; rencana ke Atha sebelum kode), **menit kerja Atha** per pilot, batch shadow dengan issue yang tidak
    dijelaskan rinci oleh Claude.
  - *Tahap 3, pipeline berhirarki:* hanya bila ada issue yang salah dikerjakan lengan tanpa riset, atau pekerjaan gabungan
    yang tidak cukup dengan urutan tetap. Isi: satu spek + 4-6 PR jalur ketat (planner dengan dependensi/M4, oper hasil
    antar task/ADR-005, cap bertingkat dengan ledger dan crash-resume, stop/retry/replan); planner tetap stage run.
  - *Tahap 4, perluasan kemampuan:* satu pack per kali menurut nilai terukur dan kesiapan provider; gate non-kode ADR-006
    dulu; registry dan policy formal (M7) saat jumlah tool membutuhkannya.
  - *Jalur samping:* UI kontrol (fase 1 read-only kapan saja; fase berbayar menunggu scope).
- **Tidak dibangun sekarang:** Router v1 SPEC-001 utuh, memori berlapis (M8), penemuan tool, production.
- **Risiko yang dicatat:** pilot terlalu bersih (issue ditulis Claude, sampel 1-2); riset belum terbukti dibutuhkan oleh
  kode (#298: kedua lengan benar, riset 2× lebih mahal); cap USD non-Anthropic bertumpu pada hitungan heuristik; isi web
  adalah data tidak tepercaya (prompt injection pada code task belum diukur).
- **Riset pertama tahap 1: "Agentic AI"**, dipersempit Claude menjadi pertanyaan yang bisa dicek (pola memory, tool use
  dan recovery di LangGraph, OpenAI Agents SDK dan Claude Agent SDK, per November 2026). Hasil di bagian 4d.
- **Izin sesi 2026-11-05:** perbaikan riset dikerjakan di jalur cepat, termasuk "go live" dan merge oleh Claude, dengan
  `/code-review medium` bila perlu (#307-#309).

Diputuskan 2026-11-07 s.d. 2026-11-11 (Atha):
- **Jalur cepat didelegasikan** (2026-11-08): Claude meng-approve, meng-apply dan men-deploy draf jalur cepat (aplikasi latihan,
  viewer/ledger) sendiri; berhenti pada draf tidak sehat atau jalur ketat. Jalur ketat (uang/ledger, crash-resume, sandbox, key,
  grader, staging): spek, review, mutan, `verify_at`, lalu "merge" Atha ("merge setelah lulus verify" boleh diberikan per PR).
- **"Go live" per `PLAN.md` ter-commit** untuk staging; sejak 2026-11-11 ada izin tetap untuk deploy pull-only tanpa restart,
  staging, uang atau key. Satu "go live" per batch untuk job `argus code` di batch SWE; approve/retry tetap per draf.
- **Urutan verifikasi** (2026-11-11): review (satu subagen Sonnet untuk kode dan keamanan) → mutan + tes yang tersentuh → **satu**
  `verify_at` sendirian (tanpa suite non-sandbox terpisah; catatan lama "CPU berebut membuat exit 137" tidak pernah dibuktikan, lihat `docs/reviews/SPEC_SANDBOX_SPLIT.md` bagian 2) → merge. Log pilot ikut PR fiturnya.
  **Pra-cek tes sandbox** (2026-11-13; ditemukan setelah dua `verify_at` gagal pada kerja APPEND-TESTS): bila sebuah perubahan menambah tes yang memakai
  sandbox Docker, (1) taruh di modul yang sumbernya memuat `SANDBOX NOT AVAILABLE` (lewat fixture `scfg` yang di-skip dengan teks itu di modul yang sama; mengimpor
  fixture dari modul lain tidak cukup), karena `conftest.py` mengelompokkan modul sandbox ke satu grup serial dari **sumber modulnya**; (2) sebelum `verify_at`, jalankan modul
  yang tersentuh **bersama** `tests/test_acceptance_sandbox.py` dengan `-n 4 --dist loadgroup` (sekitar 1 sampai 2 menit, dengan pin image terpasang), karena satu tes di sana
  menuntut bahwa tidak ada kontainer sandbox **milik run itu** yang tersisa (dibatasi per token sejak SPEC_VERIFY_HARDENING, bukan seluruh mesin), dan sebuah tes sandbox yang lepas dari grup tetap bisa membuatnya gagal hanya di rangkaian penuh. Pra-cek
  ini tidak menggantikan `verify_at` dan tidak dijalankan berbarengan dengannya (CPU). Sejak SPEC_VERIFY_HARDENING pra-cek itu satu perintah: `bash scripts/precheck.sh [basis]`
  (sekitar 40 detik; memilih tes dari berkas yang berubah, memasang pin, memakai `-n 4 --dist loadgroup`; `PRECHECK_PRINT=1` hanya mencetak rencananya), dan `conftest.py` mengelompokkan sebuah tes ke grup
  sandbox juga bila fixture yang dipakainya didefinisikan di berkas yang memuat teks itu (daftar modulnya dikunci di `tests/test_xdist_groups.py`, dihitung dari koleksi sungguhan).
  **Dua grup sandbox** (SPEC_SANDBOX_SPLIT): tes sandbox serial **di dalam** tiap grup, bukan lagi satu grup untuk semuanya. `sandbox_a` = tes yang didefinisikan di `tests/test_draft.py`; `sandbox_b` = semua tes sandbox lain (termasuk tes modul lain yang memakai fixture `test_draft`). `VERIFY_SANDBOX_GROUPS=1` mengembalikan satu grup (`sandbox`), nilai lain selain `1` dan `2` ditolak; nilainya dicetak di log. Aturan mundur: satu kegagalan `verify_at` karena batas waktu atau exit 137 di luar daftar-izin tes yang membunuh kontainer dengan sengaja berarti kembali ke `1`.
- **UI kontrol** (`SPEC_CONTROL_UI`, 8711): fase 1-2 live (baca, reject/abandon, chatbox penulis issue); sisa: fase 3 (approve)
  dan 4 (staging), prioritas rendah.
- **Penulis issue** (`SPEC_ISSUE_WRITER`): Haiku 5.5 lewat OpenRouter; harness yang mencari bentrok (`touches`, `clash_check`);
  bentrok berarti tes lama yang **pasti** gagal.
- **Redraft otomatis (3b) ditunda** sampai kasus `submits_exhausted` muncul lagi (Atha 2026-11-11).
- **Probe rantai** (bagian 4e): operator rantai tetap sebelum planner; planner berhirarki belum dibenarkan.
- **Prompt injection:** v0 bersih (#339); tes lanjutan dirancang Fable, voucher reset Fable Atha kedaluwarsa 17 November.

Diputuskan 2026-11-15 (Atha):
- **Arah: "spesialis di sifatnya, generalis di permukaannya"**, dengan kekuatan **"agen yang bisa ditinggal: kerjanya terbukti,
  biayanya terkunci"** (bagian 0). Menggantikan arah 2026-11-03 (general-purpose agent, dimulai dari deep research) dan 2026-10-28
  (coding agent untuk production). Alasan yang dibahas: jaminan Argus baru kuat untuk kode; lebar bukan tempat bersaing; riset belum
  terbukti dibutuhkan kode; planner tiga kali diuji tetap tidak dibenarkan; Atha ingin daya saing sekaligus enak untuk pekerjaan
  sehari-hari, yang dijawab dengan memisahkan sifat (inti) dari permukaan (chat).
- **Lapisan 2026-11-05 dibaca ulang:** L0 fondasi dan L1 kode = inti; L2 riset dan L3 gabungan = kemampuan permukaan; L4 hirarki dan
  L5 kemampuan baru = ditunda sampai ada bukti. Urutan tahap 1–4 (2026-11-05) tidak berlaku lagi.
- **Yang tidak lagi berkaitan diarsipkan:** `PENDING.md` ditulis ulang, salinan utuh di `reviews/PENDING_ARCHIVE_2026-11-15.md`; daftar
  yang diarsipkan ada di bagian "Diarsipkan 2026-11-15" `PENDING.md`.
- **Waktu kerja Atha:** kurang lebih 8 jam per hari, tergantung limit Claude. Angka "4 jam per minggu" di rencana Fable 2026-11-11
  diketik asal dan tidak berlaku (jadwal bagian 8 rencana itu ikut tidak berlaku).
- **UI kontrol dipensiunkan**, diserap aplikasi chat (C4): chat di `127.0.0.1:8711`, `argus-control` dimatikan.

- **Vonis fase 2, eksperimen repo luar (boltons, more-itertools): fase ditutup, garisnya diganti** (Atha memilih pilihan 3 dari tiga:
  sukses, gagal menurut rubrik, ganti garis). Dicatat sebagai **"benar menurut tes, belum rapi menurut rubrik"**: tes pemelihara 6 dari 8
  (batch 2) dan 6 dari 6 (batch 3); nilai buta batch 2 A1 B6 C1, batch 3 B semua; batch 1 dari 7 issue sah 6 A 1 C bila artefak mode
  diabaikan, 2 A bila dihitung (`pilots/outside_v0/RESULT.md` adendum 2026-11-13 dan 2026-11-15). Bukan "sukses", bukan "gagal". Garis
  A/B/C untuk 10 issue tidak dipakai lagi; **ukuran pengganti: persen issue yang sampai staging tanpa campur tangan Claude** (belum
  diukur). Yang dulu menunggu vonis (antrean "PRD sampai staging", operator rantai, pekerjaan baru di jalur riset) kini menunggu urutan
  inti di bawah.

- **Urutan inti** (Atha 2026-11-15, memilih "Terima urutan" dari empat pilihan: terima, `argus apply` dulu, permukaan dulu, bahas
  dulu): VF O1 kenari dan nonce → `argus apply` → antrean PRD; di permukaan: assistant atas Argus sendiri. Antrean PRD dibuka sesudah
  kenari, nonce dan `argus apply`. Operator rantai dan pekerjaan baru di jalur riset tidak ada di urutan itu dan tetap tidak dimulai.
- **Aturan main arah** (Atha 2026-11-15, memilih "2 minggu, 1 hari"): (1) satu angka di repo, persen issue yang sampai staging tanpa
  campur tangan Claude; (2) arah hanya diubah di titik cek tetap **tiap 2 minggu, pertama 2026-11-29**, ide di antaranya masuk parkiran
  di `PENDING.md`; (3) jatah eksplorasi permukaan **1 hari per minggu** (dihitung dengan kurang lebih 8 jam per hari; usul lama 1 dari
  4 jam tidak berlaku); (4) log permintaan yang chat belum bisa di `PENDING.md`, kemampuan berikutnya dipilih dari log itu di titik cek.
- **"Daya saing" untuk siapa** (Atha 2026-11-15, memilih "Portofolio/karier"): bukti dan angka cukup; production dan pengguna kedua
  tetap ditunda. Bisa dibuka lagi di titik cek.
- **Peninjau jalur ketat: sementara Opus sejak 2026-11-16 (Atha: "Ganti reviewer ke opus bro, limit fable gw hampir abis"); kembali ke Fable bila limitnya pulih dan Atha bilang.** Aturan lama di bawah:
  **Peninjau jalur ketat (Atha 2026-11-15: "Reviewer pake fable aja 1"):** satu peninjau, Fable, untuk spek dan diff jalur ketat (Opus tidak lagi diminta). Dasarnya tiga sampel Opus dan Fable
  atas artefak yang sama (spek VF O1, diff VF O1, spek `argus apply`): hampir semua temuan keduanya nyata dan diverifikasi dengan menjalankan, masing-masing menemukan hal yang tidak ditemukan
  yang lain (n = 3, bukan kesimpulan statistik); Claude menyarankan keduanya, Atha memilih satu. Dikaji lagi di titik cek 2026-11-29 dengan jumlah temuan unik per PR.
- **`argus apply` (Atha 2026-11-15: "K1-k7 setuju ... Merge semua PR. Langsung lanjut"):** spek `docs/reviews/SPEC_ARGUS_APPLY.md` rev 2 disetujui (K1 `--read-sha` wajib; K2 HEAD sama dengan `intake.commit`, tanpa
  `--onto-descendant`; K3 commit di cabang aktif; K4 tanpa push, merge atau deploy; K5 hook, filter, fsmonitor dan gpg tidak berjalan, konfigurasi lokal di luar daftar putih ditolak; K6 kartu chat menyusul; K7 dua PR:
  PR 1 memperbaiki `applied()` dan mencatat sha patch, PR 2 `argus apply`). Merge kedua PR diizinkan sesudah `verify_at` lulus.


Diputuskan 2026-11-16 (Atha):
- **Penulis PRD (B2), D5-D9** ("Ok setuju. Langsung merge aja kalo udah ok"): terminal dulu, halaman chat belakangan; model = role `issue_writer` (Haiku 5.5); `max_items` 5; giliran $0,30 dan job $1,50 (tebakan, diukur); selama tiga PRD pilot pertama Claude tidak menulis issue antrean. "Merge kalau sudah ok" berlaku untuk PR 1 dan PR 2 sesudah `verify_at` PASS dan tinjauan Fable.
- **Pilot di repo luar (athena)** dijalankan dengan batas $3,00 (antrean) dan $1,00 (PRD pilot); Atha menyetujui tiap draf dan tiap apply. Satu perubahan kecil memakai penulis issue biasa, bukan PRD ("kalau gitu pake issue biasa juga bisa ya").
- **Dicatat dulu, tidak dikerjakan:** environment node untuk repo dengan frontend; kegagalan provider pada job `prd` jadi `WRITE_FAILED` (bukan `BLOCKED`); **penyambung satu-prompt** ("sekali nulis prompt langsung bisa semua kerja": research -> penulis -> antrean, berhenti hanya di gerbang manusia; tempatnya terhadap arah: kelanjutan "bisa ditinggal", spek menunggu angka dari pilot); pengingat memeriksa ARB 2 Januari 2027.
- **Perbaikan arah, bukan perubahan arah (Atha 2026-11-16: "ini masuknya perbaikan arah bukan merubah arah hehe"): tahapan "tanpa pusing Atha".** Ukuran "bisa ditinggal" diperbaiki dari "persen issue tanpa campur tangan Claude" ke (1) peran **Claude sebagai operator** per job yang harus menyusut, dipisah dari peran **Claude sebagai pembangun Argus** (diagnosis, jalur ketat, environment, firewall), dan (2) **Atha menilai kartu dengan benar** (uji 4 dari 5 kartu cacat-ditanam, dari HP). Tahap: T1 gerbang contoh yang bisa dijalankan, T2 kartu baca-saja di chat, T3 uji kartu cacat-ditanam (menggantikan "uji lepas tangan" yang menyuruh Atha membaca patch), T4 kartu aksi sesudah T3 lulus, T5 penyambung satu-prompt, T6 `argus env init`, node, repo baru; tanpa repo baru sampai T6. Rincian dan syarat keluar di `PENDING.md` Inti 2. Yang tetap jujur: contoh membuktikan perilaku, bukan bahwa kodenya bersih; pembaca patch tetap Claude, dicatat sebagai tahap.
- **Operasional:** port 443 di firewall mesin ini dibuka (aturan `iptables` dan satu baris di `/etc/iptables/rules.v4`) karena PWA athena memberi `no-response`; security list di konsol Oracle belum diperiksa.

Menunggu keputusan Atha (rinci di `PENDING.md`):
1. *(selesai 2026-11-15: vonis fase 2, urutan inti, aturan main arah, "daya saing" untuk siapa; lihat di atas)*
2. **Approve dari HP lewat chat** dan tombol staging (dulu UI kontrol fase 3 dan 4): ditahan, prioritas rendah.
3. **Operator rantai tetap** (`argus chain`) dan **redraft otomatis (3b)**: menunggu rantai lintas repo kedua dan kasus
   `submits_exhausted` berikutnya.

Diputuskan 2026-11-21 (Atha):
- **Izin sesi diperbarui:** auto-merge PR jalur ketat sesudah semua gerbang (tinjau Opus, mutan sekali, precheck, satu `verify_at` PASS dari baris `RESULT:` terakhir, "sandbox tests skipped: 0", pin image) dan restart `argus-chat.service` sesudah merge; tidak mencakup pilot berbayar atau perubahan batas config.
- **Dibangun (jalur ketat, semua ter-merge):** `argus apply --accept-concerns "ALASAN"` (#650), uang antrean (#651: job APPLIED dihitung sebesar biaya nyata, petunjuk di kartu STOPPED), dua slot kunci chat (#653: kunci kode OpenRouter, kunci riset DeepSeek, kunci penulis OpenRouter, atas drop-in Atha), tingkat `blocker`/`nit` di pembaca patch (#654; uji cacat tanam LULUS, tetapi tidak ada bacaan `nit` di uji itu: efek pada sudut remeh dari job nyata belum terukur), P2a PRD dari chat (#660).
- **T6 dan bulking-app:** spek T6 `SPEC_T6_ENV_BUILD` rev 1 ditulis dan ditinjau (lima PR; hanya PR1 pengerasan builder yang direkomendasikan; **tidak dibangun**: Atha mempertanyakan proporsinya terhadap proses membangunnya; Claude: tunda PR2-5 sampai ada repo Python dengan dependensi nyata). Repo privat bulking-app (React 18, Vite) dipakai sebagai pilot luar pertama untuk frontend: environment `bulking_node22` (#656: Vite 6 + vitest 3 karena harness memakai `configLoader runner`), pendaftaran (#657), kerangka tes di repo Atha (PR #3), satu issue dari PRD sampai PR #4 tanpa retry, biaya sekitar $0,015. Atha mengizinkan kode repo privat itu ke model lewat OpenRouter. **Celah:** `argus apply` menolak berkas tes baru yang cocok dengan `.argus/protected` (`*.test.*`) padahal SPEC_PROTECTED_FILES P3 mengizinkannya; sementara apply manual (`git apply` + `argus applied`); perbaikan jalur ketat dicatat di PENDING.
- **Arah, hanya dicatat:** (a) kemampuan Argus seperti operator (buka PR, merge untuk repo pilot terdaftar, browser hanya-baca; urutan usul Claude); (b) **mandor di chat** (ngobrol, usulan rute ke riset atau PRD, kartu langkah berikutnya; `SPEC_CHAT_MANAGER` rev 1, tinjau Opus GO WITH CHANGES, enam PR) **diparkir sampai titik cek 2026-11-29** atas kata Atha ("masuk parkiran ... gw mencoba komitmen"), kecuali P2a yang sudah dibangun; (c) planner berhirarki tetap tidak dibenarkan bukti (tiga probe); (d) `--web` (ReadDocs untuk agen kode, host di `web.hosts`) dan `argus research` adalah dua hal berbeda dan bukan browser.
