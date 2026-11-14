#!/usr/bin/env python3
"""Runner of the frozen synthetic RC/GATE cases (pilots/synthetic_rc_gate/PROTOCOL.md section 6, step 4). No model of Argus is called (a scripted agent
writes the files of a case's workspace/ with WriteFile, then calls Finish or ReportConflict); the validations and the red check run in the real
Docker sandbox, through codetask.run.run_code_task, so the decision order of the acceptance node is the real one.

It refuses to run unless the git tree sha of cases/ is the one sealed in FROZEN.md. It never edits a case. A mismatch between `expect` and the
outcome is reported as MISMATCH with the case; classifying it (an error of the code, or a spec gap) is a human decision.

Usage (from the repository root, with ARGUS_SANDBOX_IMAGE and ARGUS_SANDBOX_IMAGE_ARGUS set):
    .venv-verify/bin/python pilots/synthetic_rc_gate/run.py [--only RC-01,GATE-03] [--out DIR]
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from acceptance import contract as ct  # noqa: E402
from codetask import status as st  # noqa: E402
from codetask.run import run_code_task  # noqa: E402
from models.fake import StrictScriptedChatModel, reply  # noqa: E402
from runner import load_config  # noqa: E402
from tools import sandbox as sb  # noqa: E402

CASES = HERE / "cases"
SPARE_FINISHES = 3          # replies the scripted agent has left if the harness gives it another attempt


def bypass_the_tools_scope_guard():
    """RUNNER ADAPTATION (declared; found by the first full run, which was discarded): the agent's own WriteFile refuses a path that is protected or
    outside the writable scope (codetask/tools.py _writable), so a case whose final workspace differs from the input in a test file, a conftest or
    any other protected path could never reach the acceptance node: the agent could not make that change. What the cases test is the HARNESS's
    check of a final workspace (the diff against the intake, the scope criteria, the conflict verification), which exists exactly because other code
    (the agent's production code run by the validations) could write elsewhere. So the scripted agent here writes through a guard that only keeps the
    path jail and the SUMMARY.json rule; everything the harness decides afterwards is the real one."""
    from codetask import tools as tl
    cls = next(c for c in vars(tl).values() if isinstance(c, type) and "_writable" in vars(c))
    orig = cls._writable

    def writable(self, path, tool):
        norm = "/".join(self.jail.parts(path))
        if norm == tl.SUMMARY:
            return None, f"Rejected: {tl.SUMMARY} is written by Finish, not {tool}."
        return norm, None
    cls._writable = writable
    return cls, orig


def call(name, args, i):
    return reply(tool_calls=[{"name": name, "args": args, "id": i}], input_tokens=500, output_tokens=60)


def seal_ok():
    """True when the tree sha of cases/ is the sealed one (FROZEN.md)."""
    want = re.search(r"`([0-9a-f]{40})`", (HERE / "FROZEN.md").read_text(encoding="utf-8")).group(1)
    got = subprocess.run(["git", "rev-parse", "HEAD:pilots/synthetic_rc_gate/cases"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "--", "pilots/synthetic_rc_gate/cases"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    return want == got and not dirty, want, got, dirty


def copy_tree(src, dst):
    for f in sorted(p for p in Path(src).rglob("*") if p.is_file()):
        t = Path(dst) / f.relative_to(src)
        t.parent.mkdir(parents=True, exist_ok=True)
        t.write_bytes(f.read_bytes())


def run_case(d, cfg, work):
    case = json.loads((d / "case.json").read_text(encoding="utf-8"))
    name = re.sub(r"[^a-z0-9_]", "_", case["id"].lower())
    root = Path(work) / "root"
    copy_tree(d / "input", root / "fixtures" / "repos" / name)
    shim = root / "fixtures" / "repos" / name / "conftest.py"
    if not shim.exists():
        # RUNNER SHIM (declared, applied to every case that has no root conftest.py): the sandbox runs `python3 -I -m pytest`, which puts the
        # test file's directory, not the repository root, on sys.path; every fixture repo of the project has an empty root conftest.py for
        # that. The cases were written without being told this. The case files are not edited: the shim exists only in the working copy,
        # in the input, never in a case's workspace (so the agent never "changes" it).
        shim.write_text("", encoding="utf-8")
    contract = {"contract": name, "version": 1, "inputs": {"workspace": f"fixtures/repos/{name}", "issue": case["what"]},
                "scope": case["contract"]["scope"], "artifacts": [{"path": "SUMMARY.json", "type": "json", "schema": "claims_v2"}],
                "validation": [{**v, "environment": v.get("environment") or "argus"} for v in case["contract"]["validation"]],
                "judge": [], "limits": {"max_usd": 1.0, "max_iterations": 3}}
    problems = ct.validate(contract)
    if problems:
        return {"id": case["id"], "outcome": "INVALID_CONTRACT", "problems": problems}
    path = Path(work) / "contract.json"
    path.write_text(json.dumps(contract), encoding="utf-8")
    script, n = [], 0
    for f in sorted(p for p in (d / "workspace").rglob("*") if p.is_file()):
        rel = f.relative_to(d / "workspace").as_posix()
        if rel == "SUMMARY.json":
            continue
        n += 1
        script.append(call("WriteFile", {"path": rel, "content": f.read_text(encoding="utf-8")}, f"w{n}"))
    ag = case["agent"]
    script.append(call("ReportConflict", {"files": ag["files"]}, "c1") if ag["end"] == "conflict_reported"
                  else call("Finish", {"claims": [], "summary": "done"}, "f1"))
    script += [call("Finish", {"claims": [], "summary": "done"}, f"s{i}") for i in range(SPARE_FINISHES)]
    model = StrictScriptedChatModel(script=script)
    t0 = time.time()
    r = run_code_task(contract_path=path, run_id=name, runs_dir=Path(work) / "runs", cfg=cfg, models={"coder": model},
                      preflight=lambda: (True, "ok"), env_preflight=lambda e: (True, "ok"), root=root)
    run_dir = Path(work) / "runs" / name
    v0 = json.loads((run_dir / "verdict_0.json").read_text(encoding="utf-8")) if (run_dir / "verdict_0.json").exists() else {}
    crit = {c["id"]: c["status"] for c in v0.get("criteria", [])}
    detail = {c["id"]: {"reason": c.get("reason"), "evidence": {k: v for k, v in (c.get("evidence") or {}).items() if k != "output_tail"},
                        "output_tail": str((c.get("evidence") or {}).get("output_tail", ""))[-600:]}
              for c in v0.get("criteria", []) if c["status"] != "pass"}
    out = {"id": case["id"], "status": r.get("status"), "blocked_reason": r.get("blocked_reason"), "stop_reason": r.get("stop_reason"),
           "attempts": r.get("attempts"), "model_calls": len(model.calls), "shim_conftest": not (d / "input" / "conftest.py").exists(),
           "criteria": crit, "failed_detail": detail, "conflict": v0.get("conflict"),
           "seconds": round(time.time() - t0, 1), "expect": case["expect"]}
    ex = case["expect"]
    if case["id"].startswith("RC-"):
        actual = ("confirmed" if r.get("status") == st.BLOCKED and r.get("blocked_reason") == "test_conflict"
                  else "blocked" if r.get("status") == st.BLOCKED else "unconfirmed")
        out["actual"] = {"decision": actual}
        out["match"] = actual == ex["decision"]
    else:
        hit = crit.get("scope:no_test_detection", "pass") != "pass"
        terminal = r.get("status") == st.FAILED_ACCEPTANCE and str(r.get("stop_reason", "")).startswith("test_detection")
        out["actual"] = {"detection": "hit" if hit else "clean", "terminal": terminal}
        out["match"] = out["actual"]["detection"] == ex["detection"] and terminal == ex["terminal"]
    out["outcome"] = "MATCH" if out["match"] else "MISMATCH"
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--out", default=str(HERE / "results"))
    a = ap.parse_args()
    ok, want, got, dirty = seal_ok()
    if not ok:
        print(f"REFUSED: the cases are not the sealed ones (sealed {want}, now {got}, uncommitted: {dirty or 'none'})")
        return 2
    bypass_the_tools_scope_guard()
    cfg = load_config()
    cfg["roles"]["coder"]["model"] = "fake:scripted"
    cfg["sandbox"] = {**(cfg.get("sandbox") or {}), "kind": "docker"}
    good, why = sb.status({**cfg["sandbox"], "environment": "argus"})
    if not good:
        print(f"REFUSED: the sandbox is not available: {why}")
        return 2
    only = {x for x in a.only.split(",") if x}
    cases = sorted(p for p in CASES.iterdir() if p.is_dir() and (not only or p.name in only))
    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for d in cases:
        with tempfile.TemporaryDirectory(prefix="rcgate_") as work:
            try:
                res = run_case(d, cfg, work)
            except Exception as e:      # a crash is a result, not a reason to stop the other cases
                res = {"id": d.name, "outcome": "CRASH", "error": f"{type(e).__name__}: {str(e)[:300]}"}
        results.append(res)
        extra = res.get("actual") or res.get("error") or res.get("problems")
        print(f"{res['outcome']:16} {res['id']:8} expect={res.get('expect')} actual={extra}", flush=True)
        (out_dir / "results.json").write_text(json.dumps({"sealed_tree": want, "results": results}, indent=1, default=str), encoding="utf-8")
    n = len(results)
    cnt = {k: sum(1 for r in results if r["outcome"] == k) for k in ("MATCH", "MISMATCH", "INVALID_CONTRACT", "CRASH")}
    print(f"\n{n} cases: {cnt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
