#!/usr/bin/env bash
# Pilot W2b-2, step 1: one guarded live run of the drafter (scripts/draft_task.py) on a new issue (the PR.md title), over intake
# argus_p7. It only drafts: approval and the agent run are later steps with their own gates. See w2b2/PREFLIGHT.md. On the VM, in
# the live checkout:
#
#   bash pilots/m6_w2b/w2b2/go_live_draft.sh --check-only   every gate, no key asked, no run, no money (the preflight)
#   bash pilots/m6_w2b/w2b2/go_live_draft.sh w2b2d1          the gates, then asks for the API key (not shown) and runs ONCE
#
# The key is typed by the owner into this script's prompt; it is never an argument, never written anywhere, and unset at the end.
# Every gate below must hold, or nothing is started. The expected values are fixed in this file (reviewed in the PR), not read from the
# environment. Terminal times (start, key entered, end) go to ~/argus-supervision.log, outside the repository.
set -u
LIVE_DIR="${LIVE_DIR:-$HOME/pilot3a_live}"
INTAKE=argus_p7
ISSUE="pilots/m6_w2b/w2b2/issue.txt"
CONFIG="pilots/m6_w2b/w2b2/config_w2b2_draft.yaml"
MAX_USD=0.75
EXPECT_ISSUE_SHA="e4d511dbcc3e61b086778084e3c22247ebc4e5da23a6b9bc43a6ed33613cce0f"     # sha256 of the issue (line ends normalised)
EXPECT_CONFIG_SHA="eea49cd5455bb244cbe737186b9b3c0d8494025b44b779d500f3c8e56c52a839"    # sha256 of the pilot config (line ends normalised)
PY="${PY:-$HOME/Argus-agent/.venv-verify/bin/python}"
SUPLOG="$HOME/argus-supervision.log"

fail() { echo "REFUSED: $1" >&2; exit 1; }

MODE="${1:-}"
[ -n "$MODE" ] || fail "usage: go_live_draft.sh --check-only | go_live_draft.sh <run-id>   (run id like w2b2d1)"
if [ "$MODE" = "--check-only" ]; then RUN_ID=""; else
  RUN_ID="$MODE"
  [[ "$RUN_ID" =~ ^w2b2d[1-9]$ ]] || fail "run id must look like w2b2d1 (got '$RUN_ID')"
fi

cd "$LIVE_DIR" 2>/dev/null || fail "live checkout $LIVE_DIR not found"
[ -z "$(git status --porcelain --untracked-files=all)" ] || fail "the live checkout is not clean (git status must be empty)"
[ -f "$ISSUE" ] && [ -f "$CONFIG" ] && [ -f scripts/draft_task.py ] || fail "issue, pilot config or scripts/draft_task.py missing"

# 1. the intake: unchanged since it was taken in, without pilots/ and verification/ (excluded at intake)
PYTHONPATH=. "$PY" - "$INTAKE" <<'PYEOF' || exit 1
import sys
from pathlib import Path
from acceptance import intake
name = sys.argv[1]
rec = intake.record_for(f"fixtures/repos/{name}", Path("."))
bad = []
if rec is None or rec.get("kind", "intake") != "intake":
    bad.append(f"no intake record for {name}")
else:
    bad += intake.check(rec, Path("fixtures/repos") / name)
for leak in ("pilots", "verification"):
    if (Path("fixtures/repos") / name / leak).exists():
        bad.append(f"{leak}/ is in the intake (it must be excluded)")
if bad:
    print("REFUSED: " + "; ".join(bad), file=sys.stderr); sys.exit(1)
print(f"gate 1 ok: intake {name} unchanged ({rec['files']} files, commit {rec['commit'][:12]}); no pilots/ or verification/ in it")
PYEOF

# 2. the issue and the config: exactly the reviewed files; the config differs from config.yaml only in the four reviewed keys
GOT_ISSUE_SHA="$(tr -d '\r' < "$ISSUE" | sha256sum | cut -d' ' -f1)"
[ "$GOT_ISSUE_SHA" = "$EXPECT_ISSUE_SHA" ] || fail "issue.txt sha256 $GOT_ISSUE_SHA, expected $EXPECT_ISSUE_SHA"
GOT_CONFIG_SHA="$(tr -d '\r' < "$CONFIG" | sha256sum | cut -d' ' -f1)"
[ "$GOT_CONFIG_SHA" = "$EXPECT_CONFIG_SHA" ] || fail "config_w2b2_draft.yaml sha256 $GOT_CONFIG_SHA, expected $EXPECT_CONFIG_SHA"
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
want = [("/budget/max_tokens", 200000, 1200000), ("/budget/max_usd", 0.5, 0.75), ("/drafter/attempt_tokens", 200000, 400000),
        ("/llm/prompt_cache/enabled", False, True)]
if diffs != want:
    print("REFUSED: the pilot config must differ from config.yaml only in " + repr(want) + ", found " + repr(diffs), file=sys.stderr)
    sys.exit(1)
print("gate 2 ok: issue.txt and config_w2b2_draft.yaml are the reviewed files; the config differs from config.yaml only in budget.max_tokens"
      " (200,000 -> 1,200,000), budget.max_usd (0.50 -> 0.75), drafter.attempt_tokens (200,000 -> 400,000) and"
      " llm.prompt_cache.enabled (false -> true)")
PYEOF

# 3. effective limits and policy, computed by the functions a drafter run uses (cap = min(budget.max_usd, --max-usd))
PYTHONPATH=. "$PY" - "$CONFIG" "$MAX_USD" <<'PYEOF' || exit 1
import json, sys
from codetask import drafter as dt
from harness.llm import prompt_cache_for
from models.registry import ModelRef
from runner import load_config
cfg = load_config(sys.argv[1])
cap = min(float(cfg["budget"]["max_usd"]), float(sys.argv[2]))
cfg = {**cfg, "budget": {**cfg["budget"], "max_usd": cap}}
lim = dt.drafter_settings(cfg)
role = cfg["drafter"]["role"]
ref = ModelRef.parse(cfg["roles"][role]["model"])
e = {"cap_usd": cap, **lim, "max_submits": cfg["drafter"]["max_submits"], "environment": cfg["drafter"]["environment"],
     "validation_timeout_s": cfg["drafter"]["validation_timeout_s"], "model": str(ref),
     "max_output_tokens": cfg["roles"][role]["max_output_tokens"], "tools": cfg["tools"][role],
     "prompt_cache": prompt_cache_for(cfg, role, ref), "prices": cfg["prices"][str(ref)]}
want = {"cap_usd": 0.75, "attempt_tokens": 400000, "attempt_usd": 0.7, "max_input_tokens": 64000, "max_steps": 16, "max_usd": 0.75,
        "max_submits": 3, "environment": "argus", "validation_timeout_s": 300, "model": "anthropic:claude-sonnet-5-5",
        "max_output_tokens": 16384, "tools": ["list_files", "search_files", "read_file"], "prompt_cache": True,
        "prices": {"input": 2.0, "output": 10.0, "cache_read": 0.1, "cache_write_5m": 2.5, "cache_write_1h": 4.0}}
if e != want:
    print("REFUSED: the effective limits are not the reviewed ones: " + json.dumps({k: (e.get(k), want[k]) for k in want if e.get(k) != want[k]}),
          file=sys.stderr)
    raise SystemExit(1)
print("gate 3 ok: Sonnet 5.5, one attempt of $0.70 (cap $0.75), input <= 64,000 per call, output 16,384, 16 steps, 3 submits,"
      " read-only tools, validations in environment argus, prompt caching on (every input token reserved at the $2.50/M write rate)")
PYEOF

# 4. the live path itself refuses without ARGUS_LIVE=1 and creates nothing; a run id that exists is refused
( unset ARGUS_LIVE ANTHROPIC_API_KEY
  PROBE="$(mktemp -d)"
  "$PY" scripts/draft_task.py --intake "$INTAKE" --issue-file "$ISSUE" --max-usd "$MAX_USD" --run-id gate_nolive --runs-dir "$PROBE" \
      --config "$CONFIG" --quiet 2>&1 | grep -q "set ARGUS_LIVE=1" && [ -z "$(ls -A "$PROBE")" ]
  rc=$?; rm -rf "$PROBE"; exit $rc ) || fail "without ARGUS_LIVE=1 the drafter must refuse and create no run directory; it did not"
echo "gate 4 ok: without ARGUS_LIVE=1 the drafter refuses and creates no run directory"
if [ -n "$RUN_ID" ]; then [ ! -e "runs/$RUN_ID" ] || fail "run $RUN_ID already exists (use a new id; --resume only for a run that died)"; fi

if [ "$MODE" = "--check-only" ]; then echo "check-only: every gate holds. Nothing was started."; exit 0; fi

# 5. the key, typed now; nothing is started if it is empty or not shaped like one key
echo "$(date -u +%FT%TZ) w2b2 $RUN_ID gates_passed" >> "$SUPLOG"
read -rsp "Type or paste the API key, then Enter (not shown): " ANTHROPIC_API_KEY; echo
[ "${#ANTHROPIC_API_KEY}" -gt 0 ] || fail "the key is empty; nothing was started"
case "$ANTHROPIC_API_KEY" in sk-ant-*) ;; *) fail "the key does not start with sk-ant-; nothing was started" ;; esac
[[ "$ANTHROPIC_API_KEY" =~ [[:space:]] ]] && fail "the key contains whitespace (pasted twice?); nothing was started"
[[ "${ANTHROPIC_API_KEY#sk-ant-}" == *sk-ant-* ]] && fail "the key contains sk-ant- more than once (pasted twice?); nothing was started"
echo "key length: ${#ANTHROPIC_API_KEY}"
echo "$(date -u +%FT%TZ) w2b2 $RUN_ID key_entered" >> "$SUPLOG"
export ANTHROPIC_API_KEY ARGUS_LIVE=1 ARGUS_SANDBOX_IMAGE="$(cat .sandbox_image)" ARGUS_SANDBOX_IMAGE_ARGUS="$(cat .sandbox_image_argus)"
"$PY" scripts/draft_task.py --intake "$INTAKE" --issue-file "$ISSUE" --max-usd "$MAX_USD" --run-id "$RUN_ID" --config "$CONFIG"
rc=$?
unset ANTHROPIC_API_KEY ARGUS_LIVE
echo "$(date -u +%FT%TZ) w2b2 $RUN_ID run_end exit=$rc" >> "$SUPLOG"
echo "finished (exit $rc). The key is gone from this shell. Tell Claude; revoke the key in the dashboard after the last run."
exit $rc
