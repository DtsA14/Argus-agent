#!/usr/bin/env bash
# Print which commit is being verified and whether the working tree is clean, for the verify.sh log.
# Untracked files count as dirty: they can change what the tests import. Paths given as arguments are
# left out (verify.sh passes the log file it is writing).
# Usage: bash scripts/provenance.sh [path-to-exclude ...]
set -uo pipefail
cd "$(dirname "$0")/.."

if ! head="$(git rev-parse HEAD 2>/dev/null)"; then
  echo "commit: <not a git checkout>"
  exit 0
fi
echo "commit: $head"

excludes=()
for p in "$@"; do excludes+=(":(exclude)$p"); done
status="$(git status --porcelain --untracked-files=all -- . ${excludes[@]+"${excludes[@]}"})"
if [ -z "$status" ]; then
  echo "working tree: clean"
else
  echo "working tree: DIRTY ($(printf '%s\n' "$status" | wc -l | tr -d ' ') paths)"
  echo "== git status --porcelain"
  printf '%s\n' "$status"
fi
