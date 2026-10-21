# Note on `provenance.json` (2026-10-21)

Pilot 1's `provenance.json` has the same artefact found in pilot 2: four checks (`patch_made`, `changes_match_verdict`,
`final_state_identical`, `workspace_stable`) show `ok: true` with a leftover failure text in `detail` (for example
"the patch is empty" although the patch has 4,255 bytes). The `ok` flags and `valid` are right; `PR.md` prints a detail
only for failed checks. Cause and fix: `Checks.add` (PR #94, `codetask/review.py`). The file is left as it was produced
at the time; do not read the `detail` of a check with `ok: true`.
