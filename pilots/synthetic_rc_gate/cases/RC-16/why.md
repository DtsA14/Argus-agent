# RC-16: named file is not protected

## Expectation

`decision: unconfirmed`.

## The tree, by construction

- `tests/test_header_legacy.py::test_header_is_upper_title` genuinely contradicts the new underlined header, is green on the input, red in its own body with the change, and the file is unchanged.
- But the contract's `scope.protected` lists only `tests/test_width.py` and `tests/test_header_new.py`, and the repository has no `.argus/protected`. The red file is neither writable nor protected.

## Spec sentences that decide it

- v1 R2.4: "Setiap node merah ada di berkas yang ada di intake, digest-nya tidak berubah, cocok glob protected (kontrak atau `.argus/protected`), dan bukan `new_tests`/`changed_tests` draf." It does not match a protected glob.
- v3 C1: "Syarat baru, untuk setiap node merah: `outcome == "failed"`, `path` tidak `None`, dan berkas `path` (a) ada di intake dengan digest yang sama, (b) cocok glob protected (kontrak atau `repo_protected` yang dibekukan di setup), (c) bukan berkas `new_tests`/`changed_tests` draf." (b) fails for the `path` file (the same file).
- v3 §7: "Syarat C1 (a)(b)(c) dikenakan pada **dua hal**: berkas node merah dan `path` dari record `red_check` (keduanya harus berkas input yang tak disentuh, terlindungi, dan bukan tes draf)."
- v1 §5 tes 3: "[...] atau berkasnya tidak protected → tidak terkonfirmasi."

## Why nothing else decides it

The agent did not touch the file, so the scope criterion passes, and all other conditions hold. This case intentionally departs from the set's rule that `scope.protected` covers all old test files: that departure is the condition under test.
