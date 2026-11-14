# RC-18: report with nothing red

## Expectation

`decision: unconfirmed` (never `confirmed`); the run itself ends `DONE` and `verdict.conflict.unconfirmed` is `["nothing is red"]`.

## The tree, by construction

- The agent's change is correct and complete: the old test and the new test are both green. It nevertheless ends with `ReportConflict` naming the old file.

## Spec sentences that decide it

- v3 C3.1: "`outcome == "pass"` → `DONE`, seperti sekarang. Tidak ada tes merah, jadi laporan tidak diverifikasi; `verdict.conflict` mencatat `{files, unconfirmed: ["nothing is red"]}`."
- v3 §2 tes 7: "Laporan, tetapi semua kriteria lulus → `DONE`, `verdict.conflict.unconfirmed` terisi (C3)."

## Why nothing else decides it

The step order of v3 C3 puts `outcome == "pass"` before the verification, so no `red_check` runs at all. If a runner reports only a three-valued decision, the value is `unconfirmed`; the precise spec outcome is `DONE` with the recorded note. (Requires the artifact criterion to pass with the tool's `SUMMARY.json`, `claims: []`: v3 C2 "`SUMMARY.json` tetap ditulis dengan `claims: []` supaya `evaluate` berjalan".)
