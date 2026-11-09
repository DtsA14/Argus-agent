#!/usr/bin/env bash
# verify.sh on one commit, in its own git worktree with its own venv, so this checkout and its .venv-verify (the python
# of the pilot commands) stay usable while it runs (Atha 2026-11-09). The evidence log is copied into this checkout's
# verification/ and the worktree is removed, whatever the result.
# The image pins verify.sh and the sandbox tests read (.sandbox_image*, git-ignored, written by pin_sandbox_image.sh and
# the build scripts) are copied in first: without them the sandbox tests skip and the result is FAIL.
# Exit status: 0 only when the log's last RESULT line is PASS (as verify.sh's own).
# Usage: bash scripts/verify_at.sh <commit> [directory for the worktree, default $TMPDIR or /tmp]
set -euo pipefail
root="$(git rev-parse --show-toplevel)"
commit="$(git -C "$root" rev-parse --verify "${1:?usage: verify_at.sh <commit> [dir]}^{commit}")"
base="${2:-${TMPDIR:-/tmp}}"
wt="$(mktemp -d "$base/argus-verify-${commit:0:12}-XXXXXX")"
rmdir "$wt"
cleanup() {
  git -C "$root" worktree remove --force "$wt" >/dev/null 2>&1 || rm -rf "$wt"
  git -C "$root" worktree prune
}
trap cleanup EXIT
git -C "$root" worktree add -q --detach "$wt" "$commit"
shopt -s nullglob
pins=("$root"/.sandbox_image*)
if [ ${#pins[@]} -gt 0 ]; then
  cp -p "${pins[@]}" "$wt"/
fi
echo "verify_at: $commit in $wt (${#pins[@]} image pin file(s) copied)"
set +e
(cd "$wt" && bash scripts/verify.sh)
set -e
logs=("$wt"/verification/verify-*.log)
if [ ${#logs[@]} -eq 0 ]; then
  echo "verify_at: verify.sh wrote no log" >&2
  exit 1
fi
log="$(ls -t "${logs[@]}" | head -n 1)"
mkdir -p "$root/verification"
cp -p "$log" "$root/verification/"
echo "verify_at: evidence copied to verification/$(basename "$log")"
grep '^RESULT: ' "$log" | tail -n 1 | grep -q '^RESULT: PASS'
