# Gap analysis M6 (repo-to-PR) berbasis bukti

Status: **untuk review; tanpa perubahan kode.** 2026-10-17. Basis: main `f51a8b2`.

Acuan:
- spesifikasi `docs/FUTURE_ARCHITECTURE.md` (branch `docs-future-architecture`, draf 2026-10-15), bagian 5 (M6) dan
  bagian 6 (kriteria MVP M6);
- bukti eksperimen di `PENDING.md`.

Disepakati di review:
- M6 adalah **hipotesis yang diuji**, bukan keputusan;
- bukti cukup sampai tingkat file, simbol, dan tes, kecuali gap yang menghalangi M6, yang ditelusuri lebih dalam;
- "belum ada" hanya dipakai jika sudah diperiksa di repo. Jika belum diperiksa, statusnya **belum terverifikasi**.

| Status | Arti |
|---|---|
| **Lulus** | ada implementasi dan verifikasi (tes atau run live) yang sesuai |
| **Lulus di jalur terbatas** | berfungsi, tapi hanya dalam batas tertentu (disebutkan) |
| **Belum ada** | diperiksa di repo, dan implementasinya tidak ada |
| **Belum terverifikasi** | mungkin ada, tapi buktinya belum cukup |

## 1. Alur M6 dari spesifikasi, per tahap

| Tahap | Status | Bukti / catatan |
|---|---|---|
| Issue / requirement masuk | Lulus di jalur terbatas | Issue di kontrak (`inputs.issue`, maksimal 2.000 karakter, `acceptance/contract.py` `validate`). Kontrak ditulis manusia |
| Analisis repo | Lulus di jalur terbatas | Agen membaca repo lewat `ListFiles`, `ReadFile`, dan `SearchFiles` (`codetask/tools.py`). Tidak ada tahap analisis terpisah; analisis terjadi di dalam loop agen |
| Rencana | **Belum ada** | `codetask/` tidak punya planner atau rencana bertipe. `nodes/plan.py` hanya memvalidasi rencana orchestrator di graph harness (task laporan data) |
| Perubahan kode | Lulus | `WriteFile` dan `EditFile` dengan scope dan path jail (`codetask/tools.py` `_writable`, `tools/fs.py` `PathJail`). Live: pilot `argus_self_2` DONE |
| Tes di sandbox | Lulus di jalur terbatas | `acceptance/validation.py` dan `tools/sandbox.py`. Hanya `python -m unittest discover` (`PREFIX`, `OPTIONS`), di image Python tanpa dependensi proyek |
| Recovery terbatas | Lulus | attempt berikutnya dengan umpan balik verdict (`codetask/agent.py` `feedback_from`), `max_iterations`, dan stagnasi. Live: seri #2 (0/9 → 4/9), pilot 2 |
| Diff / proposal PR yang bisa di-review | **Belum ada** | Tidak ada kode yang membuat diff, patch, atau PR (grep `git diff`, `gh pr`, `unified_diff`, `format-patch` di `codetask`, `acceptance`, `harness`, `evals`, `scripts`: tidak ada). Diff dan PR pilot dibuat manual |

## 2. Kriteria MVP M6 (spesifikasi bagian 6)

| # | Kriteria | Status | Bukti |
|---|---|---|---|
| 1 | Menerima issue yang terbatas dan target repo | Lulus di jalur terbatas | `inputs.workspace` wajib di bawah `fixtures/repos/` (`acceptance/contract.py:106`). Repo nyata harus disalin dulu sebagai snapshot (dilakukan manual di pilot) |
| 2 | Rencana bertipe dan kriteria acceptance eksplisit | Sebagian | **Kriteria:** eksplisit, tapi **ditulis manusia** di kontrak (validasi, `must_pass`, scope). **Rencana bertipe: belum ada** (lihat tahap Rencana) |
| 3 | Baca/tulis dibatasi ke workspace | Lulus | `PathJail` (`tools/fs.py`); `Toolbox._writable` untuk WriteFile dan EditFile; cek scope di acceptance (`acceptance/workspace.py` `scope_check`). Tes: `tests/test_fs.py`; `test_writes_outside_the_scope_are_refused_and_change_nothing` (`tests/test_codetask.py`); `tests/test_edit_tool.py` (scope, jail, symlink) |
| 4 | Kode dan tes berjalan terisolasi | Lulus di jalur terbatas | `tools/sandbox.py`: `--network none`, `--read-only`, `--user 65534`, `--cap-drop ALL`, `no-new-privileges`, batas memori, CPU dan pid; workspace di-mount read-only saat validasi. Tes: `tests/test_sandbox.py` (`test_no_network`, `test_filesystem_is_read_only_except_workspace_and_tmp`, `test_memory_limit_kills_the_code`, `test_timeout_kills_and_removes_the_container`). Batas: hanya image Python polos |
| 5 | Plafon biaya per task dan per run | Lulus | `LLMCaller` (`harness/llm.py`, reservasi dan penolakan sebelum mengirim); `admission` (`codetask/run.py`); cap kontrak dan config. Seri: `run_series` `--max-usd-series`. Tes: `tests/test_codetask.py` (budget), `tests/test_budget_experiment.py`, `tests/test_run_series.py`. Live: 0 pelanggaran budget di semua seri |
| 6 | State tersimpan, lanjut setelah interupsi | Lulus | `durability="sync"`, memo per langkah, checkpoint SQLite. Tes lintas proses: `tests/test_codetask_crash.py` (tujuh titik crash, ditambah dua untuk EditFile) |
| 7 | Menghindari operasi berbayar ganda | Lulus di jalur terbatas | **Ledger:** langkah yang sudah di-commit tidak dibeli ulang; balasan yang belum di-commit dibeli ulang dan **keduanya dibayar dan dicatat** (`test_a_crash_before_a_reply_is_committed_buys_it_again_and_pays_for_both`). **Provider:** tidak ada idempotency key dan tidak ada konfirmasi ke provider (belum ada) |
| 8 | Artefak, diff, log, dan provenance tersimpan | Lulus di jalur terbatas | Run dir menyimpan kontrak beku dan sha, `events.jsonl` (ledger), memo, `verdict_<i>.json`, workspace, dan `tool_journal.jsonl`. **Tidak ada artefak diff.** Commit agen hanya dicatat di laporan eval (`evals/runner.py` `agent_version`), tidak di `result.json` `run_code_task`. Commit dasar repo target tidak dicatat |
| 9 | Menolak tool tanpa izin dan akses file/jaringan di luar scope | Lulus | `GATED` dan `tool_denied` (`codetask/tools.py`); tes `test_a_denied_tool_is_never_run`, `test_c_offers_every_tool_but_search_and_refuses_a_search_call`; agen tidak punya tool jaringan; sandbox `--network none` |
| 10 | Lulus/gagal per kriteria dengan bukti | Lulus | `acceptance/verdict.py` `evaluate` (kriteria beserta bukti), `verdict_<i>.json`; validasi ulang independen dan klaim (`evals/score.py`) |
| 11 | Diff atau proposal PR yang bisa di-review, tanpa merge/deploy otomatis | **Belum ada** | Tidak ada pembuatan diff atau PR (lihat tahap 1). "Tanpa merge otomatis" terpenuhi secara trivial: tidak ada mekanisme merge sama sekali |
| 12 | Tes deterministik untuk delapan kasus (bagian 3) | Sebagian | lihat bagian 3 |

## 3. Tes deterministik yang diminta spesifikasi

| Kasus | Status | Bukti |
|---|---|---|
| Sukses | Lulus | `tests/test_codetask.py` (DONE dengan model palsu); `tests/test_eval_sandbox.py` (mode reference di sandbox) |
| Tool gagal | Lulus | `No such file`, `Rejected`, dan `Refused` di `tests/test_codetask.py`, `tests/test_edit_tool.py`, `tests/test_searchfiles.py` |
| Timeout | Lulus | validasi: `test_a_validation_that_hangs_is_killed_at_its_timeout` (`tests/test_acceptance_sandbox.py`); sandbox: `test_timeout_kills_and_removes_the_container`; provider: `test_codetask.py:190` (HTTP 401 → `BLOCKED provider_failed`). Timeout panggilan model di code task: **belum terverifikasi** |
| Pemulihan crash | Lulus | `tests/test_codetask_crash.py` |
| Budget habis | Lulus | `test_no_attempt_starts_when_one_attempt_does_not_fit`, `test_another_attempt_starts_only_if_its_whole_reservation_fits`, `test_a_next_attempt_that_does_not_fit_the_budget_is_not_run_and_nothing_is_done` |
| Izin ditolak | Lulus | `test_a_denied_tool_is_never_run`; tes scope di `tests/test_edit_tool.py` |
| Output model rusak | Lulus di jalur terbatas | Ditangani di loop code task (`codetask/agent.py`: `invalid_call_errors`, `is_truncated`, Finish yang tidak sendiri). Tes deterministik ada untuk node graph harness (`tests/test_invalid_tool_calls.py`) dan `test_finish_must_be_alone_and_well_formed`. **Tool call rusak dan balasan terpotong di loop code task belum punya tes deterministik**; buktinya hanya dari run live (pilot 1–3, seri #2 b3) |
| Quality gate gagal | Lulus | tes `FAILED_ACCEPTANCE` di `tests/test_codetask.py` dan `tests/test_eval_sandbox.py` (mode wrong) |

## 4. Hambatan minimum agar Argus bisa: task repo nyata → kerja → validasi → PR siap review

Diurutkan dari yang paling menghalangi.

1. **Validasi untuk proyek nyata.** Sandbox hanya menjalankan `python -m unittest discover` di image Python tanpa
   dependensi proyek. Akibatnya Athena (pytest dan numpy/pandas) dan test suite Argus sendiri tidak bisa divalidasi.
   - Yang dibutuhkan minimal: image sandbox per proyek dengan dependensi yang di-pin (tetap tanpa jaringan saat run),
     dan perintah pytest yang terstruktur beserta parser hasilnya.
   - Ini menyentuh acceptance dan sandbox, jadi ikut proses ketat.
2. **Diff dan proposal PR.**
   - Yang dibutuhkan minimal: patch dari workspace terhadap commit dasar, disimpan sebagai artefak run, ditambah draf
     deskripsi PR dari verdict dan klaim.
   - Usul: **membuka PR tetap dilakukan manusia** (atau harness setelah approval eksplisit). Dengan begitu MVP tidak
     membutuhkan layanan approval dulu. Membuka PR adalah aksi ke luar (GitHub), jadi tunduk pada ADR-007.
3. **Intake repo di commit tertentu.** Saat ini workspace wajib di bawah `fixtures/repos/`, dan repo nyata disalin
   manual. Yang dibutuhkan minimal: snapshot yang bisa diulang dari repo dan commit tertentu, dengan commit dasar dan
   commit agen dicatat di `result.json` (sekarang tidak). Itu provenance minimum untuk PR.
4. **Profil budget per task.** 30.000 token per attempt dan output 4.096 terbukti kurang untuk task berat:
   - eksperimen budget: 30k 3/9 vs 45k 9/9;
   - pilot 3: thinking 100% di batas output.

   Yang dibutuhkan minimal: profil di config yang dipilih per kontrak, tanpa mengubah default untuk task kecil.
5. **Kriteria dan rencana.** Kriteria acceptance saat ini ditulis manusia, dan tidak ada rencana bertipe. Ini
   **keputusan, bukan sekadar gap**: untuk MVP, kontrak bisa tetap ditulis manusia. Opsinya:
   - (a) tetap manual;
   - (b) model membuat draf kontrak dan tes, lalu manusia menyetujui;
   - (c) planner penuh.
6. **Tes deterministik untuk output rusak di loop code task** (tool call rusak, balasan terpotong). Penanganannya sudah
   ada, tapi belum dikunci oleh tes. Kecil dan tidak menghalangi, tapi spesifikasi memintanya.

## 5. Bukan hambatan M6 minimum (tidak perlu dibangun sekarang)

- **ADR-001** (registry formal dan policy engine): allowlist dan tool lewat kontrak cukup untuk MVP.
- **ADR-003** (knowledge memory dan project memory): belum ada bukti kebutuhan.
- **ADR-005** penuh (store artefak terpusat dan lineage): run dir ditambah artefak patch cukup untuk MVP.
- **M4** (multi-agent paralel): tidak ada bukti bahwa single-agent menjadi penghalang. Sukses yang sudah terbukti
  (16/16, 9/9 di 45k, pilot 2) semuanya single-agent.
- **Rekonsiliasi di sisi provider dan idempotency key** (kriteria 7): tidak menghalangi. Biaya ganda sudah dibatasi
  dan tercatat di ledger.

## 6. Keputusan untuk review

1. Apakah hambatan 1–4 adalah lingkup MVP M6, dengan kriteria acceptance M6 ditetapkan setelah review ini?
2. Kriteria dan rencana untuk MVP: (a) manual, (b) draf oleh model lalu disetujui manusia, atau (c) planner.
3. Membuka PR: selalu oleh manusia di MVP, atau oleh harness setelah approval eksplisit (lebih banyak kerja, ADR-007)?
4. Repo nyata pertama untuk M6: Athena (pytest dan dependensi), atau test suite Argus sendiri?

Tidak ada implementasi M6 sebelum keputusan ini dan kriteria acceptance M6 disetujui.
