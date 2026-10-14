# Permintaan review: fase 2e (smoke live di VM OCI)

Branch `m2-2e`. Dibangun di atas `verify-commit-sha` (PR #4), jadi PR #4 sebaiknya di-merge dulu.
Bukti: `verification/verify-20261014T165526Z-aarch64.log` (commit `9b00a0c`, working tree bersih, 440 lulus,
0 tes sandbox di-skip) dan `verification/smoke-2e/` (event log, ledger, ringkasan, laporan kedua run).

## File utama
- `scripts/smoke_live.py`: satu run live. Tanpa `ARGUS_LIVE=1` tidak melakukan apa pun. `budget.max_usd` hanya bisa
  diturunkan ke `smoke.max_usd`. Model tanpa harga dan key yang hilang ditolak sebelum apa pun dibuat. Worker jalan
  satu per satu (`max_concurrency`). Tidak pernah diulang.
- `runner.py`: `run_task(max_concurrency=...)`.
- `harness/budget.py`: `effective_estimates()`, `llm_token_estimates` untuk node dengan `impl: llm`.
- `harness/llm.py`: `is_truncated()`, `llm_call.truncated`, event `output_truncated`.
- `nodes/orchestrator.py`, `nodes/llm_worker.py`: balasan yang terpotong tidak dijalankan atau diterima, dan tidak diulang.
- `config.yaml`: `orchestrator.force_tool: false`, `llm_token_estimates`, `smoke`, harga `cache_read` Sonnet/Opus 5.5.

## Pemeriksaan sebelum request pertama
- ID model: `smoke_models.py --list` menemukan `claude-haiku-5-5`, `claude-sonnet-5-5`, `claude-opus-5-5`.
- Harga input/output dan `cache_read` Sonnet/Opus dicocokkan dengan tabel model Anthropic. Tarif Haiku 5.5 untuk prompt
  di atas 100K token ($0.50/$2.50) tidak dimodelkan; ini aman selama estimasi node jauh di bawah 100K.
- `smoke_models.py`: chat dan tool call lolos untuk orchestrator (Sonnet 5.5) dan worker (Haiku 5.5), total ±$0.00008.
- Ditemukan: Sonnet 5.5, Opus 5.5, dan Fable 5.1 menolak `tool_choice` paksa dengan HTTP 400, jadi `force_tool`
  dimatikan. Tanpa paksaan, balasan yang bukan tepat satu `SubmitPlan` dikembalikan sebagai rencana tidak valid.

## Run 1 (`smoke_2e_1`): FAILED_BUDGET, $0.022479
Estimasi token masih angka untuk node palsu (orchestrator 3.000, worker 2.000).
- Ketiga worker: langkah ReadData ±970 token, langkah berikutnya butuh ±1.650 input. Request **ditolak sebelum dikirim**
  (`refused`, $0), lalu `worker_failed`.
- Orchestrator iterasi 1 (revisi): input 2.095, batas output 905, output **905**, artinya terpotong. Rencana ditolak hanya
  karena kebetulan field `tasks` ikut hilang (`tasks: Field required`). Percobaan berikutnya ditolak sebelum dikirim.
- Ledger: 5 request terkirim dan 5 `llm_call` ok, 4 ditolak tanpa terkirim, tidak ada yang `unknown`.

## Patch (syarat GPT)
1. **Jatah token LLM terpisah dari M1.** `llm_token_estimates` (orchestrator 12.000, worker 12.000) hanya berlaku untuk
   node `impl: llm`, lewat satu fungsi yang dipakai untuk reservasi node, reservasi token per iterasi, dan estimasi USD.
   Angka M1 tidak berubah: iterasi 11.500 token.
2. **Worst case dihitung ulang dengan kode budget:** iterasi LLM = 12.000 + 3 × 12.000 + 1.000 + 1.500 = 50.500 token;
   USD = 12.000 × $10/M (Sonnet, tarif termahal) + 3 × 12.000 × $0.50/M (Haiku) = **$0.138**. Yang membatasi jumlah iterasi
   adalah gate yang ada: token 200.000 cukup untuk 3 iterasi penuh, USD $0.50 juga cukup untuk 3 (3 × 0.138 = 0.414).
   Batas global tidak dilonggarkan. Gate USD per request tetap aktif: setiap request dibatasi sisa reservasi node.
3. **Output terpotong.** Dideteksi dari sinyal provider (Anthropic `stop_reason: max_tokens`; OpenAI/DeepSeek
   `finish_reason: length`), bukan ditebak dari isi. Balasan seperti itu tidak divalidasi, dijalankan, atau diterima, dan
   **tidak diulang**, karena percobaan berikutnya tidak mendapat ruang output lebih besar.
   - Orchestrator: `FAILED_PLAN` dengan alasan `output_truncated`.
   - Worker: `worker_failed` dengan alasan `output_truncated`.
   - Memo menyimpan flag ini, jadi balasan terpotong yang di-replay setelah crash tetap tidak diterima.

Tes: 12 kasus tes baru untuk patch, ditambah 20 kasus tes smoke dari commit sebelumnya (suite: 408 → 440).
Mutasi: 12 + 12 dijalankan, 24 tertangkap.
- Smoke: gate `ARGUS_LIVE`, cap yang bisa naik, `max`/`min`, validasi cap, `allow_unpriced`, harga, key, impl,
  retry, concurrency (dua tempat), `force_tool`.
- Patch: orchestrator menerima atau mengulang rencana terpotong, worker menjalankan balasan terpotong, memo atau replay
  membuang flag, `finish_reason` atau `stop_reason` diabaikan, ledger tanpa `truncated`, estimasi LLM diabaikan atau
  ikut dipakai node palsu, USD atau graph memakai estimasi lama.

## Run 2 (`smoke_2e_2`): DONE, skor evaluator 1.0, $0.009684
Satu run, worker serial, `max_usd` 0.50, commit `9b00a0c`.

| Node | Langkah | Token (ledger) | USD |
|---|---|---|---|
| orchestrator | 1 rencana, valid di percobaan pertama | 1.793 | 0.007986 |
| worker T1 (top3) | ReadData, SubmitResult | 3.002 | 0.000462 |
| worker T2 (trend) | ReadData, SubmitResult | 2.958 | 0.000439 |
| worker T3 (data_check) | ReadData, SubmitResult (ditolak validator), SubmitResult | 5.239 | 0.000797 |

- 8 request terkirim dan 8 `llm_call` ok, 0 ditolak, 0 terpotong, 0 `estimate_miss`, 0 `budget_violation`, 0 `unknown`.
- `usd_billed` = `usd_used` = jumlah ledger = $0.0096843.
- Token per node di `node_end` sama dengan jumlah ledger per node.
- Node terbesar (T3) memakai 5.239 dari 12.000 token, jadi masih ada ruang ±2,3 kali.

Total biaya live 2e: ±$0.0322 (dua run ditambah smoke model).

## Batasan yang disadari
- Satu run sukses belum membuktikan stabilitas. Satu worker butuh langkah tambahan karena validator menolak submit
  pertamanya. Angka 12.000 adalah titik awal, bukan hasil kalibrasi statistik.
- Evaluator masih programmatic (`recs_rubric` stub), dan rekomendasi di laporan dibuat oleh synthesize, bukan model (M3).
- Run tanpa sandbox (`sandbox.kind: none`): workers tidak punya RunPython. Smoke dengan `--sandbox docker` belum dijalankan.
- `token_estimates` untuk synthesize dan evaluator tetap angka node palsu, karena keduanya belum memanggil model.

## Pertanyaan untuk reviewer
- Perlu smoke kedua dengan `--sandbox docker` sebelum 2e dianggap selesai, atau cukup di M3?
- Perlukah memo menyimpan alasan penolakan validator sebagai event (sekarang hanya ada di hasil tool), supaya langkah
  ekstra seperti T3 terlihat di event log?

## Tanggapan atas review GPT (2026-10-15)

Bukti setelah patch: `verification/verify-20261014T172944Z-aarch64.log` (commit `b61d022`, working tree bersih, **448 lulus,
0 tes sandbox di-skip**) dan `verification/smoke-2e/smoke_2e_3`.

| Temuan | Status |
|---|---|
| P2: prompt worker tidak mengenalkan RunPython saat sandbox aktif | **Diperbaiki.** Tool yang ditawarkan sekarang diturunkan dari allowlist role: ReadData hanya dengan `read_data`, RunPython hanya dengan sandbox dan `run_python`, SubmitResult selalu ada. System prompt menjelaskan **persis** tool itu (RunPython: `/data/penjualan.csv` read-only, `/workspace` writable, tanpa jaringan). Temuan tambahan: tool yang tidak ditawarkan sebelumnya tetap sampai ke gate dan memicu `PermissionDenied` yang bisa menjatuhkan worker; sekarang dijawab sebagai tool tidak dikenal. Tes untuk ketiga mode (tanpa sandbox, sandbox, python-only), termasuk satu tes di container sungguhan |
| Catatan: alasan penolakan validator tidak terlihat di event log | **Dikerjakan.** Event `submission_invalid` berisi `errors` dari validator, maksimal 10 pesan × 200 karakter |
| Smoke Docker terarah | **Dijalankan, satu kali.** `smoke_live.py --sandbox docker --python-only`: worker **tidak** mendapat ReadData, jadi data hanya bisa dibaca dan dihitung di sandbox. Sandbox dicek sebelum apa pun dibuat |

Mutasi: 13 dijalankan, 13 tertangkap. Yang dimutasi:
- ReadData ditawarkan tanpa izin.
- RunPython ditawarkan tanpa sandbox, atau tidak pernah ditawarkan.
- Prompt mengabaikan tool yang ditawarkan, tidak menjelaskan RunPython, atau selalu menjelaskan ReadData.
- ReadData dijalankan walau tidak ditawarkan.
- Event `submission_invalid` hilang, atau pesannya tidak dipotong atau tidak dibatasi jumlahnya.
- `--python-only` tanpa sandbox, `--python-only` yang tetap memberi ReadData, sandbox yang tidak bisa dipakai tetap diterima.

### Run 3 (`smoke_2e_3`): Docker, python-only, DONE, skor evaluator 1.0, $0.0119085
Satu run, worker serial, `max_usd` 0.50, image `python@sha256:70729b46…` (arm64).

| Node | Langkah | Token (ledger) |
|---|---|---|
| orchestrator | 1 rencana, valid di percobaan pertama | 1.915 |
| worker T1 | RunPython, RunPython, SubmitResult | 5.576 |
| worker T2 | RunPython, RunPython, SubmitResult | 5.634 |
| worker T3 | 2 × RunPython (paralel dalam satu balasan), RunPython, SubmitResult | 7.247 |

- Model sungguhan memilih RunPython sendiri. Total 7 eksekusi container, semua exit 0, tanpa timeout, dan `cleanup_failed`
  false semua. Tidak ada container `argus.sandbox=1` yang tersisa setelah run.
- `tool_call`: `run_python` 7 kali, `write_file` 1 kali (laporan). **`read_data` 0 kali, `tool_denied` 0.**
- 10 request terkirim dan 10 `llm_call` ok, 0 ditolak, 0 terpotong, 0 `estimate_miss`, 0 `submission_invalid`.
  Ledger = `usd_used` = `usd_billed`, dan token per node di `node_end` sama dengan ledger.
- Node terbesar (T3) memakai 7.247 dari 12.000 token, jadi ruangnya ±1,65 kali. Lebih sempit daripada run tanpa sandbox,
  karena output RunPython ikut masuk input langkah berikutnya.

Total biaya live 2e: ±$0.044 (tiga run ditambah smoke model).

### Catatan kecil
- Event `sandbox_run` belum membawa nomor langkah (`step`), karena meta yang diteruskan ke sandbox hanya berisi node,
  task, dan iterasi. Urutannya tetap bisa dibaca dari `step_committed`. Bisa ditambahkan kalau diperlukan.
