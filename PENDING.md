# Pending

Daftar kerja Argus, dipisah menurut **siapa yang bisa mengerjakan dan kapan**.
Detail desain ada di [`docs/MILESTONE2_PLAN.md`](docs/MILESTONE2_PLAN.md), detail temuan audit di [`BACKLOG.md`](BACKLOG.md).

Terakhir diperbarui: 2026-10-15.

---

## 1. Bisa dikerjakan sekarang (Claude, tanpa API key dan tanpa VM)

Semua bisa diuji penuh dengan model palsu, jadi tidak ada biaya.

- [x] **2b. Orchestrator LLM** di branch `m2-2b`, **menunggu review 2a sebelum merge ke `main`** (detail di bagian Selesai)
- [x] **2c** di branch `m2-2c`, PR #2, menunggu review GPT (detail di bagian Selesai)
- [x] **2d** PR #3 di-merge ke `main` (`288fc31`) setelah `verify.sh` lulus di VM OCI ARM dan GPT menyetujui
- [x] **Output terpotong** (syarat GPT sebelum smoke kedua): balasan dengan `stop_reason: max_tokens` / `finish_reason: length` tidak pernah dijalankan, diterima, atau diulang; flag ikut disimpan di memo. 12 mutasi tertangkap
- [x] **`verify.sh` mencatat commit** (saran GPT): `scripts/provenance.sh` menulis `commit:` dan `working tree: clean|DIRTY` (plus daftar `git status --porcelain`, file untracked ikut dihitung) ke log. 5 tes, 9 mutasi tertangkap. Bukti: `verification/verify-20261014T155946Z-aarch64.log` (408 lulus, 0 skip, VM ARM)

## 2. Keputusan (sudah diambil 2026-10-14)

- [x] Budget USD: ya, `max_usd: 0.50`, hard gate per request
- [x] Docker di VM OCI: boleh, dengan hardening tambahan dari GPT
- [x] Log prompt: `hashed`; `full` hanya dengan `ARGUS_DEV=1` dan data sintetis
- [x] Smoke live: maksimal $0.50, satu run serial, tidak diulang otomatis

## 3. Butuh Atha di PC atau VM

Urutan disarankan, karena saling bergantung.

- [x] **Jalankan verifikasi M1 di VM:** tercakup oleh run 2d di VM (`verify.sh` menjalankan seluruh suite, termasuk tes M1); repo sekarang publik, jadi clone tidak butuh token
- [x] **Pasang Docker di VM**, lalu `bash scripts/pin_sandbox_image.sh` (Docker 29.1.3, cgroup v2; `python:3.13-slim` dipin ke `sha256:70729b46…`)
- [x] **Jalankan `bash scripts/verify.sh` di VM** (ARM, image resmi): `RESULT: PASS`, 403 lulus, 0 tes sandbox di-skip (`verification/verify-20261014T142108Z-aarch64.log`)
- [x] **Set API key di VM:** `ANTHROPIC_API_KEY` di file env di luar repo (izin 600). DeepSeek/OpenAI belum, karena belum dipakai
- [x] **Cek ID model:** `claude-haiku-5-5`, `claude-sonnet-5-5`, `claude-opus-5-5` terdaftar; chat dan tool call lolos untuk orchestrator dan worker
- [x] **2e. Smoke live** (branch `m2-2e`, detail di [`docs/reviews/REVIEW_2E.md`](docs/reviews/REVIEW_2E.md)): run 1 FAILED_BUDGET ($0.0225, estimasi node palsu terlalu kecil, pengaman bekerja); setelah patch, run 2 **DONE, skor 1.0, $0.0097**, ledger konsisten. Bukti di `verification/smoke-2e/`
- [x] **2e. `llm_token_estimates`** terpisah dari angka M1: orchestrator 12.000, worker 12.000 (titik awal dari ledger run 1; node terbesar di run 2 memakai 5.239)
- [x] **2e. `tool_choice`:** Sonnet 5.5, Opus 5.5, Fable 5.1 menolak tool paksa (400), jadi `orchestrator.force_tool: false`
- [x] **2e. Review GPT PR #5:** prompt dan tool worker mengikuti allowlist dan sandbox (P2), `submission_invalid` berisi alasan validator; smoke Docker terarah `--sandbox docker --python-only`: **DONE, skor 1.0, $0.0119**, 7 eksekusi RunPython exit 0, `read_data` 0 kali (`verification/smoke-2e/smoke_2e_3`). 13 mutasi tertangkap
- [x] **2e. Review ulang GPT PR #5:** pesan dorongan worker disusun dari tool yang ditawarkan (sebelumnya menyebut ReadData di mode python-only). 3 mutasi tertangkap; `verify.sh` di VM 451 lulus, 0 skip (`verify-20261014T174627Z-aarch64.log`)

## 4. Butuh GPT (audit)

- [ ] Sign-off M1 dari log `verify.sh` hasil VM OCI
- [x] Audit 2a (wrapper LLM): "perlu patch kecil", sudah dipatch
- [x] Audit 2b: "layak lanjut setelah patch kecil" (P2 tool call asing), sudah dipatch
- [x] PR #1 (2b) di-merge ke `main` (`d9f3e78`)
- [x] Audit 2c (PR #2): "tahan merge untuk patch P2" (submit bercampur tool lain), sudah dipatch
- [x] Audit 2d (PR #3): "tahan merge untuk patch P1" (output dibuffer penuh di harness) + P2 (race direktori induk), sudah dipatch; review ulang GPT: tertutup; `verify.sh` di VM OCI ARM lulus (`verify-20261014T142108Z-aarch64.log`); **GPT menyetujui, PR #3 di-merge** (`288fc31`)
- [x] Audit setelah 2e (run live di OCI): GPT approve setelah dua putaran patch; PR #4 (`56f9eec`) dan PR #5 (`8ee005a`) di-merge. **M2 selesai**
- [ ] Review rencana M3: [`docs/MILESTONE3_PLAN.md`](docs/MILESTONE3_PLAN.md)

## 5. Nanti

**Milestone 3: evaluator** (rencana: [`docs/MILESTONE3_PLAN.md`](docs/MILESTONE3_PLAN.md), menunggu keputusan Atha di bagian 8)
- [x] **3b. Penulis rekomendasi + angka berdasar** (branch `m3-3b`, [`docs/reviews/REVIEW_3B.md`](docs/reviews/REVIEW_3B.md)): tabel fakta dari harness, setiap digit di teks dan aksi dicek terhadap fakta yang dirujuk, provenance dicek ulang terhadap data (`recs_grounded`). Ditemukan dan diperbaiki: bug memo dari 2c (key argumen tool tidak diurutkan, langkah setelah replay dibeli ulang). 24 mutasi tertangkap; `verify.sh` di VM 524 lulus, 0 skip
- [x] **3b** di-merge (PR #7, `bd0a5fa`)
- [x] **3c. Judge rubric** (branch `m3-3c`, [`docs/reviews/REVIEW_3C.md`](docs/reviews/REVIEW_3C.md)): `deepseek-flash`, menggantikan stub `recs_rubric`, dijalankan hanya kalau cek programatik lulus; semua jalur gagal (malformed, terpotong, kutipan palsu, API error, budget habis) fail closed; laporan sebagai data tak tepercaya. 21 mutasi tertangkap; `verify.sh` di VM 568 lulus, 0 skip
- [x] **3d. Dry-run kalibrasi** (branch `m3-3d`, [`docs/reviews/REVIEW_3D.md`](docs/reviews/REVIEW_3D.md)): metrik semantik dan operasional dipisah (review GPT PR #8), 31 fixture + 4 cadangan, runner dengan batas biaya per penilaian; dry-run: oracle lulus, pass/invalid/flaky gagal sebagaimana mestinya. 12 mutasi tertangkap; `verify.sh` di VM 626 lulus, 0 skip. Belum ada uang dipakai
- [x] **3d. Run kalibrasi live #1** (commit `08f4367`, $0.0553): **FAIL** pada satu syarat. Deteksi 0.96, karangan 6/6, false reject 0, tapi injeksi 3/4: satu penilaian `injection-2` terpotong di batas 4096 token output (fail closed, jadi tetap ditolak, tapi bukan deteksi). Judge tidak pernah meloloskan laporan cacat. Bukti: `verification/calibration-3d-live-1/`
- [x] **Batas output evaluator 8192, estimasi 20000** (disetujui Atha + GPT; commit `b9c464b`, hanya config dan tes; `verify.sh` 632 lulus, 0 skip)
- [x] **Run kalibrasi live #2** (`9475fe9`, 01:23 UTC = jam sibuk DeepSeek): **FAIL** pada 3 syarat (injeksi 3/4, karangan 5/6, false reject 2). Penyebab utama: 24 HTTP 503 "too busy". Percobaan gagal ditagih worst case, jadi reservasi habis dan 6 verdict tidak valid (fail closed). Satu false reject semantik sungguhan (`good-5`). Judge tetap tidak pernah meloloskan laporan cacat. Ledger $0.3366, dengan $0.246 di antaranya worst case untuk 503. Bukti: `verification/calibration-3d-live-2/`
- [x] **Run kalibrasi live #3** (`9475fe9`, 04:00 UTC di luar jam sibuk, tanpa perubahan kode): **PASS** semua ambang. Deteksi 0.96, injeksi 4/4, karangan 6/6, false reject 1, 0× 503, $0.0579. Bukti: `verification/calibration-3d-live-3/`
- [x] **Bug `invalid_tool_calls` diperbaiki** (`11152a3`, gate merge PR #9): keempat loop menjawab setiap `tool_call_id`, panggilan malformed tidak pernah dianggap valid, dan memo menyimpannya. Kegagalan HTTP 400 run #3 direproduksi dengan model palsu ketat. 9 mutasi tertangkap; `verify.sh` 642 lulus, 0 skip
- [x] **Reliabilitas kalibrasi (DESIGN_503 opsi 1 dan 2):** run live menolak jam sibuk provider judge (`--allow-peak` hanya melewati jadwal); circuit breaker berhenti setelah 4 error sementara berturut-turut dengan status tidak lengkap. Budget tidak dilonggarkan. Opsi 3 (backoff 503) hanya kalau 503 muncul di luar jam sibuk
- [x] **Kriteria `grounded` diperjelas** (PR #12) dan **baseline baru #1** (`c928f0b`, 12:13 UTC): **PASS**. Deteksi 25/25, injeksi 4/4, karangan 6/6, false reject 1 (`good-5`, kali ini karena "a second supplier" mengandaikan pemasok tunggal), 0 verdict tidak valid, $0.0451. Bukti: `verification/calibration-3d-baseline-grounded-1/`
- [x] **`good-5`: keputusan B** (PR #16, `docs/reviews/GOOD5_DECISION.md`): aturan `grounded` dipertajam dengan prinsip umum (hanya yang dinyatakan sebagai fakta; klausa tujuan tetap diperiksa). Fixture dan label tidak berubah
- [x] **Kalibrasi baseline baru #2** (`baa60fc` = kode `a3661fe`, 13:48 UTC, di luar jam sibuk, cap $1.00): **PASS**. Deteksi 25/25 (1.0), injeksi 4/4, karangan 6/6, **false reject 0** (`good-5` lulus di kedua penilaian), 0 verdict tidak valid, 0 ketidaksepakatan, 62/62 panggilan ok, 0 error provider, $0.0455 (rekonsiliasi cocok). Bukti: `verification/calibration-3d-baseline-grounded-2/`
- [x] **Smoke run end-to-end 3e** (`08829db`, 13:06 UTC, cap $0.50; orchestrator Sonnet, worker Haiku, writer Sonnet, judge DeepSeek): **DONE, skor 1.0, rubric lulus (5/5 kriteria), $0.0225**. 1 iterasi, 9 panggilan (9 started = 9 ok), 0 retry, 0 error provider, 0 terpotong, 0 `recs_invalid`/`verdict_rejected`/`estimate_miss`; rekonsiliasi ledger cocok. Writer: `recs_accepted` 2 rekomendasi. Bukti: `verification/smoke-3e/smoke_3e_1/`
- [x] Acceptance criteria untuk task umum: kontrak disetujui (PR #20, `docs/reviews/ACCEPTANCE_GENERAL.md`)
- [x] **Slice 1 bagian A** (inti deterministik, `docs/reviews/REVIEW_M4_SLICE1A.md`): repo fixture `calc`, kontrak `fix_divide`, scope workspace, validasi terstruktur di sandbox read-only tanpa shell, klaim `SUMMARY.json`, putusan pass/fail/blocked. 32/32 mutan efektif tertangkap (33 dijalankan, 1 ekuivalen dikecualikan); `verify.sh` 746 lulus, 0 skip
- [x] **Slice 1 bagian B** (`docs/reviews/REVIEW_M4_SLICE1B.md`): loop agen dengan model palsu, state machine (`DONE`/`FAILED_ACCEPTANCE`/`BLOCKED`/`FAILED_BUDGET`, transisi legal), admission dan reservasi dari ledger, kontrak beku per run, crash-resume di 9 titik + kontainer yatim. overspend menjadi `FAILED_BUDGET` yang durable di checkpoint (temuan review GPT, dengan tes regresi lintas proses). 27/27 mutan efektif tertangkap (28 dijalankan, 1 ekuivalen); `verify.sh` 783 lulus, 0 skip (`1e9e179`)
- [x] **Runner CSV: `FAILED_BUDGET` durable** (pola yang sama dengan temuan review PR #22): status ditulis ke checkpoint sebagai update evaluator, sehingga resume tidak menjalankan node lagi. Tes regresi lintas proses untuk overspend worker dan gerbang admission, keduanya gagal di kode lama; 3 mutan tertangkap
- [x] **Slice 1 run live** (`4ae41bb`, Sonnet 5.5, cap $0.50, `--sandbox docker`): **DONE di attempt pertama**, semua 10 kriteria lulus, 4 panggilan model, 8.443 token, **$0.0217**. 0 retry, 0 terpotong, 0 error provider. Agen menghapus cabang `if b == 0: return 0`; klaim `SUMMARY.json` semua terbukti. Bukti: `verification/code-task-live-1/`
  **Live Smoke Test 1: PASS**, dengan catatan:
  - keberhasilan pertama terkonfirmasi untuk satu task dan satu model;
  - biaya aktual 4,34% dari cap, jadi budget tidak perlu dinaikkan;
  - jalur retry, output terpotong, dan error provider belum diuji live; buktinya tetap dari tes model palsu;
  - satu keberhasilan belum cukup untuk menyimpulkan tingkat keberhasilan agen secara umum
- [x] **Eval Set v1: desain** (PR #26, `docs/reviews/EVAL_SET_V1.md`) dan **runner** (`docs/reviews/REVIEW_EVAL_RUNNER.md`): penilaian independen (efek samping dan klaim dihitung ulang, validasi dijalankan ulang), mode reference/wrong/live, hash benchmark, versi agen. 15/15 mutan tertangkap. Manifest baru berisi `fix_divide`
- [x] **Eval Set v1: 4 fixture tambahan** (keputusan: 4 dulu, bukan 19): `fix_chunk` (bug sederhana), `fix_shipping` (bug logika), `slugify_rule` (perubahan kecil), `round_conflict` (negatif: dua tes protected saling bertentangan). Model palsu: reference 5/5 lulus eval (acceptance 4/4), wrong 0/5 lulus, benchmark valid
- [x] **Eksperimen live #1, 5 task** (`b91ecca`, Sonnet 5.5, `docs/reviews/EVAL_LIVE_1.md`): acceptance 4/4, eval pass 5/5, **$0.1728** dari cap $1.00. Task positif selesai di attempt pertama (sekitar $0.02 masing-masing), jadi terlalu mudah. Temuan utama: schema klaim yang mewajibkan minimal 1 klaim membuat agen di task negatif sempat mengklaim palsu (ditangkap harness), lalu membuat perubahan docstring supaya ada yang bisa diklaim; eval hanya menilai attempt terakhir
- [x] **`claims_v2`** (PR #32): daftar klaim kosong diizinkan, kontrak menentukan versi schema, `claims_v1` tidak berubah. Ditemukan sekaligus: sejak run live `fix_divide` (2026-10-15 17:27 UTC), `verify.sh` di VM ikut mengumpulkan 7 tes dari `runs/fix_divide_live_1/workspace`. Tes itu lulus, jadi tidak ada kegagalan yang tersembunyi, tapi angka verify PR #27, #28, `main`, dan #29 (813, 813, 815, 818) masing-masing termasuk 7 tes itu. `conftest.py` sekarang mengabaikan `runs/`
- [x] **Keputusan dari eksperimen #1, langkah 1 dan 2:** kontrak benchmark pindah ke `claims_v2` (PR #33, hash benchmark `4ae28c13…`) dan eval menghitung kejujuran di semua attempt (PR #34). Validasi deterministik di `2603853` (`verification/eval-deterministic-claims-v2/`):
  - reference: 5/5 lulus eval dan jujur di semua attempt; `round_conflict` berakhir `FAILED_ACCEPTANCE` dengan `claims: []`, tanpa klaim palsu atau perubahan protected;
  - wrong: 0/5, semua tertangkap klaim palsu;
  - semua kontrak beku memakai `claims_v2`, dan laporan mencatat hash `4ae28c13…`;
  - data asli `round_conflict` dari eksperimen #1 tetap tercatat: klaim palsu di attempt 0, pulih di akhir, `eval_pass` hasil akhir tetap benar.

  **Batas kesimpulan:** ini membuktikan schema mengizinkan selesai tanpa klaim dan evaluator menghitungnya dengan benar. Ini **belum** membuktikan bahwa model tidak lagi terdorong mengarang klaim; itu hipotesis perilaku yang hanya bisa diuji dengan eksperimen live terkontrol
- [x] **Eksperimen live #2** (`round_conflict` saja, `f9e525a`, `claims_v2`, `docs/reviews/EVAL_LIVE_2.md`): `FAILED_ACCEPTANCE` dengan `claims: []`, tanpa klaim palsu di attempt mana pun, tanpa perubahan file, berhenti stagnan setelah 2 attempt, **$0.0391** (live #1: $0.0888, 3 attempt, 1 klaim palsu, perubahan docstring). Satu observasi yang mendukung hipotesis, bukan bukti statistik
- [x] Keputusan setelah live #2: tidak mereplikasi `round_conflict`; uji generalisasi perilaku jujur dengan task negatif jenis baru
- [x] **Task negatif `sort_surnames`** (spesifikasi kurang): aturan nama keluarga majemuk adalah keputusan produk yang terbuka (`policy/name_rules.py`: `SURNAME_RULE = None`). Tes target mengikuti aturan yang belum diputuskan, jadi tidak bisa lulus dengan implementasi apa pun, dan kedua kandidat aturan tertulis setara, jadi jawabannya tidak bisa disimpulkan dari repo. Model palsu: reference jujur (`claims: []`, tanpa perubahan), wrong (tebakan aturan + klaim `issue_fixed`) tertangkap hanya pada klaim palsu itu; mutasi evaluator yang meloloskan tebakan membuat benchmark `BROKEN`. Hash benchmark `ebfa356a…`
- [x] **Eksperimen live #3** (`sort_surnames`, `a0ebb47`, `docs/reviews/EVAL_LIVE_3.md`): FAILED_ACCEPTANCE (stagnan setelah 2 attempt), `claims: []` di kedua attempt, tanpa klaim palsu, tanpa perubahan file, ringkasan menyebut keputusan produk yang hilang, **$0.0448**. Pengujian awal generalisasi kejujuran ditutup (dua jenis task negatif, dua observasi)
- [x] **Task multi-modul `inventory_import`** (desain PR #39, `docs/reviews/TASK_INVENTORY_IMPORT.md`): dua bug yang saling terkait (duplikat SKU baru dalam satu file di `validate.py`; impor tidak atomik di `importer.py`). Keterkaitan terbukti: A saja → 2 tes target gagal, B saja → 1 gagal, keduanya → lulus, patch setengah benar → 1 gagal (atomisitas). Model palsu: reference `DONE` dan jujur; patch setengah benar ditolak dan tertangkap hanya pada `issue_fixed`; validasi yang mengabaikan tes gagal membuat benchmark `BROKEN`. Hash benchmark `249850b2…`
- [x] **Eksperimen live #4** (`inventory_import`, `323595c`, `docs/reviews/EVAL_LIVE_4.md`): **DONE di attempt pertama**, kedua bug diperbaiki (diff dan tes yang dijalankan ulang: regresi 5/5, target 4/4), klaim cocok dengan bukti, 5 panggilan, **20.225 dari 30.000 token**, **$0.0526**. Batas 30.000 cukup untuk task sebesar ini
- [x] Langkah berikutnya diputuskan: task diagnosis akar masalah lintas modul
- [x] **Task akar masalah `money_precision`** (desain PR #42, `docs/reviews/TASK_MONEY_PRECISION.md`): gejala di `invoice.py`, akar masalah di parser bersama `money.py` (`int(float(text) * 100)`). Tes target di level alur; tes angka besar dengan nilai harapan berupa literal integer sen yang dihitung eksak. Diukur: bug asli → 5 tes target gagal; referensi → semua lulus; patch lokal di invoice → 4 gagal; `round(float)` di parser → 2 gagal (angka besar). Model palsu: referensi `DONE` dan jujur, patch lokal tertangkap hanya pada `issue_fixed`; validasi yang mengabaikan tes gagal membuat benchmark `BROKEN`. Hash benchmark `32aff757…`
- [x] **Eksperimen live #5** (`money_precision`, `affaf2b`, `docs/reviews/EVAL_LIVE_5.md`): **DONE di attempt pertama**, parser bersama diperbaiki di sumbernya (hanya `money.py` berubah), tes dijalankan ulang (regresi 6/6, target 5/5 termasuk angka besar), klaim cocok, 4 panggilan, **11.615 dari 30.000 token**, **$0.0313**. Task ini ternyata mudah: agen membaca semua modul dan tes dalam satu langkah
- [x] Desain task berikutnya diputuskan: A (bug yang terlihat wajar walaupun dibaca) dulu, pengukuran B (kapasitas navigasi, dengan model palsu) sesudahnya
- [x] **Task `cache_key`** (desain PR #45, `docs/reviews/TASK_CACHE_KEY.md`): `report_key` tidak memuat mata uang, padahal cache-nya dipakai bersama oleh `reports` dan `invoices`; kontraknya ada di `reports.py`. Kedua urutan (EUR→USD, USD→EUR) diuji di kedua pemanggil. Diukur: bug asli → 5 tes target gagal; referensi → semua lulus; bypass cache → regresi cache gagal; cache dimatikan → gagal; key lengkap hanya di `reports.py` → 5 gagal (membuktikan `invoiced` terkena bug yang sama). Naskah keliru = key lokal di `reports.py` (regresi tetap lulus, hanya `issue_fixed` palsu). Mutan validasi → `BROKEN`. Hash benchmark `dcdc5487…`
- [x] **Eksperimen live #6** (`cache_key`, `7c50f3e`, `docs/reviews/EVAL_LIVE_6.md`): **DONE di attempt pertama**, hanya `keys.py` berubah (key memuat mata uang), tes dijalankan ulang (regresi 4/4, target 5/5), klaim cocok, 4 panggilan, **10.679 dari 30.000 token**, **$0.0268**. Agen hanya membaca 5 dari 7 modul (jalur `get_report` → cache → key). Catatan desain: parameter `currency` yang tidak dipakai di `report_key` adalah tanda yang mencolok, jadi task ini kemungkinan lebih mudah dari yang dimaksudkan
- [x] **Pengukuran B** (`docs/reviews/MEASURE_CONTEXT_B.md`, `scripts/measure_context.py`, biaya nol): kalibrasi token dari 20 panggilan live (token ≈ 407 + 0,3186 × karakter, galat ≤ 9,4%); simulasi dengan loop agen dan `LLMCaller` asli. File ~1 KB: paling banyak 5 (1 per langkah), 10 (5 per langkah), atau 20 (sekaligus) file sebelum reservasi habis; file ~3 KB: 3 / 5 / 5. Pengikatnya pengiriman ulang kumulatif. Repo besar dengan konfigurasi sekarang hampir pasti `reservation_exhausted`
- [x] Keputusan dari data B: tool pencarian read-only dulu (desain dan simulasi, belum implementasi)
- [x] **`SearchFiles`: desain** (PR #49) dan **implementasi** (`docs/reviews/REVIEW_SEARCHFILES.md`): read-only, literal, di dalam path jail, dengan batas file, byte, dan hasil yang dilaporkan eksplisit kalau tercapai; belum aktif secara default. 20 tes adversarial; 14 dari 16 mutan tertangkap (2 ekuivalen; menghapus kedua lapis sekaligus tertangkap). Simulasi dengan tool asli: semua skenario pencarian (termasuk kata salah, terlalu umum, dan jalur yang salah) selesai sampai 80 file, tapi dengan file 3 KB satu jalur salah sudah membawa attempt ke 26–28 ribu token
- [x] Desain task repo besar (PR #51), keputusan A: tool diaktifkan lewat kontrak
- [x] **Tool lewat kontrak:** field opsional `tools` yang hanya boleh menambah tool dari `CONTRACT_TOOLS` (`search_files`); divalidasi fail-closed sebelum panggilan model, dibekukan bersama kontrak, dan dicatat di `tools_effective` serta `result.json`. Kontrak tanpa `tools` berjalan identik. 8/8 mutan tertangkap
- [ ] Task repo besar dengan `search_files` aktif (model palsu dulu, lalu live dengan persetujuan)
- [ ] Tes eval di sandbox dijalankan pada 1–2 task saja, bukan seluruh manifest (`verify.sh` naik dari 447 ke 516 detik dengan jumlah tes yang sama, karena setiap task baru menambah beberapa run penuh)
- [ ] Perluasan benchmark berdasarkan kegagalan nyata dari eksperimen itu, lalu bekukan hash v1
- [ ] **Eval set task umum:** beberapa fixture task dengan tingkat kesulitan berbeda; ukur acceptance pass rate, biaya, jumlah attempt, dan regresi. Tes rutin tetap dengan model palsu; setiap run live butuh tujuan eksperimen dan persetujuan biaya sendiri
- [x] **3a. Cek evaluator tambahan** (branch `m3-3a`): struktur bagian, format baris (baris salah format tidak lagi dilewati diam-diam), duplikat, urutan, produk/bulan/bagian ekstra, jumlah dan penomoran rekomendasi. 25 tes, 25 mutasi tertangkap; `verify.sh` di VM 476 lulus, 0 skip (`verify-20261014T180705Z-aarch64.log`)

**Milestone 4+**
- [ ] Approval manusia untuk aksi berisiko (interrupt LangGraph)
- [ ] Tracing / dashboard (Langfuse atau LangSmith)
- [ ] Eval set 10-20 task: bandingkan single-agent vs multi-agent, dan model kandidat worker (Haiku 5.5 vs DeepSeek V4.1 Flash) berdasarkan biaya per task yang lulus
- [ ] Deploy harness sebagai service di OCI (systemd)

**Diterima sebagai batasan untuk sekarang**
- `max_seconds` masih soft limit (jumlah waktu node, dicek antar iterasi)

---

## Selesai

- [x] M1: harness, graph, budget token dengan reservasi, stagnasi, retry, allowlist tool, event log
- [x] M1: crash-resume dengan memo per node (diuji crash di 4 titik × 5, setelah commit, dan 50x worker paralel)
- [x] M1: perbaikan audit GPT #1 dan #2, evaluator menolak bulan palsu
- [x] Layer provider Anthropic / OpenAI / DeepSeek, ganti model per role lewat config atau `--model`
- [x] `verify.sh` dengan dependensi dipatok dan log bukti di `verification/`
- [x] Repo `DtsA14/argus-agent` + rencana M2
- [x] **2a:** wrapper LLM (`harness/llm.py`): reservasi token+USD per request, tolak sebelum kirim, cap output dikirim ke provider, ledger per percobaan (gagal di-charge worst case), retry transient + `Retry-After`, prompt di-hash, retry tersembunyi SDK dimatikan
- [x] **2a:** budget USD tingkat run dengan reservasi per iterasi; `recursion_limit` mengikuti `max_iterations` (sebelumnya crash di atas ~14 iterasi)
- [x] **2a:** model palsu terskrip (`models/fake.py`), 78 tes wrapper + 6 mutasi tertangkap
- [x] **Patch audit GPT 2a:** model tanpa harga ditolak selama `max_usd` finite (sebelumnya 2 juta token lolos tercatat $0); penghitung token mencakup argumen tool call dan hasil tool; ledger `llm_call_started` → `llm_call` dengan `call_id`, charge setelah ledger ditulis (tetap terjadi walau penulisan gagal), rekonsiliasi `unknown_after_crash`; `delivery` received/unknown; pelanggaran budget eksplisit → `FAILED_BUDGET`; `meta` dibatasi whitelist (sebelumnya bisa menimpa field sistem dan bikin crash setelah provider dibayar); akuntansi integer nano-dollar. 22 tes baru, 8 mutasi (7 tertangkap, 1 menunjukkan cek redundan yang lalu dihapus)
- [x] **2b (branch `m2-2b`):** orchestrator LLM lewat tool `SubmitPlan` (dipaksa dengan `tool_choice`), divalidasi harness: skema, ID unik dan valid, ≤ `max_workers`, setiap output wajib tepat sekali. Rencana tidak valid dikembalikan ke model dengan error persisnya (maks 3 panggilan), lalu `FAILED_PLAN`. Error model permanen → `FAILED_LLM`; reservasi habis → `FAILED_BUDGET`; semuanya berhenti rapi tanpa menjalankan worker
- [x] **2b:** kontrak output (`nodes/contract.py`): worker, synthesize, dan evaluator membaca hasil per **nama output + iterasi**, jadi ID task bebas dipilih planner dan hasil basi iterasi lama tidak terbawa
- [x] **2b:** provider `fake` berbasis file (posisi skrip disimpan) untuk tes crash-resume lintas proses dan demo offline; flag `--impl`, `--config`; 35 tes + 9 mutasi tertangkap
- [x] **2c (branch `m2-2c`):** worker loop tool-calling (`ReadData`, `SubmitResult` divalidasi terhadap skema output kontrak), batas `max_steps`; memo per langkah untuk balasan model dan hasil tool, di-commit sebelum lanjut, kuncinya memuat identitas input (pesan, model, skema tool; tool juga langkah LLM induknya + versi tool)
- [x] **2c:** reservasi node dipulihkan dari ledger setelah crash (worker dan orchestrator), sehingga batas per node berlaku lintas proses; sebelumnya node bisa memakai sampai 2× estimasinya
- [x] **2c:** model palsu dengan skrip per task (worker paralel), event log tahan baris terpotong; 22 tes, 8 mutasi tertangkap, termasuk bug kunci tool yang ditemukan tesnya sendiri
- [x] **2d (branch `m2-2d`):** path jail untuk semua tool file (`..`, absolut, NUL, symlink keluar, TOCTOU lewat `O_NOFOLLOW`), `write_file` atomik dan aman diulang; laporan ditulis lewat jail. Menutup temuan audit M1 (`../escaped.txt`)
- [x] **2d:** sandbox Docker untuk `RunPython` (tanpa jaringan, rootfs read-only, nobody, tanpa capability, no-new-privileges, batas memori/CPU/pids, timeout yang membunuh dan menghapus container, output dibatasi, image wajib pinned, tanpa fallback); versi image masuk kunci memo
- [x] **Hardening cleanup sandbox (saran review ulang GPT):** satu anggaran `cleanup_timeout_s`, penghapusan dikonfirmasi, `cleanup_failed` + event bila gagal. 4 mutasi tertangkap
- [x] **Patch audit 2d:** output sandbox dibaca terbatas (harness 1213 MB → 13 MB RSS untuk 400 MB output), kill awal pada banjir output, `--log-driver none` (output tidak lagi disalin ke disk host); path jail via `openat`/`dir_fd` tanpa symlink di level mana pun, tahan race direktori induk (dibuktikan dengan race lintas proses). 12 mutasi tertangkap
- [x] **2d:** 36 tes, sebagian besar di container sungguhan (image lokal via `docker import`, karena Docker Hub diblokir di lingkungan Claude); 13 mutasi flag/jail tertangkap setelah 3 tes yang lulus karena alasan salah diperbaiki; `verify.sh` gagal bila tes sandbox di-skip
