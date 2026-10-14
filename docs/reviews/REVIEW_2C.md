# Permintaan review: fase 2c (worker loop + memo per langkah)

PR #2, branch `m2-2c` dari `main` `d9f3e78`. Desain: [`DESIGN_2C.md`](DESIGN_2C.md) (termasuk DoD GPT dan hasilnya).
Bukti: `verification/verify-20261014T100348Z-x86_64.log`, 347 tes lulus di venv bersih (crash 5x per titik, stress 50x).

## File utama
- `nodes/llm_worker.py`: loop worker, `ReadData` / `SubmitResult`, titik crash
- `harness/steps.py`: kunci memo langkah, `reservation_from_ledger`
- `nodes/contract.py`: `validate_output` (bentuk output, bukan kebenarannya)
- `nodes/orchestrator.py`: reservasi orchestrator kini dipulihkan dari ledger
- `harness/events.py`: log tahan baris terpotong; `models/fake.py`: skrip per task
- `tests/test_worker_llm.py`: 22 tes

## Klaim terhadap DoD GPT
| DoD | Klaim | Tes |
|---|---|---|
| 1 Loop + batas langkah + budget | `max_steps`, reservasi node per panggilan | `test_max_steps_*`, `test_worker_reservation_too_small_*` |
| 2 Kunci stabil + identitas input | LLM: hash pesan+skema tool+model; tool: + langkah LLM induk + versi tool | `test_changed_*` (feedback, versi tool, model) |
| 3 Hasil tool di-commit sebelum lanjut | `memo.put` sebelum `ToolMessage` ditambahkan | mutasi "commit setelah lanjut" tertangkap |
| 4 Crash setelah langkah berhasil tidak memanggil ulang | lintas proses, 2 titik crash | `test_crash_after_a_committed_step_redoes_nothing` |
| 5 Memo lama tidak dipakai bila input/spec/versi tool berubah | lihat DoD 2 | sama |
| 6 Hitung panggilan ulang, bukan cuma hasil | posisi skrip per task = panggilan model nyata; `step_committed kind=tool` = eksekusi tool | tes crash di atas |
| 7 Memo ≠ exactly-once | crash sebelum commit → tepat 1 panggilan ulang, tercatat dan ditanggung reservasi; tool berefek samping dijadwalkan di 2d (idempotency key = kunci langkah) | `test_crash_before_commit_redoes_one_call_and_counts_it` |

## Temuan tambahan selama 2c
- Kunci memo tool awalnya tidak terikat ke input (ketahuan oleh tes DoD 5); sudah diperbaiki.
- Celah lintas crash: node yang crash dijalankan ulang dengan reservasi penuh (bisa 2× estimasi). Sekarang reservasi dipulihkan dari ledger, untuk worker **dan** orchestrator 2b.

## Mutasi
8 dijalankan, 8 tertangkap: kunci tool tanpa induk, kunci LLM tanpa pesan, reservasi baru setelah crash,
balasan tidak di-commit, memo tool tidak dibaca, commit tool setelah lanjut, log tidak diperbaiki, urutan top3 tidak divalidasi.

## Pertanyaan untuk reviewer
- Orchestrator tidak di-memo per percobaan (biaya ulang setelah crash di tengah planning terhitung dan dibatasi, tapi dibayar). Perlu di-memo juga?
- `validate_output` hanya mengecek bentuk; kebenaran tetap tugas evaluator. Setuju dengan pembagian ini?
