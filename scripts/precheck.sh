#!/usr/bin/env bash
# The pre-check (SPEC_VERIFY_HARDENING): about a minute, before the one `verify_at`. It runs the tests a change touches, the tests
# named after the source modules it touches, and the fixed set that guards the verification itself (the sandbox check that no
# container is left over, the group list, the verify scripts), with verify.sh's own scheduling (-n 4 --dist loadgroup), so a
# sandbox test that is not in the serial group fails here and not after twenty minutes. It is not evidence: it writes nothing to
# verification/, it does not replace verify_at, and it is never run beside one (CPU: exit 137).
# Usage: bash scripts/precheck.sh [base, default origin/main]     PRECHECK_PRINT=1 only prints what it would run.
set -euo pipefail
cd "$(dirname "$0")/.."
BASE="${1:-origin/main}"
if ! git rev-parse --verify -q "$BASE^{commit}" >/dev/null; then
  echo "precheck: the base $BASE does not exist" >&2
  exit 2
fi
PY="${PRECHECK_PYTHON:-.venv-verify/bin/python}"
[ -x "$PY" ] || PY=python3
changed="$( { git diff --name-only "$BASE" --; git ls-files --others --exclude-standard; } | sort -u )"
tests="$(printf '%s\n' "$changed" | "$PY" scripts/precheck_select.py)"
pins=()
if [ -f .sandbox_image ]; then
  export ARGUS_SANDBOX_IMAGE="$(tr -d '[:space:]' < .sandbox_image)"
  pins+=(ARGUS_SANDBOX_IMAGE)
fi
for f in .sandbox_image_*; do
  case "$f" in *.json) continue ;; esac
  [ -f "$f" ] || continue
  var="ARGUS_SANDBOX_IMAGE_$(printf '%s' "${f#.sandbox_image_}" | tr 'a-z' 'A-Z')"
  export "$var=$(tr -d '[:space:]' < "$f")"
  pins+=("$var")
done
ARGS=(-q -rs -p no:cacheprovider -n 4 --dist loadgroup)
echo "base: $BASE"
echo "tests: $tests"
echo "pytest: ${ARGS[*]}"
echo "pins: ${pins[*]:-}"
[ -z "${PRECHECK_PRINT:-}" ] || exit 0
# shellcheck disable=SC2086
exec "$PY" -m pytest "${ARGS[@]}" $tests
