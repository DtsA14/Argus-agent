# Review: task umum slice 1, bagian B (loop agen, status run, budget, kontrak beku, crash-resume)

Kontrak: `docs/reviews/ACCEPTANCE_GENERAL.md`. Inti deterministik: bagian A (PR #21). Bagian ini menambahkan agen
yang benar-benar mengerjakan task, dengan model palsu saja. **Tidak ada run live.**

## Yang dibangun

| File | Isi |
|---|---|
| `codetask/status.py` | status run dan transisi legal; transisi ilegal raise `IllegalTransition` |
| `codetask/frozen.py` | kontrak dibekukan ke `<run>/contract.json` (sha256 di state); dicek di setiap node |
| `codetask/tools.py` | tool agen: `ListFiles`, `ReadFile`, `WriteFile`, `RunValidation`, `Finish`, lewat path jail workspace |
| `codetask/agent.py` | satu attempt: loop tool-calling dengan memo per langkah (pola worker M2) |
| `codetask/run.py` | graph `setup → agent → acceptance → (agent → acceptance)*`, admission dari ledger, resume |
| `scripts/run_code_task.py` | CLI; model sungguhan butuh `ARGUS_LIVE=1` |
| `tools/sandbox.py` | label `argus.run=<run_id>` di kontainer, dan `remove_labeled` untuk kontainer yatim |
| `config.yaml` | role `coder`, allowlist `tools.coder`, batas `code_task` |

## State machine

```
            ┌────────────── kontrak tidak valid / repo input / scope ──────────► BLOCKED (invalid_contract)
            ├────────────── sandbox tidak tersedia ────────────────────────────► BLOCKED (sandbox_unavailable)
 (mulai) ── setup ── attempt 0 tidak muat budget ──────────────────────────────► FAILED_BUDGET
            │
            ▼ RUNNING
          agent(i) ── kontrak beku berubah ──────────────────────────────────► BLOCKED (contract_changed)
            │ attempt selesai: Finish / max_steps / reservasi habis / provider gagal / balasan terpotong
            ▼
        acceptance(i) ── pass ───────────────────────────────────────────────► DONE
            │ ── blocked (sandbox hilang) ─────────────────────────────────────► BLOCKED (sandbox_unavailable)
            │ ── fail, attempt berakhir karena provider gagal ─────────────────► BLOCKED (provider_failed)
            │ ── fail, dan i+1 = max_iterations / gagal sama N kali / budget ──► FAILED_ACCEPTANCE (alasan)
            └── fail, attempt berikutnya diizinkan ──► RUNNING, agent(i+1) dengan feedback kriteria yang gagal
```

Transisi legal (`codetask/status.py`): `None → RUNNING | BLOCKED | FAILED_BUDGET`, `RUNNING → RUNNING`, dan
`RUNNING → status terminal mana pun`. Status terminal tidak pernah berubah, juga tidak saat resume (diuji: resume
run yang sudah DONE tidak memanggil model dan tidak menambah biaya). `BLOCKED` wajib membawa `blocked_reason` dari
daftar tetap, dan hanya `BLOCKED` yang boleh membawanya. Setiap transisi dicatat sebagai event `status`.

Kalau attempt berakhir karena alasan apa pun, harness tetap memeriksa workspace. Pemeriksaan ini gratis dan
deterministik, jadi perbaikan yang sudah benar tetap bisa `DONE`. Alasan berakhirnya attempt hanya menentukan
langkah sesudahnya.

## Jawaban untuk dua pertanyaan review

**1. Apakah `BLOCKED` hanya untuk hambatan yang bisa dipulihkan?** Tidak. `BLOCKED` berarti run tidak bisa lanjut
tanpa manusia, baik yang bisa dipulihkan (sandbox mati, provider gagal) maupun yang permanen (kontrak tidak valid,
kontrak beku berubah). Alasannya selalu eksplisit di `blocked_reason`: `invalid_contract`, `contract_changed`,
`sandbox_unavailable`, atau `provider_failed`. `BLOCKED` terminal untuk run itu: setelah penyebabnya diperbaiki,
manusia memulai run baru. Ini sesuai asumsi reviewer.

**2. Apakah resume memakai ledger persisten atau menghitung ulang dari checkpoint?** Ledger. Event
`llm_call_started` dan `llm_call` di `events.jsonl` adalah sumber kebenaran, dan checkpoint tidak pernah dipakai untuk
uang.
- **Admission attempt** (`admission` di `codetask/run.py`): total dari `reconcile_ledger`. Panggilan yang terpotong
  crash dihitung worst case. Attempt baru hanya diizinkan kalau total itu ditambah reservasi penuh satu attempt
  masih muat di `max_usd` (yang paling ketat dari config dan kontrak) dan `max_tokens`.
- **Reservasi attempt** (`reservation_from_ledger`): dimulai dari apa yang attempt yang sama sudah habiskan di proses
  sebelumnya. Jadi crash tidak bisa memberi attempt budget dua kali.
- Akibatnya resume tidak bisa mengembalikan uang yang sudah terpakai. Tes: panggilan yang terpotong crash membuat
  attempt berikutnya ditolak (`test_admission_counts_calls_cut_off_by_a_crash_at_their_worst_case`), dan
  `reservation_restored` setelah crash membawa panggilan yang hilang.

## Crash-resume: batas transaksi

Tidak ada klaim exactly-once. Jaminannya: yang sudah di-commit tidak pernah diulang, dan satu-satunya langkah yang
bisa terulang aman diulang.

| Titik crash | Yang terjadi saat resume | Tes |
|---|---|---|
| `setup@after_copy` | workspace sisa dihapus lalu disalin ulang (agen belum pernah jalan) | ✔ |
| `agent@after_llm` | balasan belum di-commit: dibeli lagi, **keduanya** ada di ledger dan dibayar | ✔ |
| `agent@llm_committed` | balasan diputar ulang dari memo, tanpa panggilan model | ✔ |
| `agent@after_tool:WriteFile` | write sudah jalan tapi belum di-commit: dijalankan lagi, dan file akhirnya sama persis dengan setelah satu kali write | ✔ |
| `agent@after_tool` (tool pertama, ReadFile) | read yang belum di-commit dijalankan lagi, dengan hasil yang sama | ✔ |
| `agent@tool_committed`, `agent@after_commit` | tidak ada yang diulang | ✔ |
| `acceptance@after_verdict` | verdict dihitung ulang (gratis, read-only), dengan digest workspace yang sama | ✔ |
| `acceptance@after_commit` | verdict yang sudah di-commit tidak dihitung ulang | ✔ |
| crash saat validasi berjalan | kontainer yatim berlabel run ini dihapus saat resume | ✔ |

Setiap tes crash lintas proses memeriksa empat hal: tidak ada langkah LLM, langkah tool, atau node yang sudah
di-commit yang diulang; jumlah panggilan model sama dengan run tanpa crash (kecuali `after_llm`, yang membeli ulang
tepat satu dan mencatat keduanya); setiap panggilan ada di ledger; dan hasil akhirnya `DONE` dengan file yang benar.

Tool dibuat aman diulang. Yang harus sama saat diulang adalah **efeknya**: write mengganti seluruh file secara atomik,
jadi dua kali write meninggalkan file yang sama. `RunValidation` read-only. Teks hasil dari tool yang belum di-commit
tidak pernah dilihat oleh langkah yang sudah di-commit (commit selalu sebelum lanjut), jadi teks itu tidak wajib sama;
mutation check di bawah membuktikannya. Checkpoint tetap `durability="sync"`.

## Kontrak beku

- Setup membaca kontrak dari file manusia **sekali**, memvalidasi, lalu menulis JSON kanonisnya ke
  `<run>/contract.json`. Sha256-nya disimpan di state.
- Node `agent` dan `acceptance` memuat salinan beku itu dan mengecek hash-nya. Kalau berubah, run `BLOCKED
  (contract_changed)`.
- File kontrak di repo tidak pernah dibaca lagi. Tes membuktikan dua hal: kalau file manusia dirusak di tengah run
  atau saat crash, run tetap selesai dengan kontrak beku; kalau salinan beku diubah saat crash, run diblokir.

## Lingkup agen

- Tool tulis menolak path yang protected, di luar `writable`, `SUMMARY.json` (hanya lewat `Finish`), traversal
  (`../`), dan path absolut, sebelum menulis apa pun. Acceptance tetap memeriksa ulang dari snapshot.
- Allowlist `tools.coder` ditegakkan di harness. Tool yang tidak diizinkan dijawab "Denied" dan tidak dijalankan.
- `Finish` harus satu-satunya panggilan di balasannya, dengan schema `claims_v1`. Kalau tidak, ditolak dan tidak ada
  yang ditulis.
- Setiap `tool_call_id` dijawab. Tes memakai model palsu ketat yang menolak request dengan id yang tidak dijawab,
  seperti DeepSeek.

## Batasan

- **Hanya model palsu.** Angka `attempt_tokens` (30.000) adalah titik awal yang dikoreksi dari ledger run live
  pertama, yang butuh persetujuan terpisah.
- **`max_seconds` global masih soft limit**, sesuai keputusan PR #20. Yang keras adalah timeout per validasi.
- **Kontainer yatim hanya dibersihkan saat resume.** Kalau run yang crash tidak pernah di-resume, kontainernya
  berjalan sampai kodenya selesai (tanpa network, dengan batas memori dan pids).

## Mutation check (VM, `tests/test_codetask.py` + `tests/test_codetask_crash.py`)

Total **27 mutan** dijalankan: 26 di run pertama dan 1 tambahan.
- **1 ekuivalen, tidak dihitung**: teks hasil `WriteFile` diberi timestamp, sehingga berbeda kalau diulang. Mutan ini
  lolos karena memang tidak berpengaruh. Hasil tool yang belum di-commit tidak pernah dipakai langkah yang sudah
  di-commit, jadi pengulangan setelah crash tidak membeli ulang apa pun. Awalnya dokumen ini mengklaim teks hasil
  harus sama; klaim itu sudah dikoreksi.
- **26 mutan efektif, semuanya tertangkap**: 25 dari run pertama, ditambah 1 mutan tambahan yang merusak efek yang
  benar-benar dijaga. Mutan itu membuat write yang diulang menambahkan isi alih-alih mengganti file. Ia hanya
  tertangkap oleh tes crash `agent@after_tool:WriteFile`, yaitu tes yang memang menjaga jaminan ini.

Daftar mutan mencakup: transisi status (restart dari status terminal, BLOCKED tanpa alasan atau dengan alasan
asing), validasi kontrak di setup, preflight sandbox, admission attempt 0 dan attempt berikutnya, panggilan yang
terpotong crash tidak dihitung, verdict blocked diperlakukan sebagai fail, provider gagal lalu diulang, hash kontrak
beku tidak dicek, scope tulis (protected, di luar writable, `SUMMARY.json`), allowlist, schema dan aturan "Finish
sendirian", commit balasan dan hasil tool, reservasi tidak dipulihkan dari ledger, kontainer yatim dibiarkan, salinan
setup yang crash dipakai ulang, dan saklar `ARGUS_LIVE`.

## Perbaikan setelah review GPT: overspend menjadi `FAILED_BUDGET` yang durable

**Temuan reviewer:** saat ada overspend (`EstimateExceeded`), handler hanya mengubah status di memori dan menulis
`result.json`. Guard melempar exception sebelum hasil node di-commit, jadi checkpoint masih menyimpan attempt sebagai
pekerjaan yang tertunda.

**Dampak yang terbukti** (handler lama, dicek di VM): resume menjalankan node `agent` lagi. Panggilan modelnya
ditolak sebelum dikirim, karena reservasi dipulihkan dari ledger, jadi tidak ada uang yang keluar. Tapi run yang
seharusnya terminal ternyata dilanjutkan, dan itu melanggar state machine.

**Perbaikan** (`codetask/run.py`): `FAILED_BUDGET` ditulis ke checkpoint lewat `graph.update_state(..., as_node="agent")`.
Routing setelah `agent` langsung ke `END`. Handler juga memastikan status sudah tersimpan dan tidak ada node yang
tertunda; kalau tidak, ia raise.

**Tes regresi:** `test_an_overspend_is_a_durable_failed_budget_that_resume_does_not_continue`, lintas proses dengan
sandbox sungguhan. Provider menagih 45.000 token input, padahal reservasi attempt 30.000. Run pertama berakhir
`FAILED_BUDGET`, dan overspend-nya tercatat di ledger. Lalu sebuah **proses baru** me-resume run itu dan tes
memeriksa:
- statusnya tetap `FAILED_BUDGET` dengan alasan yang sama;
- jumlah panggilan model tidak bertambah, dan `usd_billed` sama;
- tidak ada event `llm_call`, `llm_call_started`, `node_start`, atau `status` baru.

Tes ini **gagal dengan handler lama** dan lulus dengan perbaikannya. Satu catatan jujur: percobaan revert pertama
tidak berlaku karena bug di skrip mutasiku sendiri (`index()` menemukan baris yang lebih awal). Baru setelah
diperbaiki (`rindex`, dan dicek bahwa `update_state` benar-benar hilang dari file), tes itu terbukti menangkap bug ini.

Hitungan mutasi bagian B sekarang: 28 dijalankan, 1 ekuivalen, **27/27 efektif tertangkap**.

