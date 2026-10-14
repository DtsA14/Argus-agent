# Milestone 2: worker LLM nyata, tools, sandbox

Status: **disetujui** (Atha + GPT, 2026-10-14). Fase 2a selesai, lihat [`PENDING.md`](../PENDING.md).
Dasar: milestone 1 di commit `b972529` (harness, budget, crash-resume, layer provider).

## 0. Keputusan yang sudah diambil

| # | Keputusan | Tambahan dari review GPT |
|---|---|---|
| 1 | Budget USD **ya**, `max_usd: 0.50` per run | Hard gate per request: estimasi biaya maksimum input + output harus muat, kalau tidak ditolak sebelum dikirim. Budget token M1 tetap berlaku bersamaan |
| 2 | Docker di VM OCI **boleh** | Tambah `--cap-drop ALL` dan `--security-opt no-new-privileges`; image di-pin ke **digest**; batas memori/CPU dan mount diverifikasi benar-benar aktif di OCI; socket Docker tidak diekspos ke jaringan |
| 3 | Log prompt **hashed** (default) | Mode `full` hanya untuk development dengan data sintetis, butuh `ARGUS_DEV=1` |
| 4 | Smoke live maksimal **$0.50/run** | Satu run **serial** (bukan 3 worker paralel); jangan otomatis diulang kalau budget habis; hanya pakai ID model yang terverifikasi dan punya harga di config |

Tambahan desain dari GPT: **memo per langkah harus persisten dan atomik, termasuk hasil tool.** Hasil
tool yang berhasil di-commit sebelum worker lanjut; replay setelah crash tidak boleh memanggil model
atau menjalankan ulang tool yang sudah selesai. Tes sandbox yang di-skip **tidak dihitung lulus**.

## 1. Tujuan

Mengganti node palsu dengan LLM sungguhan **tanpa melemahkan satu pun jaminan milestone 1**,
lalu membuktikannya dengan satu run end-to-end nyata di VM OCI (ARM).

Task demo tetap sama (analisis `penjualan.csv`), supaya evaluator programatik yang sudah ada
bisa menilai hasil LLM secara objektif. Task umum menyusul di M3.

## 2. Ruang lingkup

**Masuk M2**
- Orchestrator LLM: membuat rencana task terstruktur (JSON tervalidasi).
- Worker LLM: loop tool-calling dengan batas langkah.
- Wrapper panggilan LLM dengan batas token/USD **per request**, dan pencatatan setiap percobaan.
- Tools: baca data, tulis file, jalankan Python, semuanya dikurung di folder run.
- Sandbox Docker untuk eksekusi kode.
- Memo per langkah worker, supaya crash di tengah loop tidak membayar ulang langkah yang sudah selesai.
- Tes deterministik dengan model palsu (tanpa biaya), plus smoke test live yang opt-in.

**Tidak masuk M2**
- Evaluator LLM / rubric (M3). Evaluator M2 tetap programatik, jadi role `evaluator` di config
  belum dipanggil dan ID model OpenAI yang belum terverifikasi tidak memblokir M2.
- Acceptance criteria untuk task umum (M3).
- Approval manusia untuk aksi berisiko (M4), dashboard/tracing (M5).

## 3. Desain

### 3.1 Wrapper panggilan LLM (`harness/llm.py`)

Satu-satunya pintu ke provider. Node tidak boleh memanggil model langsung.

1. **Reservasi sebelum kirim.** Hitung token input (Anthropic punya endpoint `count_tokens`; untuk
   provider lain dipakai estimasi konservatif dari jumlah karakter). `max_tokens` output diisi dari
   sisa reservasi node. Kalau input saja sudah tidak muat, panggilan **ditolak sebelum dikirim**.
2. **Budget USD di samping budget token.** Token antar provider tidak setara harganya, jadi
   ditambah `budget.max_usd`. Model tanpa harga di `config.yaml` ditolak, kecuali `allow_unpriced: true`.
3. **Setiap percobaan dicatat**, termasuk yang gagal dan yang di-retry (event `llm_call`: role,
   model, token in/out/cache, USD, latensi, nomor percobaan, status). Ini menutup temuan audit:
   sekarang `guard` hanya menghitung percobaan yang berhasil.
4. **Klasifikasi error.** 429, 5xx, dan timeout dianggap transient (retry dengan backoff + jitter,
   menghormati `Retry-After`). Error 4xx lain langsung gagal.
5. **Timeout per panggilan** dari config per role.

### 3.2 Orchestrator LLM

- Output lewat structured output / tool call dengan skema: daftar task (`id`, `instruksi`,
  `input`, `output yang diharapkan`), maksimal `max_workers`.
- Divalidasi oleh harness (skema, jumlah task, ID unik). Rencana tidak valid dikembalikan ke model
  dengan pesan error, maksimal 2 kali, lalu run gagal dengan alasan `plan_invalid`.
- Revisi iterasi berikutnya menerima feedback evaluator (daftar cek yang gagal), bukan seluruh riwayat.

### 3.3 Worker LLM

- Menerima **hanya potongan konteksnya**: instruksi task, deskripsi tools, feedback yang relevan.
- Loop: panggil model → jalankan tool call → kembalikan hasil → ulangi, sampai model menjawab
  final atau `max_steps` habis (default 6).
- Tool call cacat (nama salah, argumen tidak valid) dikembalikan ke model sebagai error dan
  dihitung sebagai satu langkah.
- **Memo per langkah** dengan kunci `(node, task, iteration, step)`. Saat resume, langkah yang sudah
  ter-commit diputar ulang dari memo tanpa memanggil model lagi. Ini perluasan langsung dari memo M1.
- Estimasi token node = `max_steps × batas per panggilan`, jadi reservasi iterasi M1 tetap berlaku.

### 3.4 Tools dan sandbox

| Tool | Akses | Catatan |
|---|---|---|
| `read_data` | baca-saja folder input | path di-resolve lalu wajib berada di dalam folder input |
| `write_file` | folder `workspace/` milik run | path jail + tulis ke file sementara lalu rename (atomic, aman diulang) |
| `run_python` | sandbox Docker | lihat di bawah |

**Path jail:** `Path.resolve()` lalu `is_relative_to(root)`. Symlink yang mengarah keluar ditolak.
Berlaku untuk semua tool file, dan menutup temuan audit (`../escaped.txt`).

**`run_python` di Docker:** `--network none`, `--read-only`, `--user 65534`, `--cap-drop ALL`,
`--security-opt no-new-privileges`, `--memory 512m`, `--cpus 1`, `--pids-limit 128`, `workspace/`
di-mount read-write, data di-mount read-only, timeout wall-clock 60 detik, output dipotong maksimal
64 KB. Image `python:3.13-slim` (multi-arch, jalan di ARM OCI) **di-pin ke digest** untuk run yang
reproducible. **Tidak ada fallback tanpa sandbox**: kalau Docker tidak tersedia, tool ini menolak
jalan. Mode `sandbox: none` hanya untuk tes dengan model palsu.

**Memo per langkah juga mencakup hasil tool:** setiap tool call yang berhasil di-commit dengan kunci
`(node, task, iteration, step, tool_call_id)` sebelum hasilnya dikembalikan ke model. Replay setelah
crash memakai hasil yang tersimpan, jadi tool tidak dijalankan ulang.

### 3.5 Konfigurasi baru (`config.yaml`)

```yaml
budget:
  max_usd: 0.50
  allow_unpriced: false
roles:
  worker:
    max_steps: 6
    max_output_tokens: 2048
    timeout_s: 60
sandbox:
  kind: docker            # docker | none (tes saja)
  image: python:3.13-slim
  timeout_s: 60
logging:
  prompts: hashed         # hashed | full
```

## 4. Strategi tes

1. **Model palsu terskrip** (`GenericFakeChatModel` dari LangChain dengan respons berisi
   `tool_calls` dan `usage_metadata`; sudah dicek bisa). Kekurangannya, model ini tidak punya
   `bind_tools`, jadi dibuat subclass tipis. Semua perilaku diuji di sini tanpa biaya:
   budget, retry, tool call cacat, rencana tidak valid, `max_steps`.
2. **Tes path jail:** `../`, path absolut, symlink keluar, nama file aneh.
3. **Tes sandbox** (butuh Docker): jaringan mati, filesystem root read-only, tidak bisa menulis di
   luar workspace, timeout membunuh proses, batas memori.
4. **Crash-resume dengan worker LLM palsu:** crash di tengah loop, lalu cek langkah yang sudah
   ter-commit tidak memanggil model lagi (jumlah panggilan model dihitung).
5. **Smoke live (opt-in, `ARGUS_LIVE=1`):** satu run nyata task CSV dengan role default, dibatasi
   `max_usd`. Tidak masuk `verify.sh` supaya verifikasi tetap gratis dan deterministik.
6. **Mutation check** untuk setiap jaminan baru, seperti di M1.

## 5. Definition of Done

- [ ] `verify.sh` lulus di venv bersih, termasuk semua tes M1 (tidak ada regresi).
- [ ] Token dan USD tidak pernah melewati batas, **termasuk percobaan yang gagal** (diuji dengan sapuan nilai batas).
- [ ] Panggilan yang tidak muat di reservasi ditolak sebelum dikirim.
- [ ] Ledger `llm_call` sama persis dengan usage yang dilaporkan provider (model palsu).
- [ ] Path jail menolak semua kasus escape yang diuji.
- [ ] Sandbox: jaringan, filesystem, memori, dan timeout terbukti dibatasi (tes Docker).
- [ ] Crash di tengah loop worker tidak membayar ulang langkah yang sudah ter-commit.
- [ ] Rencana orchestrator yang tidak valid gagal dengan alasan tercatat, bukan crash.
- [ ] Satu run live end-to-end `DONE` di VM OCI ARM, biaya tercatat dan di bawah `max_usd`.
- [ ] Audit GPT setelah fase 2b dan setelah fase 2e.

## 6. Urutan kerja

| Fase | Isi | Bisa diuji tanpa API key? |
|---|---|---|
| 2a | Wrapper LLM, budget USD, ledger per percobaan, model palsu | Ya |
| 2b | Orchestrator LLM + validasi rencana → **audit GPT** | Ya |
| 2c | Worker loop + memo per langkah | Ya |
| 2d | Path jail + sandbox Docker | Path jail ya; Docker lihat risiko |
| 2e | Smoke live + run di OCI → **audit GPT** | Tidak, butuh key dan VM |

## 7. Risiko dan hal yang belum pasti

- **Docker di lingkungan pengembangan.** Daemon Docker bisa jalan di workspace Claude, tapi
  Docker Hub diblokir, jadi image `python:3.13-slim` tidak bisa ditarik di sana. Tes sandbox akan
  di-skip otomatis kalau image tidak ada, dan dijalankan penuh di VM OCI. Perlu Docker terpasang di VM.
- **RAM VM 12 GB** dibagi antara harness dan container. Batas 512 MB per container × 3 worker
  paralel masih aman, tapi perlu diukur.
- **Hitung token input** untuk OpenAI/DeepSeek berupa estimasi, jadi bisa meleset. Mitigasinya
  memberi margin dan mencatat selisih estimasi vs aktual di ledger.
- **Perkiraan biaya live:** sekitar $0.05–0.10 per run dengan Sonnet 5.5 (orchestrator) dan
  Haiku 5.5 (worker). Ini hitungan kasar dari harga publik, bukan hasil ukur.
- **ID model OpenAI** belum diverifikasi, tapi tidak memblokir M2 karena evaluator belum memakai LLM.

## 8. Keputusan yang butuh jawaban Atha

1. **Budget USD:** setuju ditambah? Usul default `max_usd: 0.50` per run.
2. **Docker di VM OCI:** boleh dipasang (`docker.io` dari apt)? Alternatif yang lebih ringan
   (bubblewrap) ada, tapi isolasinya lebih lemah.
3. **Log prompt:** `hashed` (default, hemat dan aman untuk data klien) atau `full` (lebih mudah debug)?
4. **Batas belanja smoke live:** cukup $0.50 per run?
