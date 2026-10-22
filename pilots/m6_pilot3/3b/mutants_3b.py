"""Mutants of the 3b reference (scripts/pilot_report.py) against tests/test_pilot_report.py. Run on the VM in a worktree of main
that holds the reference and the new test (pilots/m6_pilot3/3b/): every mutant must make a test fail.

  python3 mutants_3b.py <worktree>
"""
import shutil
import subprocess
import sys
from pathlib import Path

WT = Path(sys.argv[1])
PY = str(Path.home() / "Argus-agent/.venv-verify/bin/python")
F = WT / "scripts" / "pilot_report.py"
M = [
    ("unknown cost counted", 'known = [r for r in rows if r["cost_known"]]', 'known = [r for r in rows if r["usd_billed"] is not None]'),
    ("cost per success over every DONE", 'done_known = sum(r["done"] for r in known)', "done_known = len(done)"),
    ("NO_RESULT counted as a failure", "round(len(done) / (total - no_result), 4) if total - no_result else None",
     "round(len(done) / total, 4) if total else None"),
    ("missing minutes are 0", "supervision.get(run_id)", "supervision.get(run_id, 0)", 2),
    ("done is not FAILED_ACCEPTANCE", '"done": result.get("status") == "DONE"', '"done": result.get("status") != "FAILED_ACCEPTANCE"'),
    ("negative minutes accepted", " or v < 0:", ":"),
    ("bool accepted as minutes", "isinstance(v, bool) or ", ""),
    ("NaN accepted", " or not math.isfinite(v)", ""),
    ("unknown run in the supervision file accepted", "if k not in run_ids:", "if False:"),
    ("supervision that is not an object accepted", "if not isinstance(data, dict):", "if False:"),
    ("unreadable supervision file taken as none", '        raise Refused(f"supervision file {path}: {e}")', "        return {}"),
    ("events_skipped from result.json", '"cost_known": cost_is_known(result), "events_skipped": skipped,',
     '"cost_known": cost_is_known(result), "events_skipped": result.get("events_skipped", 0),'),
    ("key order changed", '"usd_billed": result.get("usd_billed"),\n            "cost_known": cost_is_known(result),',
     '"cost_known": cost_is_known(result),\n            "usd_billed": result.get("usd_billed"),'),
    ("median replaced by mean", '"median": statistics.median(attempts_done)', '"median": statistics.mean(attempts_done)'),
    ("success rate rounded to 3", "round(len(done) / (total - no_result), 4)", "round(len(done) / (total - no_result), 3)"),
    ("distribution over DONE runs only", '        if r["status"] != "NO_RESULT":\n            dist', '        if r["done"]:\n            dist'),
    ("refusal printed on stdout", 'print(f"refused: {e}", file=sys.stderr)', 'print(f"refused: {e}")'),
    ("a directory without events.jsonl accepted", ' or not (d / "events.jsonl").is_file()', ""),
    ("cost per success rounded to 4", "round(usd_known / done_known, 6)", "round(usd_known / done_known, 4)"),
    ("supervision mean not rounded", '"mean": round(statistics.mean(minutes), 2) if minutes', '"mean": statistics.mean(minutes) if minutes'),
]
original = F.read_text(encoding="utf-8")
results = []
for m in M:
    name, old, new = m[:3]
    count = m[3] if len(m) > 3 else 1
    assert original.count(old) == count, (name, original.count(old))
    F.write_text(original.replace(old, new), encoding="utf-8")
    r = subprocess.run([PY, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", "tests/test_pilot_report.py"], cwd=WT,
                       capture_output=True, text=True)
    failed = [l for l in r.stdout.splitlines() if l.startswith("FAILED")][:1]
    results.append((name, r.returncode != 0, failed or r.stdout.strip().splitlines()[-1:]))
    print(f"{'KILLED ' if r.returncode != 0 else 'SURVIVED'} {name}: {results[-1][2]}", flush=True)
F.write_text(original, encoding="utf-8")
print(f"RESULT: {sum(k for _, k, _ in results)}/{len(results)} killed")
sys.exit(0 if all(k for _, k, _ in results) else 1)
