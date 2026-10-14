#!/usr/bin/env bash
# Reproducible milestone check: fresh virtualenv, pinned dependencies, full test suite,
# crash-resume repeated CRASH_REPEATS times per crash point (before the node and right after
# its result is committed), plus CRASH_STRESS parallel-worker crashes. The full output is saved under
# verification/ as evidence, with the environment and a hash of every source file.
# Usage: bash scripts/verify.sh            (CRASH_REPEATS=5 by default)
set -euo pipefail
cd "$(dirname "$0")/.."

VENV="${VENV:-.venv-verify}"
export CRASH_REPEATS="${CRASH_REPEATS:-5}"
export CRASH_STRESS="${CRASH_STRESS:-50}"
mkdir -p verification
LOG="verification/verify-$(date -u +%Y%m%dT%H%M%SZ)-$(uname -m).log"

{
  echo "== verify.sh $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "host: $(uname -srm)"
  rm -rf "$VENV"
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q --upgrade pip
  "$VENV/bin/pip" install -q -r requirements.txt
  echo "python: $("$VENV/bin/python" --version 2>&1)"
  echo "CRASH_REPEATS=$CRASH_REPEATS CRASH_STRESS=$CRASH_STRESS"
  echo "== pip freeze"
  "$VENV/bin/pip" freeze
  echo "== source sha256"
  find . -path ./"$VENV" -prune -o -path ./verification -prune -o \
       \( -name '*.py' -o -name '*.yaml' -o -name '*.txt' -o -name '*.sh' -o -name '*.csv' \) -type f -print \
    | LC_ALL=C sort | xargs sha256sum
  echo "== pytest"
  set +e
  "$VENV/bin/python" -m pytest -q -p no:cacheprovider 2>&1
  rc=$?
  set -e
  if [ "$rc" -eq 0 ]; then echo "RESULT: PASS"; else echo "RESULT: FAIL (pytest exit $rc)"; fi
} 2>&1 | tee "$LOG"

echo "evidence saved to $LOG"
grep -q '^RESULT: PASS' "$LOG"
