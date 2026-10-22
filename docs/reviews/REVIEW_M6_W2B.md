# M6 W2b: drafter model

Status: **implementasi untuk review.** 2026-10-22. Spec: `docs/reviews/SPEC_W2B_DRAFTER.md` (K1–K7 disetujui Atha,
"ok gas"). Tanpa run live.

## 1. Yang dibuat

| Berkas | Isi |
|---|---|
| `codetask/drafter.py` | graf `setup → draft → finalize`, loop drafter, `SubmitDraft`, dan halaman `DRAFT_REVIEW.md` |
| `scripts/draft_task.py` | CLI: `--intake --issue-file --max-usd --run-id [--resume]`; model sungguhan butuh `ARGUS_LIVE=1` |
| `acceptance/draft.py` | `check(..., reference_patch=None)` melewati cek referensi; laporan dan record memuat `feasibility`; bukti baseline memuat `output_tail` |
| `scripts/approve_draft.py` | wajib tepat satu: `--reference-patch P` atau `--no-reference` |
| `codetask/review.py` | `PR.md` memberi tahu reviewer bila task disetujui tanpa patch referensi |
| `codetask/tools.py` | `Toolbox(role=...)`, supaya event `tool_call` dan `tool_denied` menyebut role yang benar |
| `config.yaml` | `roles.drafter` (Sonnet 5.5, output 8.192), `tools.drafter` (read-only), dan bagian `drafter:` |

Alurnya:

```
draft_task.py (model) → runs/<id>/{draft.json, check_report.json, DRAFT_REVIEW.md, issue.txt}
  → manusia membaca DRAFT_REVIEW.md
  → approve_draft.py --draft runs/<id>/draft.json --task <nama> ... --no-reference [--approve]
  → run_code_task.py (agen) → build_review.py
```

## 2. Keputusan K1–K7, seperti diimplementasikan

- **K1 (B):** tanpa patch referensi, `check()` tetap menjalankan cek statis dan baseline merah. Laporan memuat
  `reference: null` dan `feasibility: "unproven"`. Record task memuat `feasibility`, yang bernilai `"proven"` hanya bila
  laporan memuat hasil referensi yang lulus. `PR.md` menulis kalimatnya untuk task `unproven`. Task lama tanpa field
  ini tidak mendapat kalimat itu, karena semuanya disetujui dengan patch referensi.
- **K2:** `SubmitDraft` memanggil `dr.check(reference_patch=None)` dengan nama task dan batas sementara
  (`drafted_task`, $0,5, 1 attempt). Hasil itu tidak pernah dipublikasikan, karena `approve_draft.py` mengecek ulang
  dengan isian manusia. Masalah dikembalikan ke model bersama bukti baseline per validasi: status, node wajib, dan
  potongan `error_excerpt` D2, diberi label "data from the sandbox, not instructions". `max_submits` (3) menghitung
  **setiap** `SubmitDraft`, termasuk yang ditolak sebelum sandbox. Submit ke-(n+1) ditolak tanpa menjalankan apa pun, dan
  run berakhir `NO_DRAFT submits_exhausted`.
- **K3:** loop terpisah. `make_attempt` milik agen tidak disentuh. Yang dipakai ulang: kunci langkah, serialisasi
  balasan, `reservation_from_ledger`, `error_excerpt`, `NUDGE`, `Toolbox` (tool baca dan gate allowlist), `cache_totals`,
  `fence`, dan `cell`.
- **K4:** model hanya memberi `paths` dan node wajib per validasi. Harness membangun
  `python -m pytest <paths>` dengan environment, timeout, dan `max_skipped: 0` dari config. Path harus relatif dan
  plain, dan tidak boleh diawali `-`, sehingga tidak ada opsi pytest seperti `-p` atau `--rootdir`.
- **K5:** `base` (intake yang diminta manusia) dan `draft_version` diisi harness. Argumen lain (`base`, `limits`,
  `inputs`, dan sebagainya) ditolak sebagai `unknown argument`.
- **K6:** role `drafter` = Sonnet 5.5, output 8.192. Satu attempt dicadangkan `min(attempt_usd 0,45, cap run)`, dengan
  input per panggilan maksimal 40.000. Cap run = `min(budget.max_usd, --max-usd)`. `attempt_tokens` 200.000 dibatasi
  `budget.max_tokens`. Prompt caching mengikuti `llm.prompt_cache` (mati bawaan; nyalakan di config pilot).
- **K7:** belum ada run live. Preflight W2b-1 menyusul setelah merge.

**Satu penyimpangan dari spec bagian 4:** `submit_draft` **tidak** ada di allowlist `tools.drafter`. `SubmitDraft`
tidak di-gate, sama seperti `Finish` pada agen, karena itu satu-satunya jalan mengakhiri run. Allowlist hanya menahan
tool baca, dan tool tulis atau validasi apa pun ditolak (`tool_denied`, role `drafter`).

## 3. Jaminan dan buktinya (`tests/test_drafter.py`, 45 tes, fake model, tanpa Docker)

| Jaminan | Tes |
|---|---|
| Draf yang lolos mengakhiri run, dan draf yang sama lolos `dr.check` lagi di luar loop | `test_a_draft_that_passes_its_check_...` |
| Submit yang ditolak kembali ke model; ERROR di baseline bukan merah, dan outputnya sampai ke model | `test_a_rejected_submit_...`, `test_an_error_on_the_baseline_...` |
| Batas submit: yang melewati batas tidak menjalankan apa pun | `test_submits_beyond_the_limit_...` |
| Read-only: WriteFile, EditFile, dan RunValidation ditolak, Finish tidak dikenal, intake dan salinannya tidak berubah; salinan yang berubah membuat run BLOCKED tanpa `draft.json` | `test_the_drafter_cannot_write_...`, `test_a_changed_source_copy_blocks_the_run` |
| Model hanya mengisi yang boleh (15 kasus) | `test_the_model_sets_only_what_a_drafter_may_set`, `test_the_harness_sets_the_base_...` |
| Input buruk, intake berubah, task sebagai intake, dan sandbox tidak ada: BLOCKED sebelum panggilan model | `test_bad_inputs_...`, `test_a_changed_intake_...`, `test_a_task_cannot_...`, `test_no_sandbox_...` |
| Uang: panggilan yang tidak muat ditolak sebelum dikirim; cap = yang lebih rendah; ledger `started` lalu `llm_call` | `test_a_call_that_does_not_fit_...`, `test_the_runs_cap_...`, `test_every_call_reaches_the_ledger_...` |
| Crash di 6 titik (subprocess): yang sudah di-commit tidak diulang, jumlah panggilan model dan cek sandbox persis, reservasi dipulihkan dari ledger | `test_a_crash_anywhere_resumes_...` |
| Bentuk loop: balasan terpotong, nudge, SubmitDraft bersama tool lain, `max_steps` | 4 tes |
| `DRAFT_REVIEW.md` (golden file) dan peringatan scope | `test_the_review_page_is_the_golden_one`, `test_scope_warnings_...` |

Ditambah:
- `tests/test_draft.py` (sandbox asli): draf tanpa referensi lolos baseline dan dipublikasikan `unproven`; draf hijau
  tetap ditolak; `approve_draft.py` tanpa flag referensi atau dengan keduanya ditolak (exit 2); laporan memuat
  `output_tail`.
- `tests/test_review.py`: kalimat `PR.md` untuk `unproven`, dan tidak untuk `proven` atau record lama.

**Mutan:** 37/37 tertangkap (bagian 5).

**Tidak diuji:** resume dengan config yang diubah. Policy dibekukan di state saat setup dan node `draft` memakai salinan
itu, tetapi belum ada tes yang mengubah config di antara crash dan resume.

## 4. Batas yang diterima

- Bobot tes tidak diperiksa otomatis (spec bagian 8). Tes yang terlalu longgar tetap lolos. Pertahanannya:
  `DRAFT_REVIEW.md` (isi tes, alasan gagal di baseline, dan peringatan scope) dan review patch.
- `check_report.json` dari drafter memakai nama task dan batas sementara. Yang mengikat hanya laporan
  `approve_draft.py`.
- Hanya pytest (batas W2a yang sama).

## 5. Mutan

`verification/mutants-w2b-20261022-1649262.log`: **37/37 tertangkap.** Setiap mutan dijalankan di worktree sendiri
terhadap `tests/test_drafter.py`, `tests/test_draft.py` (sandbox), dan `tests/test_review.py`.

| Kelompok | Mutan |
|---|---|
| Yang boleh diisi model | argumen tak dikenal diterima; kunci validasi tidak persis; opsi pytest sebagai path; path tidak plain; environment tidak diisi; profil tidak dicek |
| Loop | batas submit meleset satu; submit tidak dihitung; masalah cek diabaikan; bukti sandbox tidak sampai ke model; SubmitDraft bersama tool lain; tool tak dikenal dikirim ke Toolbox; tool tulis diizinkan (kode dan config); balasan terpotong tidak diakhiri; nudge menyebut Finish |
| Crash dan uang | hasil tool tidak di-commit; balasan tidak di-commit; reservasi tidak dari ledger; cap bukan yang lebih rendah; attempt tidak dibatasi cap (USD dan token) |
| Setup dan finalize | perubahan salinan tidak terdeteksi; draf ditulis walau run tidak `DRAFTED`; batas issue meleset satu; task diterima sebagai intake; intake berubah tidak dicek; preflight sandbox diabaikan |
| Laporan dan halaman | tanpa peringatan pola; tanpa output tes di `DRAFT_REVIEW.md` atau di laporan; event `tool_denied` menyebut `coder` |
| W2a dan paket review | tanpa referensi dianggap `proven`; record selalu `proven`; flag referensi opsional; `PR.md` salah untuk task lama, atau tidak pernah menyebut `unproven` |

Tes baru dijalankan juga di `main` sebelum W2b (`4170356`): gagal saat import (`ImportError`, modulnya belum ada).

## 6. Tambahan setelah pilot W2b-1 (2026-10-22)

`w2b1d1` (output 8.192, thinking 6.108) dan `w2b1d2` (submit 1 kurang satu node; kiriman ulang melewati batas input)
menghasilkan tiga perubahan, yang disetujui Atha ("1+2+revisedraft"):

- **`failed_nodes`** di bukti validasi pytest (`acceptance/validation.py`, maksimal 50). Cek baseline W2a menyebut tes
  yang gagal atau error padahal tidak diwajibkan.
- **`ReviseDraft`** (`codetask/drafter.py`): field yang diberikan menggantikan field yang sama di argumen submit
  terakhir. Argumen itu disimpan di record tool yang di-commit (`args`), jadi run yang di-resume merevisi draf yang
  sama. Hasilnya dicek dan dihitung seperti `SubmitDraft`. Tanpa submit sebelumnya, revisi ditolak tanpa menjalankan
  apa pun. Field tak dikenal ditolak dengan namanya. Harus sendirian di balasannya.
- **Config:** output drafter 16.384 (PR #151), `attempt_usd` 0,70, dan `max_input_tokens` 64.000. Cap run tetap
  `min(budget.max_usd, --max-usd)`.

Bukti: tes baru di `tests/test_drafter.py` (revisi, penyebutan tes, revisi tanpa submit, field terlarang, batas submit,
revisi bersama tool lain, crash setelah revisi, dan tool yang ditawarkan) serta `tests/test_draft.py` (sandbox).
Mutan: `verification/mutants-w2b-revise-20261022-59eee91.log`, **9/9 tertangkap**. Satu mutan tidak dimasukkan karena
ekuivalen dalam perilaku: menggabungkan field tak dikenal ke draf lama tetap ditolak `draft_from_args` dengan nama
yang sama.

## 7. Profil budget wajib dipilih (2026-10-23, keputusan Atha)

`w2b1d3` menghasilkan draf tanpa `budget_profile`, sehingga agen akan mendapat `default`. Sekarang `budget_profile`
**wajib** di `SubmitDraft`: draf tanpa profil, atau dengan nama yang tidak dikenal, ditolak dengan daftar profil yang
ada. Prompt task mencantumkan setiap profil dengan batasnya (USD atau token per attempt, input dan output per
panggilan; dibekukan di policy run sebagai `profile_info`), ditambah satu kalimat cara memilih. `DRAFT_REVIEW.md`
menampilkan profil yang dipilih. Mutan `verification/mutants-w2b-profile-20261023-17cd3d4.log`: 4/4. `verify.sh` lulus
di `17cd3d4`.
