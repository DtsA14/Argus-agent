# Investigasi: `runner.py` gagal setelah resume bila `events.jsonl` punya baris putus

Status 2026-10-21: **temuan dan usulan aturan pemulihan untuk review; tidak ada perubahan kode.** Basis: `main` pada `a50a3e2`.
Yang dikerjakan: inventaris pembaca log event, reproduksi ujung-ke-ujung di VM, dampak ke uang dan ke pemulihan, dan aturan
pemulihan yang diusulkan. Area: **crash-resume (inti)**, jadi proses ketat (tes yang gagal di kode lama, mutan, `verify.sh`).

## 1. Siapa yang membaca `events.jsonl`

| Pembaca | Cara | Baris putus |
|---|---|---|
| `harness/events.py` `EventLog.read` / `parse_lines` | `json.loads` per baris, **melewati** baris yang gagal di-decode, di mana pun posisinya | ditoleransi |
| `harness/steps.py:90` (pemulihan reservasi), `codetask/run.py:129,375` (admission, hasil), `codetask/review.py`, `evals/score.py` (`run_stats`, sejak pilot 1) | lewat `log.read()` / `parse_lines` | ditoleransi |
| **`runner.py` `actual_spend` (baris 25), `read_events` (35), `ledger_totals` (39)**, dipanggil di 117, 121, 126 | `json.loads(l)` pada setiap baris, tanpa `try` | **`JSONDecodeError`** |
| skrip analisis offline (`audit_run.py`, `failure_trace.py`, `analyze_series.py`, `measure_context.py`, `dry_feedback.py`, `sim_admission.py`) | `json.loads` per baris | tidak ditoleransi; di luar jalur produksi |

Jadi **hanya `runner.py`** (runner laporan CSV, jalur produksi) yang tidak toleran. `EventLog` sudah menjanjikan toleransi itu
(`harness/events.py`: "A process killed mid-write can leave a partial last line. On open, a missing final newline is restored").
Tes yang ada, `test_event_log_survives_a_line_cut_by_a_crash` (`tests/test_worker_llm.py:551`), hanya menguji `EventLog` sendiri.
Tes crash-resume (`tests/test_milestone1.py`, `test_worker_llm.py`, ...) mematikan proses di **batas node**, sehingga baris tidak
pernah terpotong; tidak ada tes yang menjalankan `run_task` melewati akuntansi akhir dengan baris putus.

## 2. Reproduksi ujung-ke-ujung (VM, `main.py` pada `a50a3e2`, model palsu, tanpa biaya)

`python main.py --scenario fail_then_pass --run-id rc --runs-dir <tmp> --quiet --crash-at evaluator`, lalu `--resume`.

| Skenario | Hasil |
|---|---|
| **Kontrol**: crash (exit 42), lalu resume | `DONE`, exit 0, `result.json` ada |
| **Baris putus**: crash, lalu satu baris event ditambah setengah (`{"ts": 1, "event": "llm_ca`, mensimulasikan proses mati di tengah tulis), lalu resume | resume #1: **exit 1**, `JSONDecodeError: Unterminated string` dari akuntansi akhir; **tidak ada `result.json`, tidak ada event `run_end`** |
| resume #2 pada run yang sama | **exit 1, error yang sama, tetap tanpa `result.json`** |

Baris putus berada di tengah file (baris 29 dari 67) karena `EventLog` menambah newline saat dibuka, sehingga baris putus itu
berdiri sendiri, dan itu persis kondisi yang dirancang `EventLog` untuk ditoleransi.

## 3. Dampak

- **Pemulihan, bukan uang di dalam run.** Graph sudah selesai (resume #1 menjalankan node yang tersisa dan sampai `END`), tetapi
  hasilnya tidak pernah ditulis. Resume berikutnya tidak menjalankan node apa pun (tidak ada pembelian ulang), lalu gagal di
  tempat yang sama: **run macet permanen** sampai file log diperbaiki manual. Tidak ada jalur resume yang memulihkannya.
- **Uang selama run tidak terpengaruh:** admission dan reservasi memakai `log.read()` yang toleran (`harness/steps.py`).
- **Seberapa mungkin.** `EventLog.emit` menulis satu baris dengan satu `write`; baris di bawah penyangga 8 KiB biasanya masuk
  sebagai satu panggilan sistem, jadi baris putus jarang (baris besar, disk penuh, kegagalan I/O, atau mati di tengah
  penulisan yang terbagi). Tetapi kodenya sendiri sudah dirancang untuk kasus ini, dan akibatnya (macet permanen) berat.

## 4. Apa yang hilang bila baris putus dilewati (tidak ada risiko uang)

| Baris yang putus | Efek pada angka hasil | Penilaian |
|---|---|---|
| `llm_call_started` | permintaan belum terkirim (ditulis sebelum kirim) | aman |
| `llm_call` akhir | `reconcile_ledger` melihat `started` tanpa akhir: **`unknown_after_crash`, ditagih worst case** | aman, konservatif (kontrak yang ada) |
| `body_done` | `tokens_spent` kurang (diagnostik "kerja yang dilakukan", tidak dipakai keputusan) | tidak menyentuh uang; kurang dari kenyataan |
| `budget_violation` | `budget_violations` kurang (status `FAILED_BUDGET` tetap ada di checkpoint) | diagnostik |

Jadi toleransi aman untuk uang; hanya dua angka diagnostik yang bisa kurang, dan itu sebabnya sebaiknya **terlihat** (bagian 5, R3).

## 5. Aturan pemulihan yang diusulkan (untuk disetujui sebelum implementasi)

- **R1. Satu pembaca.** `runner.py` memakai `parse_lines` / `EventLog.read` yang sama dengan jalur lain; tiga pembaca `json.loads`
  pribadi dihapus atau menjadi pembungkus. Tidak ada aturan parsing baru.
- **R2. Aturan toleransi = `parse_lines`.** Baris yang gagal di-decode dilewati **di mana pun posisinya** (setelah crash dan resume
  baris putus ada di tengah). Baris JSON valid dibiarkan apa adanya (semua `emit` menulis objek; tidak ada kasus non-objek yang
  teramati).
- **R3. Kehilangan terlihat.** `result.json` mendapat kunci `events_skipped` (jumlah baris yang tidak bisa di-decode; 0 normalnya)
  sehingga `tokens_spent` dan `budget_violations` yang mungkin kurang tidak tampak lengkap diam-diam. *Keputusan untuk GPT.*
- **R4. Run yang sudah macet pulih.** Dengan R1, `--resume` pada run macet (graph selesai, tanpa `result.json`) menulis
  `result.json`; teruji.
- **R5. Tidak diubah:** `EventLog`, `reconcile_ledger`, `graph.py`, `harness/guard.py`, memo, titik crash, `codetask/`, dan skrip
  analisis offline (tindak lanjut terpisah).

## 6. Rencana tes dan mutan (setelah keputusan)

**Gagal di kode lama:**
1. unit: `actual_spend`, `read_events`, `ledger_totals` pada log dengan baris putus di tengah: hasil sama dengan log yang sama
   tanpa baris itu;
2. **integrasi (subprocess `main.py`)**: crash di node, tambah baris putus, `--resume`: exit 0, `result.json` ada, dan isinya
   (`status`, `iteration`, `tokens_used`, `usd_billed`, `llm_calls`) sama dengan kontrol tanpa baris putus;
3. run macet: graph selesai dan `result.json` dihapus, baris putus ada: `--resume` menulis `result.json`;
4. **invarian uang:** `llm_call_started` diikuti `llm_call` yang putus: `ledger_totals` menagih worst case dan
   `unknown_after_crash == 1`, tidak 0;
5. (bila R3 disetujui) `events_skipped` sama dengan jumlah baris putus, dan 0 pada log utuh.

**Mutan:** kembali ke `json.loads` per baris; hanya melewati baris **terakhir** (bukan yang di tengah); membaca toleran tetapi
membuang `llm_call_started` yang tidak punya akhir (biaya menjadi 0); menghitung `events_skipped` salah atau selalu 0; satu dari
tiga fungsi lama tetap memakai `json.loads`.

**Gerbang merge:** tes yang gagal di kode lama, mutan semua tertangkap, `verify.sh` penuh (0 skip sandbox), termasuk tes
crash-resume yang ada (`tests/test_milestone1.py`, `test_runner_budget_resume.py`, `test_worker_llm.py`).

## 7. Keputusan yang dibutuhkan dari GPT

1. R1 dan R2: `runner.py` memakai `parse_lines` apa adanya (melewati baris tak ter-decode di mana pun)?
2. R3: tambahkan `events_skipped` ke `result.json` (usulan gue: ya, kunci aditif, 0 normalnya), atau cukup perilaku tolerannya?
3. R4: run yang sudah macet dipulihkan lewat `--resume` biasa (tanpa alat khusus)?
4. Skrip analisis offline yang masih `json.loads` per baris: tindak lanjut terpisah, bukan di PR ini?
5. Satu PR kecil khusus `runner.py` (dan tesnya), tanpa menyentuh yang lain?
