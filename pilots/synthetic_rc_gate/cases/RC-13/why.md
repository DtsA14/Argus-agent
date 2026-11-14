# RC-13: too many red nodes to enumerate

## Expectation

`decision: unconfirmed` (reason text "too many red tests to enumerate").

## The tree, by construction

- The old test is parametrized over `range(60)`; every one of the 60 nodes asserts the old code format and is red with the change (all green on the input). The new test is green.
- The validation therefore reports 60 failures, while its `failed_nodes` list is cut at `MAX_NODES`, which the spec gives as 50.

## Spec sentences that decide it

- v3 C5: "Validasi dengan `failures + errors != len(failed_nodes)` (daftar dipotong di `MAX_NODES`, `validation.py:350`, `394`) → tak terkonfirmasi: "too many red tests to enumerate". Ini menggantikan "lebih dari 50 node" di v2, yang tidak bisa dibedakan dari tepat 50." 60 != 50.
- v2 B1: "Lebih dari 50 node merah (`MAX_NODES`, `validation.py:54`) → tak terkonfirmasi." (the number 50 comes from here)
- v3 §2 tes 10: "Daftar `failed_nodes` terpotong [...] → tak terkonfirmasi"

## Why nothing else decides it

Otherwise this is RC-04's shape (a parametrized genuine conflict in one named file). It depends on `MAX_NODES` being 50 as the spec text says; I have not seen the constant.
