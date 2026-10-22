# Router v0: implementasi

Status: **implementasi untuk review.** 2026-10-23. Spec: `docs/reviews/SPEC_ROUTER_V0.md` (K2–K7 disetujui, K1 ditunda,
dengan tiga tambahan dari review). Belum ada run live.

## 1. Yang dibuat

| Berkas | Isi |
|---|---|
| `router/job.py` | job (state, `job.json` atomik, log keputusan dengan waktunya), kunci per job (`flock`), uang job, langkah live, perintah `start_code`, `approve`, `reject`, `redraft`, `resume`, `status` |
| `scripts/argus.py` | CLI: `code`, `status`, `approve --sha`, `reject`, `redraft`, `resume` |
| `codetask/run.py` | `run_code_task(root=...)`; `None` berarti `ROOT` yang dibaca saat dipanggil, jadi perilaku bawaan tetap sama |
| `config.yaml` | bagian `router:` (`job_max_usd` 1,00, `draft_max_usd` 0,75, `agent_max_usd` per profil, dan `overrides` untuk setiap tahap: setup pilot W2b) |
| `.gitignore` | `jobs/` |

## 2. Jaminan dan buktinya (`tests/test_router.py`, 25 tes, model dan validasi palsu)

| Jaminan | Tes |
|---|---|
| Satu job: draf, berhenti di `AWAITING_APPROVAL` tanpa agen, `approve`, agen `DONE`, paket review valid; urutan state tercatat | `test_a_job_drafts_waits_for_approval_...` |
| Root per job; `fixtures/` checkout tidak berubah; `jobs/` diabaikan git | `test_a_job_has_its_own_root_...`, `test_jobs_are_ignored_by_git` |
| Agen tidak pernah mulai tanpa approve; job yang ditolak tidak menerbitkan apa pun | `test_the_agent_never_starts_without_approval`, `test_a_rejected_job_cannot_be_approved` |
| Menolak konfirmasi tidak memulai apa pun | `test_not_confirming_starts_nothing` |
| Cap agen = min(profil, sisa job); tahap yang tidak bisa mendanai satu attempt tidak dimulai (`BLOCKED`), baik drafter maupun agen; pengeluaran dijumlahkan lintas tahap | 4 tes |
| **Cap tahap yang di-resume = cap saat mulai** (agen: walau cap job diturunkan; drafter: walau cap job dinaikkan), dengan run id yang sama dan `resume=True` | `test_a_resumed_stage_keeps_the_cap_it_started_with`, `test_a_resumed_drafter_keeps_its_cap_and_its_run` |
| **Kunci per job**: `approve`, `redraft`, `reject`, `resume` ditolak saat kunci dipegang, tanpa mengubah `job.json`; `status` tetap jalan; proses yang mati melepas kunci | 2 tes |
| **Approve terikat ke draf**: sha wajib (≥ 12 karakter, sama dengan draf); draf yang berubah setelah `status` atau saat layar approve dibaca ditolak; kontrak yang berubah setelah approve membuat agen `BLOCKED` | 4 tes |
| Kunci API: bentuk dicek, ditolak tanpa terminal, hanya ada di lingkungan selama tahap, tidak tertulis di berkas job mana pun | 3 tes (6 kasus) |
| CLI menjalankan job dan mencetak perintah approve | `test_the_cli_runs_a_job_...` |

**Mutan:** `verification/mutants-router-v0-20261023-b4dcaf2.log`, **18/18**: kunci per job, cap dihitung ulang saat resume
(agen dan drafter), cap tidak dibatasi job (agen dan drafter), approve tanpa sha, draf yang berubah di layar diterima,
kontrak tidak diikat, approve di state mana pun, kunci tertinggal di lingkungan, tanpa terminal, konfirmasi diabaikan,
bentuk kunci tidak dicek, pengeluaran tidak dihitung, run agen/drafter di luar root job, cap tahap tidak menjadi budget
run, dan `root` diabaikan di `run_code_task`.

## 3. Catatan

- Router sendiri tidak memanggil model. Semua panggilan tetap lewat `run_drafter`/`run_code_task` dengan reservasi dan
  ledger yang sama.
- Saat approve, konfirmasi approve dan konfirmasi tahap agen digabung menjadi satu layar. Layar itu menampilkan sha
  draf, writable, validasi beserta node wajib, tool, profil, satu attempt, cap agen, dan status referensi, lalu
  `[y/N]`, lalu kunci.
- Pilot config W2b (`config_w2b1.yaml`, `config_w2b2_*.yaml`) kini berbeda satu bagian lagi dari `config.yaml`
  (`router:`), jadi gerbangnya akan menolak. Pilot-pilot itu sudah selesai.
- Saat dijalankan dengan `-n 4` **tanpa** `--dist loadgroup`, dua crash test sandbox sempat gagal (container dibersihkan
  bersamaan). Dijalankan berurutan: 7/7 lulus. `verify.sh` memakai `loadgroup`.
