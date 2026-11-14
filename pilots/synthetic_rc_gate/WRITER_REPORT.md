# Report of the case writer (subagent Fable, 2026-11-14), verbatim in substance

The writer read only the five specs, `ACCEPTANCE_GENERAL.md` section 5 and `acceptance/contract.py` lines 1 to 25; no git, no Argus code. **It did not run real pytest** (not installed there, no network): it checked which synthetic tests are red or green with a small stand-in runner and which lines the GATE patterns match with its own scanner (kept out of the repository, in its scratch folder); both agreed with all 35 cases, but **real pytest node ids and collection behaviour are untested**. It makes no claim that the cases match the implementation.

**Counts:** RC 18 (5 confirmed RC-01..05, 9 required negatives RC-06..14, 4 extras: RC-15 red at baseline, RC-16 file not protected, RC-17 ImportError, RC-18 nothing red -> DONE); GATE 17 (7 hits GATE-01..07, 7 clean look-alikes GATE-08..14, 3 extras: GATE-15 an old line edited -> hit, GATE-16 the whole pattern in a comment -> hit, GATE-17 a pattern split over two lines -> clean).

**Departures from the format:** `case.json` has two extra informational keys (`draft_new_tests`, `facts`); `finished` cases carry no `SUMMARY.json` (the claims schema was outside its reading) and `conflict_reported` cases carry `{"claims": []}`; each production package has an empty `__init__.py`; there is no `blocked` case (sandbox absence cannot be expressed as tree data).

## Spec gaps and ambiguities it found (for Atha to decide; none of them is a failure of the code)

1. **Flaky (v1 R2.9 "keempat hasil harus sama").** The spec does not say whether the workspace is writable during `red_check` (v1 section 3 "sandbox read-only" against v3 C2 "me-mount workspace bisa-tulis"). RC-12 is therefore order-dependent instead: red in the full run, green alone (v3 C5 "pada node-node itu saja").
2. **Draft tests (v3 C1(c)).** The case format has no field for `new_tests`/`changed_tests`; the writer assumed they are the `must_pass` files.
3. **`SUMMARY.json` and scope/diff (v1 R2.6).** Not stated whether the artifact counts as a writable-file diff or needs a writable glob.
4. **Collection errors (v3 C5).** How an ImportError appears in `failed_nodes` is unspecified, so RC-17's reason text is undecided; its decision is not.
5. **`MAX_NODES`.** The value 50 appears only in v2 B1; RC-13 depends on it.
6. **Comments and strings (GATE C1 "regex, per baris").** No exemption is stated. GATE-16 takes the literal reading (hit), which may not match the intent.
7. **Case sensitivity** of the patterns (`PyTest`) is unspecified; no case written.
8. **JS patterns in `.py` files** (e.g. `NODE_ENV` with `"test"`): the table is not split by extension; no case written.
9. **"komponen `tests`, `test`"**: exact component or substring (`testing/`) is unspecified. Test-named files inside the writable tree are exempt (GATE-14), which lets production import a detection helper from `pkg/test/x.py`.
10. **Deleted or renamed files** under C2 are not addressed.
11. **Files matching neither writable nor protected**: the scope outcome is unknown, so RC-07 uses a protected conftest.
12. **Hit plus unconfirmed report (TERMINAL):** whether the `conflict` state and the B3 line are still recorded is not stated.

## Contradictions it found between the specs

- GATE C3 says "agen mendapat percobaan lagi seperti kriteria lain; tidak ada jalur khusus"; TERMINAL Usul 1 says "Tidak ada attempt berikutnya". TERMINAL does not say it replaces C3.
- v1 section 5 test 6 ("Baseline hijau lalu merah -> tidak terkonfirmasi") and v1 section 4 ("Tes lama flaky | Butir 9") cannot hold with v3 C7's single baseline run, which accepts "flaky sesekali terkonfirmasi salah".
- v3 C3.1 says the report "tidak diverifikasi" yet records `unconfirmed: ["nothing is red"]`. RC-18 expects `unconfirmed` with the run `DONE`.
- v1 R1 (at most 3 files) against v2 B1 (1 to 5 files): resolved only by v2's status line.
- v3 C1 states conditions (a)(b)(c) for `path` only; v3 section 7 extends them to the node's file.
