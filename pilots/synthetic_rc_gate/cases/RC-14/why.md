# RC-14: empty diff

## Expectation

`decision: unconfirmed`.

## The tree, by construction

- `workspace/` holds only `SUMMARY.json` (written by the tool). No writable file differs from the input.
- So the tree behaves like the input: the old test is green, the draft's new test `test_perimeter` is red (the feature does not exist).
- The agent names `tests/test_area_old.py`, which has no red node.

## Spec sentences that decide it

- v1 R2.6: "Diff terhadap intake tidak kosong di berkas writable." The diff is empty in writable files (`geo/**`); `SUMMARY.json` is the artifact, not a writable production file.
- v1 R2.5: "Setiap `must_pass` milik tes baru draf hijau (fiturnya ada)." The `must_pass` node is red.
- v3 C5: "Setiap node merah harus berada di salah satu berkas yang disebut; berkas yang disebut tanpa node merah → tak terkonfirmasi." The red node is outside the named file and the named file has no red node.
- v1 §5 tes 5: "`must_pass` merah, diff kosong [...] → tidak terkonfirmasi (satu kasus masing-masing)"
- v1 §4: "Jalan keluar malas (tes lama benar) | Butir 5-6 memaksa fitur ada"

## Why nothing else decides it

An empty diff cannot be combined with a green new test and a red old test (the input is green by the approve rule quoted in v2 §2), so the three reasons necessarily come together. The red set is not empty, so this is not v3 C3.1 (`DONE`).
