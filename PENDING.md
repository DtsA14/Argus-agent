# Pending

Daftar kerja Argus, dipisah menurut **siapa yang bisa mengerjakan dan kapan**.
Detail desain ada di [`docs/MILESTONE2_PLAN.md`](docs/MILESTONE2_PLAN.md), detail temuan audit di [`BACKLOG.md`](BACKLOG.md).

Terakhir diperbarui: 2026-10-14.

---

## 1. Bisa dikerjakan sekarang (Claude, tanpa API key dan tanpa VM)

Semua bisa diuji penuh dengan model palsu, jadi tidak ada biaya.

- [ ] **2a. Wrapper LLM** (`harness/llm.py`): reservasi token sebelum kirim, `max_tokens` dari sisa reservasi, klasifikasi error transient vs permanen, timeout per role
- [ ] **2a. Budget USD** (`budget.max_usd`), tolak model tanpa harga kecuali `allow_unpriced`
- [ ] **2a. Ledger per percobaan** (event `llm_call`), termasuk percobaan gagal dan retry
- [ ] **2a. Model palsu terskrip** (subclass `GenericFakeChatModel` + `bind_tools`) untuk semua tes
- [ ] **2b. Orchestrator LLM** dengan output terstruktur + validasi rencana (skema, jumlah task ≤ `max_workers`, ID unik), retry maksimal 2x lalu `plan_invalid`
- [ ] **2c. Worker loop tool-calling** dengan `max_steps`, tool call cacat dikembalikan sebagai error
- [ ] **2c. Memo per langkah worker** `(node, task, iteration, step)` + tes crash di tengah loop
- [ ] **2d. Path jail** untuk semua tool file (`../`, path absolut, symlink keluar) + `write_file` atomic (temp lalu rename)
- [ ] **2d. Kode sandbox Docker** (`run_python`). Tesnya otomatis di-skip di sini karena Docker Hub diblokir, lalu dijalankan penuh di VM

Default sementara dipakai sampai Atha memutuskan (lihat bagian 2): `max_usd: 0.50`, log prompt `hashed`.

## 2. Butuh keputusan Atha (tidak memblokir pengerjaan bagian 1)

- [ ] Tambah budget USD? Default `max_usd: 0.50` per run
- [ ] Boleh pasang Docker di VM OCI? Kalau tidak, alternatifnya bubblewrap (isolasi lebih lemah)
- [ ] Log prompt: `hashed` (aman untuk data klien) atau `full` (lebih mudah debug)?
- [ ] Batas belanja smoke test live: $0.50 per run cukup?

## 3. Butuh Atha di PC atau VM

Urutan disarankan, karena saling bergantung.

- [ ] **Jalankan verifikasi M1 di VM:** `git clone` repo → `bash scripts/verify.sh` → kirim baris `RESULT:` (butuh token GitHub read-only, lihat README)
- [ ] **Pasang Docker di VM** (setelah keputusan di bagian 2), lalu cek `docker run --rm python:3.13-slim python -V`
- [ ] **Set API key di VM** sebagai env var: `ANTHROPIC_API_KEY`, `DEEPSEEK_API_KEY`, `OPENAI_API_KEY`. Jangan di file repo
- [ ] **Cek ID model:** `python scripts/smoke_models.py --list --grep gpt`, lalu `python scripts/smoke_models.py`. Kirim hasilnya
- [ ] **2e. Smoke live:** satu run nyata task CSV di VM, dibatasi `max_usd` (setelah 2a-2d selesai)

## 4. Butuh GPT (audit)

- [ ] Sign-off M1 dari log `verify.sh` hasil VM OCI
- [ ] Audit setelah 2b (wrapper LLM + orchestrator)
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
