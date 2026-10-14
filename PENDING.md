# Pending

Daftar kerja Argus, dipisah menurut **siapa yang bisa mengerjakan dan kapan**.
Detail desain ada di [`docs/MILESTONE2_PLAN.md`](docs/MILESTONE2_PLAN.md), detail temuan audit di [`BACKLOG.md`](BACKLOG.md).

Terakhir diperbarui: 2026-10-14.

---

## 1. Bisa dikerjakan sekarang (Claude, tanpa API key dan tanpa VM)

Semua bisa diuji penuh dengan model palsu, jadi tidak ada biaya.

- [x] **2b. Orchestrator LLM** di branch `m2-2b`, **menunggu review 2a sebelum merge ke `main`** (detail di bagian Selesai)
- [ ] **2c. Worker loop tool-calling** dengan `max_steps`, tool call cacat dikembalikan sebagai error
- [ ] **2c. Memo per langkah worker** `(node, task, iteration, step)`, **termasuk hasil tool**, persisten dan atomik + tes crash di tengah loop
- [ ] **2d. Path jail** untuk semua tool file (`../`, path absolut, symlink keluar) + `write_file` atomic (temp lalu rename)
- [ ] **2d. Kode sandbox Docker** (`run_python`) dengan `--cap-drop ALL`, `no-new-privileges`, image di-pin ke digest. Tesnya **tidak dihitung lulus** kalau di-skip; dijalankan penuh di VM

## 2. Keputusan (sudah diambil 2026-10-14)

- [x] Budget USD: ya, `max_usd: 0.50`, hard gate per request
- [x] Docker di VM OCI: boleh, dengan hardening tambahan dari GPT
- [x] Log prompt: `hashed`; `full` hanya dengan `ARGUS_DEV=1` dan data sintetis
- [x] Smoke live: maksimal $0.50, satu run serial, tidak diulang otomatis

## 3. Butuh Atha di PC atau VM

Urutan disarankan, karena saling bergantung.

- [ ] **Jalankan verifikasi M1 di VM:** `git clone` repo → `bash scripts/verify.sh` → kirim baris `RESULT:` (butuh token GitHub read-only, lihat README)
- [ ] **Pasang Docker di VM** (setelah keputusan di bagian 2), lalu cek `docker run --rm python:3.13-slim python -V`
- [ ] **Set API key di VM** sebagai env var: `ANTHROPIC_API_KEY`, `DEEPSEEK_API_KEY`, `OPENAI_API_KEY`. Jangan di file repo
- [ ] **Cek ID model:** `python scripts/smoke_models.py --list --grep gpt`, lalu `python scripts/smoke_models.py`. Kirim hasilnya
- [ ] **2e. Smoke live:** satu run nyata task CSV di VM, dibatasi `max_usd` (setelah 2a-2d selesai)
- [ ] **2e. Setel `token_estimates` untuk node LLM dari ledger.** Satu panggilan orchestrator ≈ 700-1300 token input + output rencana; estimasi 3000 (dibuat untuk node palsu) hanya muat ~2 percobaan. Tes LLM memakai 12000. Angka final diambil dari `llm_call` hasil run nyata, bukan ditebak
- [ ] **2e. Cek `tool_choice` per provider.** Orchestrator memaksa tool `SubmitPlan`; kalau sebuah provider menolaknya (mis. mode thinking DeepSeek), set `orchestrator.force_tool: false`

## 4. Butuh GPT (audit)

- [ ] Sign-off M1 dari log `verify.sh` hasil VM OCI
- [x] Audit 2a (wrapper LLM): "perlu patch kecil", sudah dipatch
- [ ] Konfirmasi GPT atas patch 2a, lalu audit 2b (validasi rencana orchestrator, semua panggilan model lewat wrapper)
- [ ] Audit setelah 2e (run live di OCI)

## 5. Nanti

**Milestone 3: evaluator**
- [ ] Rubric LLM menggantikan stub `recs_rubric`; evaluator pakai provider berbeda dari worker
- [ ] Acceptance criteria untuk task umum (bukan cuma CSV demo)
- [ ] Cek evaluator tambahan: baris duplikat, urutan salah, produk atau bagian ekstra

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
