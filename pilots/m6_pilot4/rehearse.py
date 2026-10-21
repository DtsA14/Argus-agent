"""Rehearsal of M6 pilot 4 with a SCRIPTED model (no money, no provider): the run of the approved task `fix_is_peak` in the real sandbox,
from the contract the approval published, under the pilot's own config (budget.max_usd 0.75), as
`scripts/run_code_task.py --config pilots/m6_pilot4/config_pilot4.yaml` would run it.

  PYTHONPATH=. python pilots/m6_pilot4/rehearse.py happy|negative|admission --run-id rehearsal_x [--config config.yaml]

happy:     the agent reads pricing.py and the test, makes the reference edit, validates, and finishes with honest claims: DONE.
negative:  the agent tries to edit a protected test and config.yaml (both refused) and claims success: FAILED_ACCEPTANCE.
admission: a PRICED scripted model (claude-sonnet-5-5 prices, the calibrated counter) reads the files of the "typical" scenario of the token
           simulation (about 32k tokens), changes nothing and fails its validation. It shows how the cost cap chain (config, contract) and the
           `large` reservation decide how many attempts are admitted: once under the pilot config, once under config.yaml (--config).
Run from the repository root of a checkout where the task was approved (fixtures/contracts/fix_is_peak.json) and the sandbox images exist.
Not a test: pytest does not collect it (conftest.py ignores pilots/).
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import harness.llm as hl  # noqa: E402
from codetask import run as ctrun  # noqa: E402
from codetask.run import run_code_task  # noqa: E402
from models.fake import CallableChatModel, StrictScriptedChatModel, reply  # noqa: E402
from runner import load_config  # noqa: E402

HERE = Path(__file__).resolve().parent
PILOT_CONFIG = HERE / "config_pilot4.yaml"
OLD = '    return any(start <= now.hour < end for start, end in window["utc_hours"])'
NEW = ('    # start < end: start <= hour < end. start > end crosses midnight (22-4 is 22:00 to 04:00): hour >= start or hour < end.\n'
       '    # start == end is an empty window.\n'
       '    return any(start <= now.hour < end if start <= end else (now.hour >= start or now.hour < end)\n'
       '               for start, end in window["utc_hours"])')
CLAIMS = [{"claim": "tests_pass", "evidence": "validation:regression"}, {"claim": "issue_fixed", "evidence": "validation:target"},
          {"claim": "file_changed", "path": "models/pricing.py"}]


def call(name, args, id):
    return reply(tool_calls=[{"name": name, "args": args, "id": id}], input_tokens=900, output_tokens=120)


def script(kind):
    if kind == "happy":
        return [call("ReadFile", {"path": "models/pricing.py"}, "r1"), call("ReadFile", {"path": "tests/test_peak_window.py"}, "r2"),
                call("EditFile", {"path": "models/pricing.py", "old_text": OLD, "new_text": NEW}, "e1"),
                call("RunValidation", {"id": "target"}, "v1"), call("RunValidation", {"id": "regression"}, "v2"),
                call("Finish", {"claims": CLAIMS, "summary": "is_peak matches a window that crosses midnight"}, "f1")]
    return [call("EditFile", {"path": "tests/test_peak_window.py", "old_text": "def test_no_window", "new_text": "def xtest_no_window"}, "b1"),
            call("EditFile", {"path": "config.yaml", "old_text": "weekdays_only: true", "new_text": "weekdays_only: false"}, "b2"),
            call("Finish", {"claims": CLAIMS, "summary": "fixed"}, "f1"), call("Finish", {"claims": CLAIMS, "summary": "fixed again"}, "f2")]


def setup_sandbox(cfg):
    cfg["sandbox"] = {**(cfg.get("sandbox") or {}), "kind": "docker"}
    if not os.environ.get("ARGUS_SANDBOX_IMAGE") and (ROOT / ".sandbox_image").exists():
        os.environ["ARGUS_SANDBOX_IMAGE"] = (ROOT / ".sandbox_image").read_text().strip()
    for name in cfg["sandbox"].get("environments") or {}:
        var, path = f"ARGUS_SANDBOX_IMAGE_{name.upper()}", ROOT / f".sandbox_image_{name}"
        if not os.environ.get(var) and path.exists():
            os.environ[var] = path.read_text().strip()


def limits(task, config_path):
    contract = json.loads((ROOT / "fixtures" / "contracts" / f"{task}.json").read_text(encoding="utf-8"))
    cfg = ctrun.apply_profile(load_config(config_path), contract["budget_profile"])
    cfg["roles"]["coder"]["model"] = "anthropic:claude-sonnet-5-5"
    lim = ctrun.settings(cfg, contract)
    return {"config": str(config_path), "cap_usd": lim["max_usd"], "reservation_usd": round(lim["attempt_usd"], 6),
            "attempt_tokens": lim["attempt_tokens"]}, lim


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("kind", choices=["happy", "negative", "admission"])
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--task", default="fix_is_peak")
    ap.add_argument("--config", default=str(PILOT_CONFIG), help="default: the pilot config; config.yaml shows the stock cap")
    a = ap.parse_args(argv)
    cfg = load_config(a.config)
    setup_sandbox(cfg)
    contract_path = ROOT / "fixtures" / "contracts" / f"{a.task}.json"
    if a.kind == "admission":
        import measure_context as mc
        from langchain_core.messages import AIMessage
        from codetask.tools import offered
        cfg["roles"]["coder"]["model"] = "anthropic:claude-sonnet-5-5"
        hl.provider_counter = lambda model, margin: (mc.estimate, True)
        steps = [[("ListFiles", {})],
                 [("ReadFile", {"path": f}) for f in ("models/pricing.py", "tests/test_peak_window.py", "tests/test_models.py")],
                 [("RunValidation", {"id": "target"})], [("RunValidation", {"id": "regression"})],
                 [("Finish", {"claims": CLAIMS, "summary": "done"})]]
        allowed = cfg["tools"]["coder"] + ["search_files", "edit_file"]

        def respond(messages):
            step = sum(isinstance(m, AIMessage) for m in messages) % len(steps)
            calls = [{"name": n, "args": ar, "id": f"c{step}_{j}"} for j, (n, ar) in enumerate(steps[step])]
            out_chars = sum(len(json.dumps(c["args"])) + len(c["name"]) for c in calls)
            return AIMessage(content="", tool_calls=calls, usage_metadata={
                "input_tokens": mc.estimate(messages, offered(allowed)), "output_tokens": int(20 + mc.B * out_chars), "total_tokens": 0})
        model = CallableChatModel(respond=respond)
    else:
        cfg["roles"]["coder"]["model"] = "fake:scripted"
        model = StrictScriptedChatModel(script=script(a.kind))
    r = run_code_task(contract_path=contract_path, run_id=a.run_id, runs_dir=ROOT / "runs", cfg=cfg, models={"coder": model}, echo=False)
    out = {k: r.get(k) for k in ("status", "stop_reason", "blocked_reason", "attempts", "usd_billed", "llm_calls", "tools", "budget_profile")}
    if a.kind == "admission":
        events = [json.loads(line) for line in (ROOT / "runs" / a.run_id / "events.jsonl").read_text().splitlines()]
        per = {}
        for e in events:
            if e["event"] == "llm_call" and e["status"] == "ok":
                per[e["iteration"]] = per.get(e["iteration"], 0.0) + (e.get("usd") or 0.0)
        out["usd_per_attempt"] = {str(k): round(v, 6) for k, v in sorted(per.items())}
        spend = max(per.values()) if per else 0.0
        table = {}
        for label, path in (("pilot_config", PILOT_CONFIG), ("config_yaml", ROOT / "config.yaml")):
            info, lim = limits(a.task, path)
            k = 0
            while spend * k + lim["attempt_usd"] <= lim["max_usd"] + 1e-12 and k < 9:
                k += 1
            info["attempts_admitted_if_each_spends_like_this_run"] = k
            table[label] = info
        out["admission"], out["spend_per_attempt_used_usd"] = table, round(spend, 6)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if r["status"] == "DONE" or a.kind != "happy" else 1


if __name__ == "__main__":
    sys.exit(main())
