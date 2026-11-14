# RC-08: exception raised in production code

## Expectation

`decision: unconfirmed`.

## The tree, by construction

- New behaviour (required by the new test): `parse_qty("-1")` raises `ValueError`. The old test `test_negative_passes_through` calls `parse_qty("-1")`, so it goes red with a `ValueError` raised INSIDE `orders/qty.py`: the innermost repository frame (`path`) is the writable production file.
- pytest reports it as `failed` (an exception in the call phase), the node is green on the input, the new test is green, the file is named, unchanged and protected. Semantically this even is a real contradiction; the spec refuses it on purpose.

## Spec sentences that decide it

- v3 C1: "Yang tetap ditolak, dengan sengaja: tes lama yang merah karena exception dilempar **di kode produksi** (`path` di berkas writable). Dari bukti harness itu tidak bisa dibedakan dari bug agen. Laporan seperti itu tak terkonfirmasi dan terlihat lewat baris B3"
- v3 C1: "Syarat baru, untuk setiap node merah: `outcome == "failed"`, `path` tidak `None`, dan berkas `path` (a) ada di intake dengan digest yang sama, (b) cocok glob protected (kontrak atau `repo_protected` yang dibekukan di setup), (c) bukan berkas `new_tests`/`changed_tests` draf." `path` = `orders/qty.py`: it fails (a) (digest changed) and (b) (it matches writable, not protected).
- v3 §2 tes 2: "Tes lama merah karena exception dilempar di berkas writable → tak terkonfirmasi, baris B3 menyebut butirnya (C1)."

## Why nothing else decides it

All conditions of v1 R2.1-7 and v3 C5 hold; only the `path` rule of v3 C1 fails. Under v2 B2 ("`path` record = berkas tes itu sendiri") it would also fail; under v1 R2.8 ("`AssertionError`") too. v3 keeps the refusal.
