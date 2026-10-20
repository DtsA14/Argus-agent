"""Rehearsal of M6 pilot 1 with a SCRIPTED model (no money, no provider): the run of the approved task `fix_run_stats`
in the real sandbox, from the contract the approval published, as `scripts/run_code_task.py` would run it.

  PYTHONPATH=. python pilots/m6_pilot1/rehearse.py happy      --run-id rehearsal_happy
  PYTHONPATH=. python pilots/m6_pilot1/rehearse.py negative   --run-id rehearsal_negative

happy:    the agent makes the reference change with EditFile, checks it, and finishes with honest claims.
negative: the agent tries to edit a protected test and a protected file (both refused), changes nothing useful and
          claims success: the run must end FAILED_ACCEPTANCE and there must be no review package.
Run from the repository root of a checkout where the task was approved (fixtures/contracts/fix_run_stats.json) and
the sandbox images exist (.sandbox_image, .sandbox_image_argus). This file is not a test; pytest does not collect it
(conftest.py ignores pilots/).
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from codetask.run import run_code_task  # noqa: E402
from models.fake import StrictScriptedChatModel, reply  # noqa: E402
from runner import load_config  # noqa: E402

IMPORT_OLD = "from acceptance.workspace import diff, snapshot\n"
IMPORT_NEW = IMPORT_OLD + "from harness.events import parse_lines\n"
LINE_OLD = ('    events = [json.loads(l) for l in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines() '
            'if l.strip()]\n')
LINE_NEW = '    events = parse_lines((run_dir / "events.jsonl").read_text(encoding="utf-8"))\n'
CLAIMS = [{"claim": "tests_pass", "evidence": "validation:regression"},
          {"claim": "issue_fixed", "evidence": "validation:target"},
          {"claim": "file_changed", "path": "evals/score.py"}]


def call(name, args, id):
    return reply(tool_calls=[{"name": name, "args": args, "id": id}], input_tokens=900, output_tokens=120)


def script(kind):
    if kind == "happy":
        return [call("ReadFile", {"path": "evals/score.py"}, "r1"),
                call("EditFile", {"path": "evals/score.py", "old_text": IMPORT_OLD, "new_text": IMPORT_NEW}, "e1"),
                call("EditFile", {"path": "evals/score.py", "old_text": LINE_OLD, "new_text": LINE_NEW}, "e2"),
                call("RunValidation", {"id": "target"}, "v1"),
                call("RunValidation", {"id": "regression"}, "v2"),
                call("Finish", {"claims": CLAIMS, "summary": "run_stats now reads events.jsonl with "
                                "harness.events.parse_lines, so a line that is not valid JSON is skipped"}, "f1")]
    lazy = call("Finish", {"claims": CLAIMS, "summary": "fixed"}, "f1")
    return [call("EditFile", {"path": "tests/test_run_stats.py", "old_text": "def test_a_log", "new_text": "def xtest_a_log"}, "b1"),
            call("EditFile", {"path": "harness/events.py", "old_text": "continue", "new_text": "raise"}, "b2"),
            lazy,
            call("Finish", {"claims": CLAIMS, "summary": "fixed again"}, "f2")]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("kind", choices=["happy", "negative"])
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--task", default="fix_run_stats")
    a = ap.parse_args(argv)
    cfg = load_config()
    cfg["roles"]["coder"]["model"] = "fake:scripted"
    cfg["sandbox"] = {**(cfg.get("sandbox") or {}), "kind": "docker"}
    if not os.environ.get("ARGUS_SANDBOX_IMAGE") and (ROOT / ".sandbox_image").exists():
        os.environ["ARGUS_SANDBOX_IMAGE"] = (ROOT / ".sandbox_image").read_text().strip()
    for name in cfg["sandbox"].get("environments") or {}:
        var, path = f"ARGUS_SANDBOX_IMAGE_{name.upper()}", ROOT / f".sandbox_image_{name}"
        if not os.environ.get(var) and path.exists():
            os.environ[var] = path.read_text().strip()
    model = StrictScriptedChatModel(script=script(a.kind))
    r = run_code_task(contract_path=ROOT / "fixtures" / "contracts" / f"{a.task}.json", run_id=a.run_id,
                      runs_dir=ROOT / "runs", cfg=cfg, models={"coder": model}, echo=False)
    print(json.dumps({k: r.get(k) for k in ("status", "stop_reason", "blocked_reason", "attempts", "usd_billed",
                                            "llm_calls", "tools", "budget_profile")}, ensure_ascii=False))
    return 0 if r["status"] == "DONE" else 1


if __name__ == "__main__":
    sys.exit(main())
