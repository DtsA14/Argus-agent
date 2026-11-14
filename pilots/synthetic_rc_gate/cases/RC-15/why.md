# RC-15: red at baseline

## Expectation

`decision: unconfirmed`.

## The tree, by construction

- `tests/test_convert_old.py::test_body_temperature` expects 99 but integer arithmetic gives 98: it is red on the INPUT, before the agent did anything, and stays red (same assertion, test body) with the change.
- The agent's change only adds `f_to_c` (new test green) and does not touch `c_to_f`. The agent blames the old file.

## Spec sentences that decide it

- v1 R2.7: "**Baseline:** node yang sama dijalankan harness pada salinan input yang tak disentuh (read-only): semua lulus." Not all pass: the node is red on the input.
- v1 §5 tes 4: "Tes itu sudah merah di baseline → tidak terkonfirmasi."
- v2 §2 baris R2.7: "Di acceptance cukup satu jalan ulang pada input, untuk flaky" and v3 C7: "**Baseline satu kali** (v2) tetap." (one run on the input is still made, and it is red)

## Why nothing else decides it

Every other condition holds (file named, unchanged, protected, failure in the test body, must_pass green, diff non-empty). The input violates the approve rule quoted in v2 §2 ("hanya tes baru wajib yang merah"), which a real job would have caught earlier; the verification must still refuse on its own evidence.
