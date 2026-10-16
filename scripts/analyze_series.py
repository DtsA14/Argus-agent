"""Per-run analysis of a run_series.py series (run from the repository root on the VM with PYTHONPATH=.):
ledger totals, tool calls (search queries, files read), diff against the fixture, claims, and validation re-run
independently in the Docker sandbox on a copy of the final workspace. Prints one JSON line per run."""
import filecmp
import json
import shutil
import sys
import tempfile
from pathlib import Path

from acceptance.validation import run_validation
from runner import load_config

SERIES = Path(sys.argv[1])
REPO = Path("fixtures/repos/ledger")
cfg = load_config()
scfg = {**(cfg.get("sandbox") or {}), "kind": "docker"}


def changed(ws):
    out = []
    for p in sorted(ws.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts and p.name != "SUMMARY.json":
            rel = p.relative_to(ws)
            ref = REPO / rel
            if not ref.exists() or not filecmp.cmp(p, ref, shallow=False):
                out.append(rel.as_posix())
    for p in sorted(REPO.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts and not (ws / p.relative_to(REPO)).exists():
            out.append(f"deleted:{p.relative_to(REPO).as_posix()}")
    return out


series = json.loads((SERIES / "series.json").read_text())
for row in series["runs"]:
    d = SERIES / f"{row['position']:02d}_{row['entry']}"
    run = next(p.parent for p in d.rglob("result.json"))
    res = json.loads((run / "result.json").read_text())
    evs = [json.loads(line) for line in (run / "events.jsonl").read_text().splitlines()]
    calls = [e for e in evs if e["event"] == "llm_call"]
    started = [e for e in evs if e["event"] == "llm_call_started"]
    tools = [(e.get("iteration"), e.get("tool")) for e in evs if e["event"] == "tool_call"]
    ends = [e["reason"] for e in evs if e["event"] == "attempt_end"]
    per_attempt = {}
    for e in calls:
        if e["status"] == "ok":
            per_attempt[e["iteration"]] = per_attempt.get(e["iteration"], 0) + e["tokens"]
    contract = json.loads((run / "contract.json").read_text())
    with tempfile.TemporaryDirectory() as t:
        ws = Path(t) / "ws"
        shutil.copytree(run / "workspace", ws, ignore=shutil.ignore_patterns("__pycache__"))
        fresh = {}
        for spec in contract["validation"]:
            v = run_validation(spec, str(ws), scfg)
            e = v["evidence"]
            fresh[spec["id"]] = {"status": v["status"], "run": e.get("tests_run"), "failures": e.get("failures"),
                                 "errors": e.get("errors"), "skipped": e.get("skipped"),
                                 "must_pass": sorted(set((e.get("must_pass") or {}).values()))}
    summary = json.loads((run / "workspace" / "SUMMARY.json").read_text()) if (run / "workspace" / "SUMMARY.json").exists() else None
    print(json.dumps({
        "entry": row["entry"], "status": res["status"], "stop": res["stop_reason"], "attempts": res["attempts"],
        "attempt_ends": ends, "tools_effective": res["tools"], "usd": res["usd_billed"],
        "llm_started": len(started), "llm_calls": len(calls), "refused": sum(e["status"] == "refused" for e in calls),
        "tokens_per_attempt": per_attempt, "tool_calls": len(tools),
        "searches": sum(t == "search_files" for _, t in tools), "reads": sum(t == "read_file" for _, t in tools),
        "changed": changed(run / "workspace"), "claims": summary and summary.get("claims"),
        "summary": summary and summary.get("summary"), "fresh": fresh}))
