# RC-11: a required new test is red as well

## Expectation

`decision: unconfirmed`.

## The tree, by construction

- The draft requires two things (both in `must_pass`): lower-casing and dropping duplicates. The agent built only lower-casing.
- Red with the change: the old `tests/test_clean_old.py::test_case_preserved` (a genuine contradiction with lower-casing) AND the new `tests/test_clean_new.py::test_duplicates_dropped` (feature missing).
- The agent names both files, so every red node is in a named file and every named file has a red node: v3 C5's file rules are satisfied and cannot be the reason.

## Spec sentences that decide it

- v1 R2.5: "Setiap `must_pass` milik tes baru draf hijau (fiturnya ada)." `test_duplicates_dropped` is a `must_pass` node and is red.
- v1 R2.4: "Setiap node merah ada di berkas yang ada di intake, digest-nya tidak berubah, cocok glob protected (kontrak atau `.argus/protected`), dan bukan `new_tests`/`changed_tests` draf." One red node is in the draft's new test file.
- v3 C1: "Syarat baru, untuk setiap node merah: `outcome == "failed"`, `path` tidak `None`, dan berkas `path` (a) ada di intake dengan digest yang sama, (b) cocok glob protected (kontrak atau `repo_protected` yang dibekukan di setup), (c) bukan berkas `new_tests`/`changed_tests` draf." (c) fails for `tests/test_clean_new.py`.
- v1 §5 tes 3: "Node yang disebut adalah tes baru draf [...] → tidak terkonfirmasi." and tes 5: "`must_pass` merah [...] → tidak terkonfirmasi"

## Why nothing else decides it

The two reasons (must_pass red; red node is a draft test) are two views of the same fact and cannot be split. If the agent had named only the old file, v3 C5 ("node merah di luar berkas yang disebut") would reject it as well: still unconfirmed.
