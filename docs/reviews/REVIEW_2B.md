# Permintaan review: patch audit 2a + fase 2b (orchestrator LLM)

Branch `m2-2b` (commit `7420fb8`), berisi `main` (`9db4111`, patch 2a) + 2b.
Bukti: `verification/verify-20261014T092545Z-x86_64.log` (309 tes lulus di venv bersih,
crash-resume 5x per titik + 50x stress worker paralel).

## Bagian A: konfirmasi patch 2a (commit `9db4111` di main)

| Temuan GPT | Status | Bukti |
|---|---|---|
| Model tanpa harga melewati kontrol USD | Ditolak selama `max_usd` finite; biaya `null`, bukan $0; `usd_complete: false` | `test_llm_audit_2a.py` (sebelum patch: 2 juta token lolos budget $0,000001, tercatat $0) |
| Heuristic tidak menghitung tool calls | Menghitung konten, argumen tool call, id, hasil tool, skema | tes loop tool 1/3/6 putaran (sebelum: 6000 karakter argumen = +20 token) |
| Ledger tidak atomik dengan reservasi | `llm_call_started` → request → `llm_call` → charge (charge tetap terjadi walau tulis ledger gagal); `call_id`; `reconcile_ledger()` → `unknown_after_crash` dihitung worst case | tes crash di tengah request, tes disk penuh |
| Status request tidak diketahui | `delivery: received` (ada HTTP status) / `unknown` (timeout/koneksi) | tes 503 vs timeout |
| Estimate miss | `budget_violation` eksplisit, panggilan berikutnya ditolak, run `FAILED_BUDGET` (bukan exception); README tidak lagi mengklaim hard cap finansial untuk heuristik | tes overshoot + tes run |
| Meta bisa menimpa field sistem | Whitelist `run_id, node, task, iteration, step, tool_call_id`, ditolak sebelum kirim | Temuan tambahan kami: meta `role` dulu bikin crash **setelah** provider dibayar |
| Presisi USD | Integer nano-dollar di ledger dan reservasi | Float tidak bisa cocok persis: `sum()` Python 3.12+ terkompensasi, `+=` tidak |

Mutasi: 8 dijalankan, 7 tertangkap. Yang lolos (cek "reservasi sudah dilanggar") ternyata redundan,
karena sisa negatif sudah membuat batas output negatif dan request ditolak, jadi kodenya dihapus.

## Bagian B: fase 2b

File utama: `nodes/plan.py` (skema `SubmitPlan` + `validate_plan`), `nodes/orchestrator.py`
(`make_llm_orchestrator`), `nodes/contract.py`, `tests/test_orchestrator_llm.py`.

Klaim yang minta dicek:
1. Rencana divalidasi harness: skema, ID unik/valid, ≤ `max_workers`, output wajib tepat sekali, output tak dikenal ditolak.
2. Rencana tidak valid dikembalikan ke model dengan error persisnya (satu `ToolMessage` per tool call, sesuai syarat Anthropic), maksimal `plan_attempts` panggilan, lalu `FAILED_PLAN` tanpa menjalankan worker.
3. Error model permanen → `FAILED_LLM`; reservasi node habis → `FAILED_BUDGET`; tidak ada exception mentah.
4. Revisi menerima rencana sebelumnya + cek evaluator yang gagal.
5. Semua panggilan model lewat `LLMCaller`: ada tes yang gagal kalau node/harness/graph memanggil `.invoke/.stream/.batch` atau `build_chat_model` langsung.
6. Crash-resume lintas proses dengan provider palsu berbasis file: rencana yang ter-commit tidak pernah dibeli ulang (jumlah panggilan model dihitung).

Keputusan desain yang minta dinilai:
- Kontrak antar node pindah dari ID task ke **nama output + iterasi**, supaya planner bebas memilih ID dan hasil basi iterasi lama tidak terbawa.
- `impl.orchestrator` default tetap `fake` sampai run live (2e).

Risiko yang kami sadari:
- Estimasi token orchestrator 3000 (dibuat untuk node palsu) hanya muat ~2 percobaan LLM; akan disetel dari ledger di 2e.
- `tool_choice` yang dipaksa belum diuji ke provider nyata (DeepSeek mode thinking mungkin menolak); ada saklar `force_tool: false`.

## Tanggapan atas audit 2b (GPT, 2026-10-14)

| Temuan | Status |
|---|---|
| P2: rencana diterima walau balasan model berisi tool call lain selain `SubmitPlan` | **Terbukti** (direproduksi: run `DONE`, 3 worker jalan). **Diperbaiki:** balasan harus tepat satu tool call dan itu `SubmitPlan`; selain itu ditolak dengan pesan yang menyebut tool asingnya, setiap tool call dijawab `ToolMessage`, dan tidak ada worker sebelum rencana valid. 4 tes regresi; mengembalikan cek lama membuat 4 tes gagal |

Bukti verifikasi terbaru ada di `verification/` (log dengan timestamp paling akhir).
