"""Check a task draft and, with --approve, publish it as a task (M6 W2a). See acceptance/draft.py.

  python scripts/approve_draft.py --draft d.json --task fix_x --issue-file issue.txt --max-usd 0.5 \\
      --max-iterations 3 --reference-patch ref.patch                    # check only: prints the report
  python scripts/approve_draft.py ... --approve                           # a human approves: publishes the task

The human supplies the task name, the issue, the cost cap, the attempt limit and the reference patch; the draft never
does. Checks run in the Docker sandbox (named environments from .sandbox_image_<name>, as scripts/run_code_task.py).
Exit codes: 0 ok (and published with --approve), 1 a check failed, 2 refused.
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from acceptance import draft as dr  # noqa: E402
from acceptance import intake  # noqa: E402
from runner import load_config  # noqa: E402


def sandbox_cfg(config=None):
    cfg = {**(load_config(config).get("sandbox") or {}), "kind": "docker"}
    if not os.environ.get("ARGUS_SANDBOX_IMAGE") and (ROOT / ".sandbox_image").exists():
        os.environ["ARGUS_SANDBOX_IMAGE"] = (ROOT / ".sandbox_image").read_text().strip()
    for name in cfg.get("environments") or {}:
        var, path = f"ARGUS_SANDBOX_IMAGE_{name.upper()}", ROOT / f".sandbox_image_{name}"
        if not os.environ.get(var) and path.exists():
            os.environ[var] = path.read_text().strip()
    return cfg


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--draft", required=True)
    ap.add_argument("--task", required=True, help="lower-case name of the task to publish")
    ap.add_argument("--issue-file", required=True)
    ap.add_argument("--max-usd", type=float, required=True)
    ap.add_argument("--max-iterations", type=int, required=True)
    ap.add_argument("--reference-patch", required=True,
                    help="the human's solution: a git diff against the intake plus the draft's tests")
    ap.add_argument("--config")
    ap.add_argument("--approve", action="store_true", help="publish the task if every check passes")
    a = ap.parse_args(argv)
    try:
        draft = json.loads(Path(a.draft).read_text(encoding="utf-8"))
        issue = Path(a.issue_file).read_text(encoding="utf-8").strip()
    except (OSError, ValueError) as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    try:
        report = dr.check(draft, task=a.task, issue=issue, max_usd=a.max_usd, max_iterations=a.max_iterations,
                          reference_patch=a.reference_patch, sandbox_cfg=sandbox_cfg(a.config), root=ROOT)
        print(json.dumps({k: v for k, v in report.items() if k != "contract"}, indent=2, ensure_ascii=False))
        if not report["ok"]:
            return 1
        if a.approve:
            record = dr.approve(report, draft, root=ROOT)
            (ROOT / "fixtures" / "intake" / f"{a.task}.report.json").write_text(
                json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"approved: fixtures/contracts/{a.task}.json, fixtures/repos/{a.task} "
                  f"(contract sha256 {record['contract_sha256'][:12]})")
        return 0
    except (dr.DraftError, intake.IntakeError) as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
