#!/usr/bin/env bash
# Pilot 3a v2: one guarded live run of the approved task fix_run_inspectors_v2 (the task of pilot3a, re-approved with the profile
# large_usd) under D1 (attempt in USD, input limit per call), D2 (error lines in the feedback) and D3 (auto-validation). See PREFLIGHT.md.
# Run it on the VM, in the live checkout:
#
#   bash pilots/m6_pilot3/3a/v2/go_live.sh --check-only       every gate, no key asked, no run, no money (the preflight)
#   bash pilots/m6_pilot3/3a/v2/go_live.sh pilot3a3            the gates, then asks for the API key (not shown) and runs ONCE
#
# The key is typed by the owner into this script's prompt; it is never an argument, never written anywhere, and unset at the end.
# Every gate below must hold, or nothing is started. The expected values are fixed in this file (reviewed in the PR), not read from the
# environment. Nothing is raised for this run beyond what PREFLIGHT.md states; reservation_exhausted / context_limit are results.
set -u
LIVE_DIR="${LIVE_DIR:-$HOME/pilot3a_live}"
TASK=fix_run_inspectors_v2
CONTRACT="fixtures/contracts/$TASK.json"
RECORD="fixtures/intake/$TASK.json"
CONFIG="pilots/m6_pilot3/3a/v2/config_pilot3a_v2.yaml"
EXPECT_CONTRACT_SHA="SET_AFTER_APPROVAL"                                                  # sha256 prefix of the approved contract
EXPECT_CONFIG_SHA="ed3c277747dbee74bb77a67fe897b3416825e5a7ba1bb0792b06d41411888e06"      # sha256 of the pilot config (line ends normalised)
PY="${PY:-$HOME/Argus-agent/.venv-verify/bin/python}"

fail() { echo "REFUSED: $1" >&2; exit 1; }

MODE="${1:-}"
[ -n "$MODE" ] || fail "usage: go_live.sh --check-only | go_live.sh <run-id>   (run id like pilot3a3)"
if [ "$MODE" = "--check-only" ]; then RUN_ID=""; else
  RUN_ID="$MODE"
  [[ "$RUN_ID" =~ ^pilot3a[3-9]$ ]] || fail "run id must look like pilot3a3 (got '$RUN_ID'; pilot3a and pilot3a2 are the earlier runs)"
fi

cd "$LIVE_DIR" 2>/dev/null || fail "live checkout $LIVE_DIR not found"
[ -z "$(git status --porcelain --untracked-files=all)" ] || fail "the live checkout is not clean (git status must be empty)"
[ -f "$CONTRACT" ] && [ -f "$RECORD" ] && [ -f "$CONFIG" ] || fail "contract, intake record or pilot config missing: the task is not approved here"

# 1. contract: the approved one (name, hash, profile, limits, scope)
"$PY" - "$CONTRACT" "$RECORD" "$EXPECT_CONTRACT_SHA" <<'PYEOF' || exit 1
import json, sys
contract, record, want = json.load(open(sys.argv[1])), json.load(open(sys.argv[2])), sys.argv[3]
bad = []
if contract.get("contract") != "fix_run_inspectors_v2": bad.append(f"contract name {contract.get('contract')!r}")
if len(want) != 12 or not record.get("contract_sha256", "").startswith(want):
    bad.append(f"contract sha256 {record.get('contract_sha256', '')[:12]!r}, expected {want!r}")
if contract.get("budget_profile") != "large_usd": bad.append(f"profile {contract.get('budget_profile')!r}, expected 'large_usd'")
if contract.get("limits") != {"max_usd": 0.75, "max_iterations": 3}: bad.append(f"limits {contract.get('limits')!r}")
if contract.get("scope", {}).get("writable") != ["evals/runlog.py", "scripts/audit_run.py", "scripts/failure_trace.py"]: bad.append("writable scope is not the three files")
if bad:
    print("REFUSED: " + "; ".join(bad), file=sys.stderr); sys.exit(1)
print("gate 1 ok: contract fix_run_inspectors_v2, sha256", want + "...", "profile large_usd, limits $0.75 / 3 iterations, three writable files")
PYEOF

# 2. config: exactly the reviewed file, and it differs from config.yaml only in the three reviewed keys
GOT_CONFIG_SHA="$(tr -d '\r' < "$CONFIG" | sha256sum | cut -d' ' -f1)"
[ "$GOT_CONFIG_SHA" = "$EXPECT_CONFIG_SHA" ] || fail "config_pilot3a_v2.yaml sha256 $GOT_CONFIG_SHA, expected $EXPECT_CONFIG_SHA"
"$PY" - "$CONFIG" <<'PYEOF' || exit 1
import sys, yaml
a, b = yaml.safe_load(open("config.yaml", encoding="utf-8")), yaml.safe_load(open(sys.argv[1], encoding="utf-8"))
diffs = []
def walk(x, y, path=""):
    if isinstance(x, dict) and isinstance(y, dict):
        for k in sorted(set(x) | set(y), key=str):
            walk(x.get(k), y.get(k), path + "/" + str(k))
    elif x != y:
        diffs.append((path, x, y))
walk(a, b)
want = [("/budget/max_tokens", 200000, 1200000), ("/budget/max_usd", 0.5, 0.75), ("/code_task/auto_validate", False, True)]
if diffs != want:
    print("REFUSED: the pilot config must differ from config.yaml only in " + repr(want) + ", found " + repr(diffs), file=sys.stderr)
    sys.exit(1)
print("gate 2 ok: config_pilot3a_v2.yaml is the reviewed file; it differs from config.yaml only in budget.max_usd (0.50 -> 0.75),"
      " budget.max_tokens (200,000 -> 1,200,000) and code_task.auto_validate (false -> true)")
PYEOF

# 3. effective limits and loop policy, computed by the functions a run uses; an empty ledger admits one attempt
PYTHONPATH=. "$PY" - "$CONTRACT" "$CONFIG" <<'PYEOF' || exit 1
import json, sys, tempfile
from pathlib import Path
from codetask import run as ctrun
from harness.events import EventLog
from runner import load_config
contract = json.load(open(sys.argv[1]))
cfg = ctrun.apply_profile(load_config(sys.argv[2]), contract["budget_profile"])
lim = ctrun.settings(cfg, contract)
with tempfile.TemporaryDirectory() as d:
    blocker = ctrun.admission(EventLog(Path(d) / "e.jsonl"), lim)
e = {"applied_profile": cfg["code_task"]["applied_profile"], "attempt_tokens": lim["attempt_tokens"],
     "attempt_usd": lim["attempt_usd"], "max_input_tokens": lim["max_input_tokens"],
     "coder_max_output_tokens": cfg["roles"]["coder"]["max_output_tokens"], "coder_model": cfg["roles"]["coder"]["model"],
     "cap_usd": lim["max_usd"], "run_max_tokens": lim["max_tokens"], "max_iterations": lim["max_iterations"],
     "max_steps": lim["max_steps"], "auto_validate": cfg["code_task"]["auto_validate"],
     "auto_validate_max": cfg["code_task"]["auto_validate_max"], "admission_with_empty_ledger": blocker}
want = {"applied_profile": "large_usd", "attempt_tokens": 400000, "attempt_usd": 0.45, "max_input_tokens": 40000,
        "coder_max_output_tokens": 8192, "coder_model": "anthropic:claude-sonnet-5-5", "cap_usd": 0.75, "run_max_tokens": 1200000,
        "max_iterations": 3, "max_steps": 12, "auto_validate": True, "auto_validate_max": 4, "admission_with_empty_ledger": None}
if e != want:
    print("REFUSED: the effective limits are not the reviewed ones: " + json.dumps({k: (e[k], want[k]) for k in want if e[k] != want[k]}),
          file=sys.stderr)
    raise SystemExit(1)
print("gate 3 ok: profile large_usd ($0.45 per attempt, input <= 40,000 per call, output 8,192), cap $0.75, run tokens 1,200,000,"
      " 3 attempts, 12 steps, auto-validation on (4 per attempt); a second attempt only if the first spent <= $0.30")
PYEOF

# 4. the live path itself refuses without ARGUS_LIVE=1 and creates nothing; a run id that exists is refused
( unset ARGUS_LIVE ANTHROPIC_API_KEY
  PROBE="$(mktemp -d)"
  "$PY" scripts/run_code_task.py --contract "$CONTRACT" --run-id gate_nolive --runs-dir "$PROBE" --config "$CONFIG" --sandbox docker --quiet 2>&1 | grep -q "set ARGUS_LIVE=1" \
    && [ -z "$(ls -A "$PROBE")" ]
  rc=$?; rm -rf "$PROBE"; exit $rc ) || fail "without ARGUS_LIVE=1 the runner must refuse and create no run directory; it did not"
echo "gate 4 ok: without ARGUS_LIVE=1 the runner refuses and creates no run directory"
if [ -n "$RUN_ID" ]; then [ ! -e "runs/$RUN_ID" ] || fail "run $RUN_ID already exists (use a new id; --resume only for a run that died)"; fi

if [ "$MODE" = "--check-only" ]; then echo "check-only: every gate holds. Nothing was started."; exit 0; fi

# 5. the key, typed now; nothing is started if it is empty
read -rsp "Type or paste the API key, then Enter (not shown): " ANTHROPIC_API_KEY; echo
[ "${#ANTHROPIC_API_KEY}" -gt 0 ] || fail "the key is empty; nothing was started"
echo "key length: ${#ANTHROPIC_API_KEY}"
export ANTHROPIC_API_KEY ARGUS_LIVE=1 ARGUS_SANDBOX_IMAGE="$(cat .sandbox_image)" ARGUS_SANDBOX_IMAGE_ARGUS="$(cat .sandbox_image_argus)"
"$PY" scripts/run_code_task.py --contract "$CONTRACT" --run-id "$RUN_ID" --config "$CONFIG" --sandbox docker
rc=$?
unset ANTHROPIC_API_KEY ARGUS_LIVE
echo "finished (exit $rc). The key is gone from this shell. Tell Claude; revoke the key in the dashboard after the last run."
exit $rc
