"""Rehearsal of M6 pilot 3a with a SCRIPTED model (no money, no provider): the run of the approved task `fix_run_inspectors` in the
real sandbox, from the contract the approval published, under the pilot's own config (budget.max_usd 0.75), as
`scripts/run_code_task.py --config pilots/m6_pilot3/3a/config_pilot3a.yaml` would run it.

  PYTHONPATH=. python pilots/m6_pilot3/3a/rehearse.py happy     --run-id rehearsal_happy
  PYTHONPATH=. python pilots/m6_pilot3/3a/rehearse.py negative  --run-id rehearsal_negative
  PYTHONPATH=. python pilots/m6_pilot3/3a/rehearse.py admission --run-id rehearsal_admission

happy:     the agent makes the reference change, checks it, and finishes with honest claims: DONE.
negative:  the agent tries to edit a protected test and a protected script (both refused) and claims success: FAILED_ACCEPTANCE.
admission: a PRICED scripted model (claude-sonnet-5-5 prices, the calibrated token counter) spends about what the clean path of the
           token simulation spends (~38k tokens) and then fails its validation. It shows how the cost cap chain (config, contract) and
           the `large` reservation decide how many attempts are admitted, once under the pilot config and once under config.yaml.
Run from the repository root of a checkout where the task was approved (fixtures/contracts/fix_run_inspectors.json) and the sandbox
images exist. Not a test: pytest does not collect it (conftest.py ignores pilots/).
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import harness.llm as hl  # noqa: E402
from codetask import run as ctrun  # noqa: E402
from codetask.run import run_code_task  # noqa: E402
from models.fake import CallableChatModel, StrictScriptedChatModel, reply  # noqa: E402
from runner import load_config  # noqa: E402

HERE = Path(__file__).resolve().parent
PILOT_CONFIG = HERE / "config_pilot3a.yaml"
FILES = ("evals/runlog.py", "scripts/audit_run.py", "scripts/failure_trace.py")
CLAIMS = [{"claim": "tests_pass", "evidence": "validation:regression"},
          {"claim": "issue_fixed", "evidence": "validation:inspectors"}] + [{"claim": "file_changed", "path": f} for f in FILES]


def call(name, args, id, *, tokens=(900, 120)):
    return reply(tool_calls=[{"name": name, "args": args, "id": id}], input_tokens=tokens[0], output_tokens=tokens[1])


def reference_files(task):
    """The three files of the reference patch, applied to a scratch copy of the task repository."""
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "w"
        shutil.copytree(ROOT / "fixtures" / "repos" / task, work)
        subprocess.run(["git", "apply", str(HERE / "reference.patch")], cwd=work, check=True)
        return {f: (work / f).read_text(encoding="utf-8") for f in FILES}


def script(kind, task):
    if kind == "happy":
        ref = reference_files(task)
        return ([call("ReadFile", {"path": "scripts/audit_run.py"}, "r1"), call("ReadFile", {"path": "scripts/failure_trace.py"}, "r2")] +
                [call("WriteFile", {"path": f, "content": ref[f]}, f"w{i}") for i, f in enumerate(FILES)] +
                [call("RunValidation", {"id": "inspectors"}, "v1"), call("RunValidation", {"id": "regression"}, "v2"),
                 call("Finish", {"claims": CLAIMS, "summary": "evals/runlog.py reads a run; audit_run.py and failure_trace.py use it"}, "f1")])
    lazy = call("Finish", {"claims": CLAIMS, "summary": "fixed"}, "f1")
    return [call("EditFile", {"path": "tests/test_run_inspectors.py", "old_text": "def test_a_run_blocked", "new_text": "def xtest_a_run_blocked"}, "b1"),
            call("EditFile", {"path": "harness/events.py", "old_text": "import", "new_text": "import  # no"}, "b2"),
            lazy, call("Finish", {"claims": CLAIMS, "summary": "fixed again"}, "f2")]


def setup_sandbox(cfg):
    cfg["sandbox"] = {**(cfg.get("sandbox") or {}), "kind": "docker"}
    if not os.environ.get("ARGUS_SANDBOX_IMAGE") and (ROOT / ".sandbox_image").exists():
        os.environ["ARGUS_SANDBOX_IMAGE"] = (ROOT / ".sandbox_image").read_text().strip()
    for name in cfg["sandbox"].get("environments") or {}:
        var, path = f"ARGUS_SANDBOX_IMAGE_{name.upper()}", ROOT / f".sandbox_image_{name}"
        if not os.environ.get(var) and path.exists():
            os.environ[var] = path.read_text().strip()


def admission_table(task, config_path):
    """For the real limits chain (config, contract, profile `large`): after k attempts that each spent S, is another admitted?"""
    contract = json.loads((ROOT / "fixtures" / "contracts" / f"{task}.json").read_text(encoding="utf-8"))
    cfg = ctrun.apply_profile(load_config(config_path), contract["budget_profile"])
    cfg["roles"]["coder"]["model"] = "anthropic:claude-sonnet-5-5"
    lim = ctrun.settings(cfg, contract)
    return {"config": str(config_path), "cap_usd": lim["max_usd"], "reservation_usd": round(lim["attempt_usd"], 6),
            "attempt_tokens": lim["attempt_tokens"]}, lim


def admitted(lim, spent):
    return spent + lim["attempt_usd"] <= lim["max_usd"] + 1e-12


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("kind", choices=["happy", "negative", "admission"])
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--task", default="fix_run_inspectors")
    ap.add_argument("--config", default=str(PILOT_CONFIG), help="default: the pilot config; config.yaml shows the stock cap")
    a = ap.parse_args(argv)
    cfg = load_config(a.config)
    setup_sandbox(cfg)
    contract_path = ROOT / "fixtures" / "contracts" / f"{a.task}.json"
    if a.kind == "admission":
        import measure_context as mc
        cfg["roles"]["coder"]["model"] = "anthropic:claude-sonnet-5-5"
        hl.provider_counter = lambda model, margin: (mc.estimate, True)
        # the clean path of the token simulation: five steps, then a Finish the validation does not accept
        steps = [[("ReadFile", {"path": f}) for f in ("scripts/audit_run.py", "scripts/failure_trace.py", "harness/events.py")],
                 [("ReadFile", {"path": "tests/test_run_inspectors.py"})],
                 [("WriteFile", {"path": "evals/runlog.py", "content": "# generated\n" + "def f():\n    return 1\n\n" * 330})],
                 [("RunValidation", {"id": "inspectors"})],
                 [("Finish", {"claims": CLAIMS, "summary": "done"})]]
        from langchain_core.messages import AIMessage
        from codetask.tools import offered
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
    out = {k: r.get(k) for k in ("status", "stop_reason", "blocked_reason", "attempts", "usd_billed", "llm_calls", "tools",
                                 "budget_profile")}
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
            info, lim = admission_table(a.task, path)
            info["attempts_admitted_if_each_spends_like_the_clean_path"] = next(
                (k for k in range(1, 10) if not admitted(lim, spend * (k - 1))), 9) - 1
            table[label] = info
        out["admission"] = table
        out["spend_per_attempt_used_usd"] = round(spend, 6)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if r["status"] == "DONE" or a.kind != "happy" else 1


if __name__ == "__main__":
    sys.exit(main())
