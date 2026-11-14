# RC-17: red by ImportError

## Expectation

`decision: unconfirmed`.

## The tree, by construction

- The agent renamed `total` to `grand_total` (the new test asks for `grand_total`) and kept no alias. `tests/test_total_old.py` has `from billing.sums import total` at module level, so pytest cannot collect the file: an `ImportError` during collection, an error, not a failed test.
- On the input the old file is collected and green.

## Spec sentences that decide it

- v3 C1: "Syarat baru, untuk setiap node merah: `outcome == "failed"`, `path` tidak `None`, dan berkas `path` (a) ada di intake dengan digest yang sama, (b) cocok glob protected (kontrak atau `repo_protected` yang dibekukan di setup), (c) bukan berkas `new_tests`/`changed_tests` draf." A collection error is not `outcome == "failed"`.
- v1 R2.8: "`AssertionError`, bukan error impor atau koleksi."
- v2 B2: "(gagal di frame tes, bukan error muat atau koleksi)"
- v1 §5 tes 5: "[...] merah karena `ImportError` → tidak terkonfirmasi"

## Why nothing else decides it

Which reason text appears is not decided by the spec: a collection error has no test node, so it may equally surface as v3 C5's count mismatch (`failures + errors != len(failed_nodes)`), as an empty red set ("Himpunan kosong → tak terkonfirmasi") or as an unreadable `red_check`. Every one of these paths ends unconfirmed, which is all this case asserts.
