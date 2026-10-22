"""Rehearsal of M6 pilot 5 with a SCRIPTED model (no money, no provider): the run of the approved task `fix_window_strict` in the real sandbox,
from the contract the approval published, under the pilot's own config (budget.max_usd 0.75), as
`scripts/run_code_task.py --config pilots/m6_pilot5/config_pilot5.yaml` would run it.

  PYTHONPATH=. python pilots/m6_pilot5/rehearse.py happy|negative|admission --run-id rehearsal_x [--config config.yaml]
  PYTHONPATH=. python pilots/m6_pilot5/rehearse.py effective        # no run: the effective limits under the pilot config and under config.yaml

happy:     the agent reads pricing.py and the strict test, makes the reference edit, validates, and finishes with honest claims: DONE.
negative:  the agent tries to edit a protected test and config.yaml (both refused) and claims success: FAILED_ACCEPTANCE.
admission: a PRICED scripted model (claude-sonnet-5-5 prices, the calibrated counter) reads the files of the "typical" scenario of the token
           simulation, changes nothing and fails its validation: how many attempts the cost cap chain admits, under the pilot config and under config.yaml.
effective: the limits a run would really use (profile applied by codetask.run.apply_profile, cap = the stricter of config and contract, the
           reservation of one attempt, and the number of attempts that are possible for several levels of spend per attempt).
Run from the repository root of a checkout where the task was approved (fixtures/contracts/fix_window_strict.json) and the sandbox images exist.
Not a test: pytest does not collect it (conftest.py ignores pilots/).
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
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
PILOT_CONFIG = HERE / "config_pilot5.yaml"
CLAIMS = [{"claim": "tests_pass", "evidence": "validation:regression"}, {"claim": "issue_fixed", "evidence": "validation:target"},
          {"claim": "file_changed", "path": "models/pricing.py"}]


def call(name, args, id):
    return reply(tool_calls=[{"name": name, "args": args, "id": id}], input_tokens=900, output_tokens=120)


def edit_blocks(task):
    """(old, new): the is_peak function of the task repository, and the reference patch's version of it (applied to a scratch copy)."""
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "w"
        (work / "models").mkdir(parents=True)
        shutil.copy(ROOT / "fixtures" / "repos" / task / "models" / "pricing.py", work / "models" / "pricing.py")
        base = (work / "models" / "pricing.py").read_text(encoding="utf-8").replace("\r\n", "\n")
        subprocess.run(["git", "apply", str(HERE / "reference.patch")], cwd=work, check=True)
        ref = (work / "models" / "pricing.py").read_text(encoding="utf-8").replace("\r\n", "\n")
    old = base[base.index("def is_peak"):base.index("def multiplier")].rstrip("\n")
    new = ref[ref.index("class WindowError"):ref.index("def multiplier")].rstrip("\n")
    return old, new


def script(kind, task):
    if kind == "happy":
        old, new = edit_blocks(task)
        return [call("ReadFile", {"path": "models/pricing.py"}, "r1"), call("ReadFile", {"path": "tests/test_peak_window_strict.py"}, "r2"),
                call("EditFile", {"path": "models/pricing.py", "old_text": old, "new_text": new}, "e1"),
                call("RunValidation", {"id": "target"}, "v1"), call("RunValidation", {"id": "regression"}, "v2"),
                call("Finish", {"claims": CLAIMS, "summary": "is_peak refuses windows and times it cannot read safely"}, "f1")]
    return [call("EditFile", {"path": "tests/test_peak_window_strict.py", "old_text": "def test_no_window", "new_text": "def xtest_no_window"}, "b1"),
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
    """The effective limits of a run of this contract under this config, computed by the same functions the run uses."""
    contract = json.loads((ROOT / "fixtures" / "contracts" / f"{task}.json").read_text(encoding="utf-8"))
    cfg = ctrun.apply_profile(load_config(config_path), contract["budget_profile"])
    cfg["roles"]["coder"]["model"] = "anthropic:claude-sonnet-5-5"
    lim = ctrun.settings(cfg, contract)
    info = {"config": str(config_path), "contract_profile": contract["budget_profile"], "applied_profile": cfg["code_task"]["applied_profile"],
            "attempt_tokens": lim["attempt_tokens"], "coder_max_output_tokens": cfg["roles"]["coder"]["max_output_tokens"],
            "config_budget_max_usd": load_config(config_path)["budget"]["max_usd"], "contract_limits": contract["limits"],
            "cap_usd": lim["max_usd"], "reservation_usd": round(lim["attempt_usd"], 6), "max_iterations": lim["max_iterations"]}
    table = {}
    for spend in (0.06, 0.11, 0.20, 0.30, 0.45):          # what one attempt costs: a clean path, a typical one, a heavy one, ..., the whole reservation
        k = 0
        while k < lim["max_iterations"] and spend * k + lim["attempt_usd"] <= lim["max_usd"] + 1e-12:
            k += 1
        table[f"each attempt spends ${spend:.2f}"] = k
    info["attempts_possible"] = table
    return info, lim


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("kind", choices=["happy", "negative", "admission", "effective"])
    ap.add_argument("--run-id")
    ap.add_argument("--task", default="fix_window_strict")
    ap.add_argument("--config", default=str(PILOT_CONFIG), help="default: the pilot config; config.yaml shows the stock cap")
    a = ap.parse_args(argv)
    if a.kind == "effective":
        print(json.dumps({"pilot_config": limits(a.task, PILOT_CONFIG)[0], "config_yaml": limits(a.task, ROOT / "config.yaml")[0]}, indent=1))
        return 0
    if not a.run_id:
        ap.error("--run-id is required")
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
                 [("ReadFile", {"path": f}) for f in ("models/pricing.py", "tests/test_peak_window_strict.py", "tests/test_peak_window.py")],
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
        model = StrictScriptedChatModel(script=script(a.kind, a.task))
    r = run_code_task(contract_path=contract_path, run_id=a.run_id, runs_dir=ROOT / "runs", cfg=cfg, models={"coder": model}, echo=False)
    out = {k: r.get(k) for k in ("status", "stop_reason", "blocked_reason", "attempts", "usd_billed", "llm_calls", "tools", "budget_profile")}
    if a.kind == "admission":
        events = [json.loads(line) for line in (ROOT / "runs" / a.run_id / "events.jsonl").read_text().splitlines()]
        per = {}
        for e in events:
            if e["event"] == "llm_call" and e["status"] == "ok":
                per[e["iteration"]] = per.get(e["iteration"], 0.0) + (e.get("usd") or 0.0)
        out["usd_per_attempt"] = {str(k): round(v, 6) for k, v in sorted(per.items())}
        out["effective_limits_of_this_run"] = limits(a.task, a.config)[0]
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if r["status"] == "DONE" or a.kind != "happy" else 1


if __name__ == "__main__":
    sys.exit(main())
