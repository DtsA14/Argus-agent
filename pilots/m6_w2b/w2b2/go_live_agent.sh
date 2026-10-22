#!/usr/bin/env bash
# Pilot W2b-2, step 2: one guarded live run of the agent on pr_title2, the task the drafter wrote (w2b2d3) and Atha approved
# without a reference patch (feasibility unproven). Auto-validation and prompt caching on. See w2b2/PREFLIGHT_AGENT.md.
# On the VM, in the live checkout:
#
#   bash pilots/m6_w2b/w2b2/go_live_agent.sh --check-only   every gate, no key asked, no run, no money (the preflight)
#   bash pilots/m6_w2b/w2b2/go_live_agent.sh w2b2a1          the gates, then asks for the API key (not shown) and runs ONCE
#
# The key is typed by the owner into this script's prompt; it is never an argument, never written anywhere, and unset at the end.
# Every gate below must hold, or nothing is started. The expected values are fixed in this file (reviewed in the PR), not read from the
# environment. Nothing is raised for this run beyond what PREFLIGHT.md states; reservation_exhausted / context_limit are results.
set -u
LIVE_DIR="${LIVE_DIR:-$HOME/pilot3a_live}"
TASK=pr_title2
CONTRACT="fixtures/contracts/$TASK.json"
RECORD="fixtures/intake/$TASK.json"
CONFIG="pilots/m6_w2b/w2b2/config_w2b2_agent.yaml"
EXPECT_CONTRACT_SHA="4de6373c659a"                                                        # sha256 prefix of the approved contract
EXPECT_CONFIG_SHA="a890003e7c1b4607bc60d8dbf37e61f0950ad83c1a1a4505c0fe11d1129ecd7d"      # sha256 of the pilot config (line ends normalised)
PY="${PY:-$HOME/Argus-agent/.venv-verify/bin/python}"
SUPLOG="$HOME/argus-supervision.log"

fail() { echo "REFUSED: $1" >&2; exit 1; }

MODE="${1:-}"
[ -n "$MODE" ] || fail "usage: go_live_agent.sh --check-only | go_live_agent.sh <run-id>   (run id like w2b2a1)"
if [ "$MODE" = "--check-only" ]; then RUN_ID=""; else
  RUN_ID="$MODE"
  [[ "$RUN_ID" =~ ^w2b2a[1-9]$ ]] || fail "run id must look like w2b2a1 (got '$RUN_ID')"
fi

cd "$LIVE_DIR" 2>/dev/null || fail "live checkout $LIVE_DIR not found"
[ -z "$(git status --porcelain --untracked-files=all)" ] || fail "the live checkout is not clean (git status must be empty)"
[ -f "$CONTRACT" ] && [ -f "$RECORD" ] && [ -f "$CONFIG" ] || fail "contract, intake record or pilot config missing: the task is not approved here"

# 1. contract: the approved one (name, hash, profile, limits, scope)
"$PY" - "$CONTRACT" "$RECORD" "$EXPECT_CONTRACT_SHA" <<'PYEOF' || exit 1
import json, sys
contract, record, want = json.load(open(sys.argv[1])), json.load(open(sys.argv[2])), sys.argv[3]
bad = []
if contract.get("contract") != "pr_title2": bad.append(f"contract name {contract.get('contract')!r}")
if len(want) != 12 or not record.get("contract_sha256", "").startswith(want):
    bad.append(f"contract sha256 {record.get('contract_sha256', '')[:12]!r}, expected {want!r}")
if contract.get("budget_profile") != "default": bad.append(f"profile {contract.get('budget_profile')!r}, expected 'default'")
if contract.get("limits") != {"max_usd": 0.5, "max_iterations": 3}: bad.append(f"limits {contract.get('limits')!r}")
if contract.get("scope", {}).get("writable") != ["codetask/review.py"]: bad.append("writable scope is not codetask/review.py alone")
if contract.get("tools") != ["edit_file"]: bad.append(f"tools {contract.get('tools')!r}, expected ['edit_file']")
if record.get("feasibility") != "unproven" or record.get("kind") != "task": bad.append("the record is not an unproven task")
if bad:
    print("REFUSED: " + "; ".join(bad), file=sys.stderr); sys.exit(1)
print("gate 1 ok: contract pr_title2, sha256", want + "...", "profile default, limits $0.50 / 3 iterations, one writable file,"
      " edit_file added, approved without a reference patch (feasibility unproven)")
PYEOF

# 2. config: exactly the reviewed file, and it differs from config.yaml only in the two reviewed keys
GOT_CONFIG_SHA="$(tr -d '\r' < "$CONFIG" | sha256sum | cut -d' ' -f1)"
[ "$GOT_CONFIG_SHA" = "$EXPECT_CONFIG_SHA" ] || fail "config_w2b2_agent.yaml sha256 $GOT_CONFIG_SHA, expected $EXPECT_CONFIG_SHA"
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
want = [("/code_task/auto_validate", False, True), ("/llm/prompt_cache/enabled", False, True)]
if diffs != want:
    print("REFUSED: the pilot config must differ from config.yaml only in " + repr(want) + ", found " + repr(diffs), file=sys.stderr)
    sys.exit(1)
print("gate 2 ok: config_w2b2_agent.yaml is the reviewed file; it differs from config.yaml only in code_task.auto_validate"
      " (false -> true) and llm.prompt_cache.enabled (false -> true)")
PYEOF

# 3. effective limits and loop policy, computed by the functions a run uses; an empty ledger admits one attempt
PYTHONPATH=. "$PY" - "$CONTRACT" "$CONFIG" <<'PYEOF' || exit 1
import json, sys, tempfile
from pathlib import Path
from codetask import run as ctrun
from harness.events import EventLog
from harness.llm import prompt_cache_for
from models.registry import ModelRef
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
     "auto_validate_max": cfg["code_task"]["auto_validate_max"], "admission_with_empty_ledger": blocker,
     "prompt_cache": prompt_cache_for(cfg, "coder", ModelRef.parse(cfg["roles"]["coder"]["model"])),
     "coder_prices": cfg["prices"][cfg["roles"]["coder"]["model"]]}
want = {"applied_profile": "default", "attempt_tokens": 30000, "attempt_usd": 0.3, "max_input_tokens": None,
        "coder_max_output_tokens": 4096, "coder_model": "anthropic:claude-sonnet-5-5", "cap_usd": 0.5, "run_max_tokens": 200000,
        "max_iterations": 3, "max_steps": 12, "auto_validate": True, "auto_validate_max": 4, "admission_with_empty_ledger": None,
        "prompt_cache": True, "coder_prices": {"input": 2.0, "output": 10.0, "cache_read": 0.1, "cache_write_5m": 2.5,
                                               "cache_write_1h": 4.0}}
if e != want:
    print("REFUSED: the effective limits are not the reviewed ones: " + json.dumps({k: (e[k], want[k]) for k in want if e[k] != want[k]}),
          file=sys.stderr)
    raise SystemExit(1)
print("gate 3 ok: profile default (30,000 tokens per attempt, reserved as $0.30; output 4,096), cap $0.50, run tokens 200,000,"
      " 3 attempts, 12 steps, auto-validation on (4 per attempt), prompt caching on (Sonnet 5.5: every input token reserved at the"
      " $2.50/M write rate, reads $0.10/M); a second attempt only if the first spent <= $0.20")
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
echo "$(date -u +%FT%TZ) w2b2 $RUN_ID gates_passed" >> "$SUPLOG"
read -rsp "Type or paste the API key, then Enter (not shown): " ANTHROPIC_API_KEY; echo
[ "${#ANTHROPIC_API_KEY}" -gt 0 ] || fail "the key is empty; nothing was started"
# The shape of an Anthropic key, checked before anything starts (pilot3a3 died on a key pasted twice). Never printed.
case "$ANTHROPIC_API_KEY" in sk-ant-*) ;; *) fail "the key does not start with sk-ant-; nothing was started" ;; esac
[[ "$ANTHROPIC_API_KEY" =~ [[:space:]] ]] && fail "the key contains whitespace (pasted twice?); nothing was started"
[[ "${ANTHROPIC_API_KEY#sk-ant-}" == *sk-ant-* ]] && fail "the key contains sk-ant- more than once (pasted twice?); nothing was started"
echo "key length: ${#ANTHROPIC_API_KEY}"
echo "$(date -u +%FT%TZ) w2b2 $RUN_ID key_entered" >> "$SUPLOG"
export ANTHROPIC_API_KEY ARGUS_LIVE=1 ARGUS_SANDBOX_IMAGE="$(cat .sandbox_image)" ARGUS_SANDBOX_IMAGE_ARGUS="$(cat .sandbox_image_argus)"
"$PY" scripts/run_code_task.py --contract "$CONTRACT" --run-id "$RUN_ID" --config "$CONFIG" --sandbox docker
rc=$?
unset ANTHROPIC_API_KEY ARGUS_LIVE
echo "$(date -u +%FT%TZ) w2b2 $RUN_ID run_end exit=$rc" >> "$SUPLOG"
echo "finished (exit $rc). The key is gone from this shell. Tell Claude; revoke the key in the dashboard after the last run."
exit $rc
