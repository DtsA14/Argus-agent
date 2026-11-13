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
# The commit already holds many verification logs: the new one is the one that was not there before (never "the
# newest", and no `ls | head`, whose early close kills the script under pipefail).
declare -A before=()
for f in "$wt"/verification/verify-*.log; do before["$f"]=1; done
# A signal (the user stops the run) kills verify.sh's whole process tree (pytest, its workers, their children) before the
# worktree goes: workers left behind kept writing into a removed tree and printed a burst of failures that were not real.
descendants() {
  local c
  for c in $(pgrep -P "$1" 2>/dev/null || true); do echo "$c"; descendants "$c"; done
}
vpid=""
on_signal() {
  if [ -n "$vpid" ]; then
    # The descendants are listed FIRST: once the group is killed their parents are gone and they are reparented to init, out of
    # reach of a walk down from verify.sh. Then the whole process group at once (verify.sh runs in its own, see below): a step the
    # script starts after one of its children died is in the group too, which a kill of the children one by one (parent last) lets
    # through. Then the listed processes, for those that left the group.
    local all
    all="$vpid $(descendants "$vpid")"
    kill -TERM -- "-$vpid" 2>/dev/null || true
    # shellcheck disable=SC2086
    kill $all 2>/dev/null || true
    wait "$vpid" 2>/dev/null || true
  fi
  exit 143
}
trap on_signal INT TERM
set +e
(cd "$wt" && exec setsid -w bash scripts/verify.sh) &
vpid=$!
wait "$vpid"
set -e
vpid=""
logs=()
for f in "$wt"/verification/verify-*.log; do
  [ -n "${before[$f]:-}" ] || logs+=("$f")
done
if [ ${#logs[@]} -ne 1 ]; then
  echo "verify_at: verify.sh wrote ${#logs[@]} new logs, not one" >&2
  exit 1
fi
log="${logs[0]}"
mkdir -p "$root/verification"
cp -p "$log" "$root/verification/"
echo "verify_at: evidence copied to verification/$(basename "$log")"
[[ "$(grep '^RESULT: ' "$log" | tail -n 1)" == "RESULT: PASS"* ]]
