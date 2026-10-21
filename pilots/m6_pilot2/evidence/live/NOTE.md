# Note on `provenance.json` (2026-10-21)

The first `provenance.json` of this package had four checks with `ok: true` and a leftover failure text in `detail`
(`patch_made`: "the patch is empty" although the patch has 6,742 bytes, and `changes_match_verdict`,
`final_state_identical`, `workspace_stable`). Cause and fix: `Checks.add` stored the detail whatever the result
(PR #94, `codetask/review.py`). The `ok` flags and `valid` were right, and `PR.md`, `tests.md` and `claims.md` were not
affected.

This file was regenerated with the fixed code (`build_review.py --run runs/pilot2`, the old package kept on the VM as
`review.before-detail-fix`). Compared with the first one: `changes.patch` is **byte-identical** (sha256
`d96f57299946b8ec…`), `PR.md`, `tests.md` and `claims.md` are identical, and only the `detail` of those four checks
differs (now empty). The code patch of this PR was not touched.
