"""Zero-cost dry run of the feedback path on the real ledger fixture with the real sandbox: a scripted model that
behaves like the baseline runs (fixes at the 5th call, then runs out before Finish) and, in the next attempt,
finishes only if it is told the harness's checks. Run from the repository root on the VM with PYTHONPATH=.:
python scripts/dry_feedback.py <out_dir>"""
import json
import sys
from pathlib import Path

sys.path.insert(0, "scripts")
import measure_context as mc  # noqa: E402
from langchain_core.messages import AIMessage  # noqa: E402

import harness.llm as hl  # noqa: E402
from codetask.run import run_code_task  # noqa: E402
from codetask.tools import offered  # noqa: E402
from models.fake import CallableChatModel  # noqa: E402
from runner import load_config  # noqa: E402

out = Path(sys.argv[1])
repo = Path("fixtures/repos/ledger")
bug = "src/steps/prepare.py"
fixed = (repo / bug).read_text(encoding="utf-8").replace("merge_options(plan, base)", "merge_options(base, plan)")
steps_dir = sorted(p.as_posix().split("ledger/", 1)[1] for p in (repo / "src" / "steps").glob("*.py")
                   if p.name != "__init__.py")
others = sorted(p.as_posix().split("ledger/", 1)[1] for p in (repo / "src").rglob("*.py")
                if p.name != "__init__.py" and "/steps/" not in p.as_posix())
read = lambda fs: [("ReadFile", {"path": f}) for f in fs]  # noqa: E731
BASELINE_LIKE = [[("ListFiles", {})],
                 read(["tests/test_consistency.py", "src/jobs/cycle.py", "src/core/pipeline.py"]),
                 read(["src/config/pipeline.json", "src/common/options.py", "src/common/settings.py"]),
                 read(steps_dir[:5]),
                 [("WriteFile", {"path": bug, "content": fixed}), ("RunValidation", {"id": "target"}),
                  ("RunValidation", {"id": "unit"})],
                 *[read(others[k:k + 5]) for k in range(0, len(others), 5)]]
FINISH = [("Finish", {"claims": [{"claim": "file_changed", "path": bug},
                                 {"claim": "tests_pass", "evidence": "validation:unit"},
                                 {"claim": "issue_fixed", "evidence": "validation:target"}],
                      "summary": "resolve_terms passed the base terms as the override; fixed earlier."})]

cfg = load_config()
cfg["roles"]["coder"]["model"] = "anthropic:claude-sonnet-5-5"
cfg["sandbox"] = {**(cfg.get("sandbox") or {}), "kind": "docker"}
contract = json.loads(Path("fixtures/contracts/ledger_terms_c.json").read_text(encoding="utf-8"))
allowed = cfg["tools"]["coder"]
seen = []


def respond(messages):
    task = messages[1].content
    step = sum(isinstance(m, AIMessage) for m in messages)
    told = "as the previous attempt left it" in task
    if step == 0:
        seen.append(task)
    plan = [FINISH] if told else BASELINE_LIKE
    calls = [{"name": n, "args": a, "id": f"c{len(seen)}_{step}_{j}"}
             for j, (n, a) in enumerate(plan[min(step, len(plan) - 1)])]
    out_chars = sum(len(json.dumps(c["args"])) + len(c["name"]) for c in calls)
    return AIMessage(content="", tool_calls=calls, usage_metadata={
        "input_tokens": mc.estimate(messages, offered(allowed)), "output_tokens": int(20 + mc.B * out_chars),
        "total_tokens": 0})


hl.provider_counter = lambda model, margin: (mc.estimate, True)
out.mkdir(parents=True, exist_ok=True)
cpath = out / "contract.json"
cpath.write_text(json.dumps(contract), encoding="utf-8")
r = run_code_task(contract_path=cpath, run_id="dry", runs_dir=out, cfg=cfg,
                  models={"coder": CallableChatModel(respond=respond)})
evs = [json.loads(line) for line in (out / "dry" / "events.jsonl").read_text().splitlines()]
print(json.dumps({k: r[k] for k in ("status", "stop_reason", "attempts", "usd_billed", "llm_calls")}))
print("attempt ends:", [e["reason"] for e in evs if e["event"] == "attempt_end"])
print("calls per attempt:", {i: sum(1 for e in evs if e["event"] == "llm_call" and e["status"] == "ok"
                                    and e["iteration"] == i) for i in range(3)})
print("--- attempt 2 task message ---")
print(seen[1] if len(seen) > 1 else "(no second attempt)")
