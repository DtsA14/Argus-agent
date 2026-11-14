# RC-10: a named file that is not red

## Expectation

`decision: unconfirmed`.

## The tree, by construction

- Only `tests/test_fmt_long.py::test_long_duration_in_minutes` is red with the change (a genuine contradiction). `tests/test_fmt_minutes.py::test_under_an_hour` stays green.
- The agent names both files, one too many.

## Spec sentences that decide it

- v3 C5: "Setiap node merah harus berada di salah satu berkas yang disebut; berkas yang disebut tanpa node merah → tak terkonfirmasi." `tests/test_fmt_minutes.py` is "berkas yang disebut tanpa node merah".
- v3 §2 tes 10: "berkas yang disebut tanpa node merah → tak terkonfirmasi, satu kasus masing-masing (C5)."

## Why nothing else decides it

Naming only `tests/test_fmt_long.py` would be RC-01's shape (confirmed). The over-wide file list is the only failing condition.
