#!/usr/bin/env bash
# Pilot 3a, REPLICATION: one guarded live run of the approved task fix_run_inspectors (the same contract, config and limits as the first run
# `pilot3a`, which failed; see INVESTIGATION.md). Run it on the VM, in the live checkout:
#
#   bash pilots/m6_pilot3/3a/go_live.sh --check-only       every gate, no key asked, no run, no money (the preflight)
#   bash pilots/m6_pilot3/3a/go_live.sh pilot3a2            the gates, then asks for the API key (not shown) and runs ONCE
#
# The key is typed by the owner into this script's prompt; it is never an argument, never written anywhere, and unset at the end.
# Every gate below must hold, or nothing is started. The expected values are fixed in this file (reviewed in the PR), not read from the environment.
# Nothing is raised or changed for this run: same contract, same profile (large), same cap ($0.75). reservation_exhausted is a result, not a reason to run again.
set -u
LIVE_DIR="${LIVE_DIR:-$HOME/pilot3a_live}"
TASK=fix_run_inspectors
CONTRACT="fixtures/contracts/$TASK.json"
RECORD="fixtures/intake/$TASK.json"
CONFIG="pilots/m6_pilot3/3a/config_pilot3a.yaml"
EXPECT_CONTRACT_SHA="0826ee93de65"                                                       # sha256 prefix of the frozen contract
EXPECT_CONFIG_SHA="46e9d99f97dcccd8365f60c8540d03fed561842e35bac7f15ca0468dfd66c655"      # sha256 of config_pilot3a.yaml (line ends normalised)
PY="${PY:-$HOME/Argus-agent/.venv-verify/bin/python}"

fail() { echo "REFUSED: $1" >&2; exit 1; }

MODE="${1:-}"
[ -n "$MODE" ] || fail "usage: go_live.sh --check-only | go_live.sh <run-id>   (run id like pilot3a2)"
if [ "$MODE" = "--check-only" ]; then RUN_ID=""; else
  RUN_ID="$MODE"
  [[ "$RUN_ID" =~ ^pilot3a[0-9]$ ]] || fail "run id must look like pilot3a2 (got '$RUN_ID')"
fi

cd "$LIVE_DIR" 2>/dev/null || fail "live checkout $LIVE_DIR not found"
[ -z "$(git status --porcelain --untracked-files=all)" ] || fail "the live checkout is not clean (git status must be empty)"
[ -f "$CONTRACT" ] && [ -f "$RECORD" ] && [ -f "$CONFIG" ] || fail "contract, intake record or pilot config missing: the task is not approved here"

# 1. contract: the approved one (name, hash, profile, limits, scope)
"$PY" - "$CONTRACT" "$RECORD" "$EXPECT_CONTRACT_SHA" <<'PYEOF' || exit 1
import json, sys
contract, record, want = json.load(open(sys.argv[1])), json.load(open(sys.argv[2])), sys.argv[3]
bad = []
if contract.get("contract") != "fix_run_inspectors": bad.append(f"contract name {contract.get('contract')!r}")
if not record.get("contract_sha256", "").startswith(want): bad.append(f"contract sha256 {record.get('contract_sha256', '')[:12]!r}, expected {want!r}")
if contract.get("budget_profile") != "large": bad.append(f"profile {contract.get('budget_profile')!r}, expected 'large'")
if contract.get("limits") != {"max_usd": 0.75, "max_iterations": 3}: bad.append(f"limits {contract.get('limits')!r}")
if contract.get("scope", {}).get("writable") != ["evals/runlog.py", "scripts/audit_run.py", "scripts/failure_trace.py"]: bad.append("writable scope is not the three files")
if bad:
    print("REFUSED: " + "; ".join(bad), file=sys.stderr); sys.exit(1)
print("gate 1 ok: contract fix_run_inspectors, sha256", want + "...", "profile large, limits $0.75 / 3 iterations, three writable files")
PYEOF

# 2. config: exactly the reviewed file, and it differs from config.yaml only in budget.max_usd = 0.75
GOT_CONFIG_SHA="$(tr -d '\r' < "$CONFIG" | sha256sum | cut -d' ' -f1)"
[ "$GOT_CONFIG_SHA" = "$EXPECT_CONFIG_SHA" ] || fail "config_pilot3a.yaml sha256 $GOT_CONFIG_SHA, expected $EXPECT_CONFIG_SHA"
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
if diffs != [("/budget/max_usd", 0.5, 0.75)]:
    print("REFUSED: the pilot config must differ from config.yaml only in budget.max_usd 0.5 -> 0.75, found " + repr(diffs), file=sys.stderr); sys.exit(1)
print("gate 2 ok: config_pilot3a.yaml is the reviewed file and differs from config.yaml only in budget.max_usd (0.50 -> 0.75)")
PYEOF

# 3. effective limits, computed by the functions a run uses (profile applied, stricter cap, one attempt's reservation)
PYTHONPATH=. "$PY" - "$CONTRACT" "$CONFIG" <<'PYEOF' || exit 1
import json, sys
from codetask import run as ctrun
from runner import load_config
contract = json.load(open(sys.argv[1]))
cfg = ctrun.apply_profile(load_config(sys.argv[2]), contract["budget_profile"])
lim = ctrun.settings(cfg, contract)
e = {"applied_profile": cfg["code_task"]["applied_profile"], "attempt_tokens": lim["attempt_tokens"],
     "coder_max_output_tokens": cfg["roles"]["coder"]["max_output_tokens"], "cap_usd": lim["max_usd"],
     "reservation_usd": round(lim["attempt_usd"], 6), "max_iterations": lim["max_iterations"]}
ok = (e["applied_profile"] == "large" and e["attempt_tokens"] == 45000 and e["coder_max_output_tokens"] == 8192
      and e["cap_usd"] == 0.75 and e["reservation_usd"] == 0.45 and e["max_iterations"] == 3)
if not ok:
    print("REFUSED: the effective limits are not large / 45000 tokens / $0.45 per attempt / cap $0.75 / 3 iterations: " + json.dumps(e), file=sys.stderr)
    raise SystemExit(1)
print("gate 3 ok: effective profile large, reservation $0.45 (45,000 tokens), cap $0.75, at most 3 attempts")
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
