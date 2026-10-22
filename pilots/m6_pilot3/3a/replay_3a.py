"""Replay of the live run pilot3a through the real harness with the RECORDED model replies (no provider, no money).

The model is replaced by a function that answers each request with the reply the live model gave to the same request (found by the prompt hash), with
the token usage the provider reported; the pre-send token estimate is the one the ledger recorded for that request. Tools and validation are real
(the sandbox runs the tests). If the harness reaches the same outcome, the outcome is determined by (the replies, the budget), not by anything that happened
at the provider.

  PYTHONPATH=. python pilots/m6_pilot3/3a/replay_3a.py runs/pilot3a <runs_dir> <run_id> [--config pilots/m6_pilot3/3a/config_pilot3a.yaml]
"""
import json
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))

import harness.llm as hl  # noqa: E402
from langchain_core.messages import AIMessage  # noqa: E402
from codetask.run import run_code_task  # noqa: E402
from codetask.tools import offered  # noqa: E402
from harness.steps import message_from_json  # noqa: E402
from models.fake import CallableChatModel  # noqa: E402
from runner import load_config  # noqa: E402

orig, runs_dir, run_id = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
config_path = sys.argv[sys.argv.index("--config") + 1] if "--config" in sys.argv else str(ROOT / "pilots/m6_pilot3/3a/config_pilot3a.yaml")
events = [json.loads(line) for line in (orig / "events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
calls = [e for e in events if e["event"] == "llm_call"]
est_by_hash = {e["prompt_hash"]: e["est_input"] for e in calls}
usage_by_hash = {e["prompt_hash"]: (e["input_tokens"], e["output_tokens"]) for e in calls if e["status"] == "ok"}
step_by_hash = {e["prompt_hash"]: (e["iteration"], e["step"]) for e in calls if e["status"] == "ok"}
db = sqlite3.connect(orig / "memo.sqlite")
reply_by_step = {}
for k, v in db.execute("select key, value from memo"):
    key = json.loads(k)
    if key[0] == "llm":
        reply_by_step[(key[3], key[4])] = json.loads(v)

cfg = load_config(config_path)
cfg["code_task"]["feedback_error_excerpt"] = False       # pilot3a ran before D2: its attempt-1 prompt had no excerpts
cfg["sandbox"] = {**(cfg.get("sandbox") or {}), "kind": "docker"}
for name in cfg["sandbox"].get("environments") or {}:
    var, path = f"ARGUS_SANDBOX_IMAGE_{name.upper()}", ROOT / f".sandbox_image_{name}"
    if not os.environ.get(var) and path.exists():
        os.environ[var] = path.read_text().strip()
if not os.environ.get("ARGUS_SANDBOX_IMAGE") and (ROOT / ".sandbox_image").exists():
    os.environ["ARGUS_SANDBOX_IMAGE"] = (ROOT / ".sandbox_image").read_text().strip()
cfg["roles"]["coder"]["model"] = "anthropic:claude-sonnet-5-5"          # priced like the live model
contract_path = ROOT / "fixtures" / "contracts" / "fix_run_inspectors.json"       # the approved contract the live run was frozen from
contract = json.loads(contract_path.read_text(encoding="utf-8"))
tools = offered(cfg["tools"]["coder"] + list(contract.get("tools") or []))
missing = []


def estimate(messages, tools_):
    h = hl.prompt_hash(messages, tools_)
    if h not in est_by_hash:
        missing.append(h)
        return 10 ** 9                      # a request the live run never made: refuse it
    return est_by_hash[h]


def respond(messages):
    h = hl.prompt_hash(messages, tools)
    if h not in step_by_hash:
        missing.append(h)
        raise RuntimeError("the replay asked something the live run never asked: " + h)
    msg = message_from_json(reply_by_step[step_by_hash[h]])
    tin, tout = usage_by_hash[h]
    return AIMessage(content=msg.content, tool_calls=msg.tool_calls, usage_metadata={"input_tokens": tin, "output_tokens": tout, "total_tokens": tin + tout})


hl.provider_counter = lambda model, margin: (estimate, True)
r = run_code_task(contract_path=contract_path, run_id=run_id, runs_dir=runs_dir, cfg=cfg, models={"coder": CallableChatModel(respond=respond)}, echo=False)
new = [json.loads(line) for line in (runs_dir / run_id / "events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
new_calls = [e for e in new if e["event"] == "llm_call"]
key = lambda e: (e["iteration"], e["step"], e["status"], e["prompt_hash"], e.get("input_tokens"), e.get("output_tokens"))  # noqa: E731
same_calls = [key(e) for e in calls] == [key(e) for e in new_calls]
old_result = json.loads((orig / "result.json").read_text(encoding="utf-8"))
v_old = json.loads((orig / "verdict_1.json").read_text(encoding="utf-8")) if (orig / "verdict_1.json").exists() else None
v_new = json.loads((runs_dir / run_id / "verdict_1.json").read_text(encoding="utf-8")) if (runs_dir / run_id / "verdict_1.json").exists() else None
v0_old = json.loads((orig / "verdict_0.json").read_text(encoding="utf-8"))
v0_new = json.loads((runs_dir / run_id / "verdict_0.json").read_text(encoding="utf-8"))
out = {
    "live": {k: old_result.get(k) for k in ("status", "stop_reason", "attempts", "usd_billed", "llm_calls")},
    "replay": {k: r.get(k) for k in ("status", "stop_reason", "attempts", "usd_billed", "llm_calls")},
    "attempt_ends_live": [e["reason"] for e in events if e["event"] == "attempt_end"],
    "attempt_ends_replay": [e["reason"] for e in new if e["event"] == "attempt_end"],
    "same_sequence_of_calls (iteration, step, status, prompt_hash, tokens)": same_calls,
    "calls_live": len(calls), "calls_replay": len(new_calls),
    "verdict_0_workspace_digest_live": v0_old["workspace_digest"][:16], "verdict_0_workspace_digest_replay": v0_new["workspace_digest"][:16],
    "verdict_0_failing_live": [c["id"] for c in v0_old["criteria"] if c["status"] != "pass"],
    "verdict_0_failing_replay": [c["id"] for c in v0_new["criteria"] if c["status"] != "pass"],
    "verdict_1_workspace_digest_live": v_old["workspace_digest"][:16] if v_old else None,
    "verdict_1_workspace_digest_replay": v_new["workspace_digest"][:16] if v_new else None,
    "requests_the_live_run_never_made": len(missing),
}
print(json.dumps(out, indent=1))
