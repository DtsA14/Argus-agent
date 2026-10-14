#!/usr/bin/env bash
# Reproducible milestone check: fresh virtualenv, pinned dependencies, full test suite,
# crash-resume repeated CRASH_REPEATS times per crash point (before the node and right after
# its result is committed), plus CRASH_STRESS parallel-worker crashes. The full output is saved under
# verification/ as evidence, with the commit, whether the working tree was clean, the environment and a
# hash of every source file.
#
# Sandbox tests run in a real Docker container and need a pinned image: ARGUS_SANDBOX_IMAGE, or the
# file .sandbox_image written by scripts/pin_sandbox_image.sh. If they are skipped, the result is FAIL:
# a skipped sandbox test does not count as passing. ARGUS_SANDBOX_OPTIONAL=1 allows it explicitly, and
# the log then says "sandbox NOT verified".
# Usage: bash scripts/verify.sh            (CRASH_REPEATS=5 by default)
set -euo pipefail
cd "$(dirname "$0")/.."

VENV="${VENV:-.venv-verify}"
export CRASH_REPEATS="${CRASH_REPEATS:-5}"
export CRASH_STRESS="${CRASH_STRESS:-50}"
if [ -z "${ARGUS_SANDBOX_IMAGE:-}" ] && [ -f .sandbox_image ]; then
  export ARGUS_SANDBOX_IMAGE="$(tr -d '[:space:]' < .sandbox_image)"
fi
mkdir -p verification
LOG="verification/verify-$(date -u +%Y%m%dT%H%M%SZ)-$(uname -m).log"

{
  echo "== verify.sh $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "host: $(uname -srm)"
  bash scripts/provenance.sh "$LOG"
  rm -rf "$VENV"
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q --upgrade pip
  "$VENV/bin/pip" install -q -r requirements.txt
  echo "python: $("$VENV/bin/python" --version 2>&1)"
  echo "CRASH_REPEATS=$CRASH_REPEATS CRASH_STRESS=$CRASH_STRESS"
  echo "sandbox image: ${ARGUS_SANDBOX_IMAGE:-<none>}"
  echo "docker: $(docker version --format 'client {{.Client.Version}} / server {{.Server.Version}} ({{.Server.Os}}/{{.Server.Arch}})' 2>/dev/null || echo 'not available')"
  echo "== pip freeze"
  "$VENV/bin/pip" freeze
  echo "== source sha256"
  find . -path ./"$VENV" -prune -o -path ./verification -prune -o \
       \( -name '*.py' -o -name '*.yaml' -o -name '*.txt' -o -name '*.sh' -o -name '*.csv' \) -type f -print \
    | LC_ALL=C sort | xargs sha256sum
  echo "== pytest"
  set +e
  "$VENV/bin/python" -m pytest -q -rs -p no:cacheprovider 2>&1 | tee /dev/stderr > .verify-pytest.out
  rc=${PIPESTATUS[0]}
  set -e
  skipped_sandbox=$(grep -c "SANDBOX NOT AVAILABLE" .verify-pytest.out || true)
  rm -f .verify-pytest.out
  echo "== sandbox tests skipped: $skipped_sandbox"
  if [ "$rc" -ne 0 ]; then
    echo "RESULT: FAIL (pytest exit $rc)"
  elif [ "$skipped_sandbox" -gt 0 ] && [ "${ARGUS_SANDBOX_OPTIONAL:-0}" != "1" ]; then
    echo "RESULT: FAIL (sandbox tests skipped: $skipped_sandbox; set ARGUS_SANDBOX_IMAGE or run scripts/pin_sandbox_image.sh)"
  elif [ "$skipped_sandbox" -gt 0 ]; then
    echo "RESULT: PASS (sandbox NOT verified: $skipped_sandbox skipped, ARGUS_SANDBOX_OPTIONAL=1)"
  else
    echo "RESULT: PASS"
  fi
} 2>&1 | tee "$LOG"

echo "evidence saved to $LOG"
grep -q '^RESULT: PASS' "$LOG"
