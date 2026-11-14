# RC-09: red node in a file the agent did not name

## Expectation

`decision: unconfirmed`.

## The tree, by construction

- The change (`Lim, Ana`) turns two old tests red, in two files. Both are genuine contradictions, green on the input, red in their own test bodies.
- The agent names only `tests/test_display_old.py`. `tests/test_greeting_old.py::test_greeting_text` is red and not in a named file.

## Spec sentences that decide it

- v3 C5: "Agen tetap menyebut 1-5 berkas. Himpunan merah = gabungan `failed_nodes` semua validasi di verdict attempt itu."
- v3 C5: "Setiap node merah harus berada di salah satu berkas yang disebut; berkas yang disebut tanpa node merah → tak terkonfirmasi."
- v3 §2 tes 10: "node merah di luar berkas yang disebut [...] → tak terkonfirmasi"
- v1 §5 tes 2: "Satu tes merah lain yang tidak disebut → tidak terkonfirmasi; umpan balik menyebut butir 3." (and the mutant "`==` jadi `⊆`")

## Why nothing else decides it

Had the agent named both files this would be RC-02's shape (confirmed). Only the incomplete file list rejects it.
