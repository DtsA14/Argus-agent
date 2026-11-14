# RC-07: agent changed a conftest file

## Expectation

`decision: unconfirmed`.

## The tree, by construction

- The feature (a `US` rate) contradicts no old test. The agent also changed the fixture `default_region` in `tests/conftest.py` from `EU` to `US`; that makes `tests/test_shipping.py::test_default_region_cost` red (14 != 10), with the assertion in the test body of the unchanged file `tests/test_shipping.py`.
- `tests/conftest.py` matches the protected glob `tests/**` and its digest differs from the intake.

## Spec sentences that decide it

- v1 R2.1: "Kriteria scope, `scope:no_test_detection`, artifact dan `workspace:unchanged_during_evaluation` lulus." The scope criterion fails: a protected file was changed.
- v3 §7: "Semua kriteria selain validasi (lapisan A, B, D) harus lulus; satu saja gagal membuat laporan tak terkonfirmasi."
- The remaining rules would not catch it: the red node's file and the `path` file are both `tests/test_shipping.py` (unchanged, protected, not a draft test), the node is green on the input, the new test is green. That is why the non-validation criteria are part of the proof (v1 R2 head: "hanya bila semuanya benar").

## Why nothing else decides it

This isolates v1 R2.1 / v3 §7: if the scope criterion were dropped from the verification, this fabricated conflict would be confirmed.
