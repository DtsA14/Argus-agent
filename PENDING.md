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
- [ ] Rubric LLM menggantikan stub `recs_rubric` (3c, judge `deepseek-flash`)
- [ ] Acceptance criteria untuk task umum (bukan cuma CSV demo)
- [x] **3a. Cek evaluator tambahan** (branch `m3-3a`): struktur bagian, format baris (baris salah format tidak lagi dilewati diam-diam), duplikat, urutan, produk/bulan/bagian ekstra, jumlah dan penomoran rekomendasi. 25 tes, 25 mutasi tertangkap; `verify.sh` di VM 476 lulus, 0 skip (`verify-20261014T180705Z-aarch64.log`)

**Milestone 4+**
- [ ] Approval manusia untuk aksi berisiko (interrupt LangGraph)
- [ ] Tracing / dashboard (Langfuse atau LangSmith)
- [ ] Eval set 10-20 task: bandingkan single-agent vs multi-agent, dan model kandidat worker (Haiku 5.5 vs DeepSeek V4.1 Flash) berdasarkan biaya per task yang lulus
- [ ] Deploy harness sebagai service di OCI (systemd)

**Proyek masa depan: Argus sebagai agen pembuat serba guna** (disimpan 2026-10-15, belum dikerjakan)
- [ ] Spesifikasi arsitektur draf (dari diskusi Atha + GPT): [`docs/FUTURE_ARCHITECTURE.md`](docs/FUTURE_ARCHITECTURE.md).
  Isinya 7 ADR (registry tool + policy, workflow bertipe, memori berlapis, eksekusi durable, artifact store, quality
  gate, keamanan dan approval), roadmap M3–M9 (M6 = agen repo-ke-PR), dan kriteria MVP M6.
  **Bukan deskripsi kode yang ada.** Roadmap-nya berbeda dengan daftar M4+ di atas, jadi harus diselaraskan dulu.
  Dimulai hanya setelah M3 selesai dan Atha memintanya. Langkah pertamanya *reality check* repo dan rencana, tanpa kode
  sebelum direview.

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
