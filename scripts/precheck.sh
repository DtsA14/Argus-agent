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
# quotePath off: a non-ASCII name is not printed in quotes, so it is neither lost nor misread; one test file per array element: a
# name with a space is one file.
changed="$( { git -c core.quotePath=false diff --name-only "$BASE" --; git -c core.quotePath=false ls-files --others --exclude-standard; } | sort -u )"
mapfile -t tests < <(printf '%s\n' "$changed" | PYTHONUTF8=1 "$PY" scripts/precheck_select.py)
if [ "${#tests[@]}" -eq 0 ] || [ -z "${tests[0]}" ]; then
  echo "precheck: no test selected (the fixed set of tests is missing?): not running the whole suite instead" >&2
  exit 2
fi
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
printf -v joined '%s, ' "${tests[@]}"
echo "tests: ${joined%, }"
echo "pytest: ${ARGS[*]}"
echo "pins: ${pins[*]:-}"
echo "sandbox groups: ${VERIFY_SANDBOX_GROUPS:-2} (VERIFY_SANDBOX_GROUPS)"
[ -z "${PRECHECK_PRINT:-}" ] || exit 0
exec "$PY" -m pytest "${ARGS[@]}" "${tests[@]}"
