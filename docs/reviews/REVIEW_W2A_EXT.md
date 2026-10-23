# Review W2a-ext: `changed_tests`

Spek: `docs/reviews/SPEC_W2A_EXT_CHANGED_TESTS.md` (K1–K7 disetujui, plus tiga tambahan di bagian 10). Ditulis Claude, 2026-10-23.

## Yang dijaga harness

| Jaminan | Di mana | Tes (semua gagal di kode lama) |
|---|---|---|
| Hanya `test_*.py` yang sudah ada di intake, maks 5, ≤ 50 KB; conftest.py, pytest.ini, pyproject.toml, setup.cfg ditolak (K5, tambahan 3) | `changed.shape_problems`, `changed.static_problems` | `test_changed_tests_of_the_wrong_shape_are_refused`, `test_static_problems_of_changed_tests` |
| File yang diubah protected dan tidak writable, isinya berbeda, dan dijalankan utuh oleh validasi pytest (tanpa `-k`) | `changed.static_problems` | sama |
| Fungsi tes yang tidak wajib harus identik secara AST, kecuali tercantum di `modified` beserta alasan (tambahan 1). Helper dan fixture tingkat modul hanya memicu peringatan K3 | `changed.function_problems` | `test_static_problems_of_changed_tests`, `test_what_a_changed_test_may_change_without_a_static_problem` |
| Tidak ada node lama yang hilang (K1): `pytest --collect-only` di sandbox, versi intake dibanding versi baru, termasuk varian parametrize, kecuali tercantum di `removed`; entri `removed` harus benar-benar hilang | `validation.collect_nodes`, `draft.collection_problems`, `changed.lost_problems` | `test_an_old_test_that_is_lost_without_a_reason_is_refused_and_named`, `..._removed_with_a_reason_is_accepted...` |
| Node wajib di file yang diubah merah karena assertion; selain itu hijau (K4) | `draft.red_paths` → `baseline_problems` | `test_a_draft_that_changes_an_old_test_...`, `test_a_test_of_a_changed_file_that_fails_without_being_required_is_named` |
| Tidak ada skip/xfail/xpass baru di file yang diubah, di baseline, referensi, maupun acceptance agen (tambahan 2). Aturannya `no_skip: {paths, allowed}` di kontrak, dipasang `build_contract` dari penanda versi intake (deterministik saat approve); draf tidak boleh mengisinya | `changed.add_no_skip`, `changed.skip_allowed`, `validation.skip_violations` / `judge_result`, `contract._no_skip` | `test_a_changed_test_file_that_skips_or_xfails_its_old_tests_is_refused` (`pytestmark` skip, `pytestmark` xfail, fixture autouse), `test_a_skip_next_to_a_red_required_test...`, `test_acceptance_refuses_a_skip_or_xfail...`, `test_what_counts_as_already_skipped...` |
| Approve: intake tidak berubah, kontrak dibangun ulang sama persis, `changed` {before, after, removed, modified} sama dengan laporan; dicatat di record | `draft.approve` | `test_an_intake_changed_between_the_check_and_approval...`, `test_a_report_whose_changed_tests_differ...` |
| Paket review: input = commit dasar + tes baru + isi baru tes yang diubah; `before` harus versi di commit dasar; ditandai `M` "(changed test, approved with the task)"; PR.md punya bagian "Existing tests changed by the task" (removed/modified); agen tetap tidak bisa mengubahnya | `codetask/review.py` | `test_a_tasks_changed_tests_are_in_the_patch...`, `test_a_changed_test_that_is_not_the_approved_change...`, `test_an_agent_change_to_a_changed_test_is_refused` |
| Drafter: `changed_tests` lewat SubmitDraft/ReviseDraft; DRAFT_REVIEW.md menampilkan diff, removed, modified, dan peringatan K3 | `codetask/drafter.py` | `test_changed_tests_go_through_submit_and_revise...`, `test_the_review_page_shows_a_changed_tests_diff...` |
| Router: layar approve dan status menyebut jumlah file dan jumlah peringatan (K6), dihitung dari intake | `router/job.changed_lines` | `test_the_approve_screen_and_status_say_how_many_old_tests...` |

## Batas yang disengaja

- Skip lama yang hanya terjadi saat run (misalnya `pytest.skip()` di dalam tubuh fungsi, `importorskip`, atau skip dari conftest) tidak dihitung sebagai "sudah skipped". File seperti itu tidak bisa diubah tanpa ditolak; ini dites di `test_a_test_skipped_only_at_run_time_in_the_intake...`.
- AST hanya melihat fungsi `test*` di tingkat modul dan metode `test*` dari kelas `Test*` di tingkat modul. Kelas bersarang dan perubahan pada isi kelas di luar metode tes hanya memicu peringatan K3.
- Tes yang melemah tetap tidak bisa dibuktikan. Peringatan K3 (assert berkurang; skip, xfail, atau `assert True` baru; kode tingkat modul berubah; tes yang dihapus) hanya menunjuk tempat yang perlu dibaca.
- `new_tests` tetap wajib berisi minimal satu file (tidak diubah).

## Bukti

- Tes terdampak di VM: 279 lulus (sandbox nyata).
- 25 tes baru dijalankan pada kode `main` lama: semuanya gagal, tidak ada yang lulus atau di-skip (`verification/w2a_ext_mutants.log`, bagian "old code").
- Mutan: 26/26 mati (log yang sama).
- `verify.sh` penuh: `verification/w2a_ext_verify.log`.
