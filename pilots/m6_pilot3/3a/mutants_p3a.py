"""Mutation check for M6 pilot 3a (inspectors only): wrong implementations, each applied on top of the reference patch in its own git worktree
(4 at a time); tests/test_run_report.py must fail for every one. Run from the checkout on the VM (HEAD = reference)."""
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PY = sys.executable
ROOT = Path.cwd()
RL, AU, FT, PR = "evals/runlog.py", "scripts/audit_run.py", "scripts/failure_trace.py", "scripts/pilot_report.py"
BASE = "a0075a9"
PATCH = ROOT / "pilots/m6_pilot3/3a/reference.patch"
TEST = ROOT / "pilots/m6_pilot3/3a/new_test.txt"

M = [
    ("reader_json_loads_per_line", [(RL, "    events = parse_lines(text)\n",
                                     "    events = [json.loads(l) for l in text.splitlines() if l.strip()]\n")]),
    ("reader_tolerates_only_the_last_line", [(RL, "    events = parse_lines(text)\n",
        "    events = [json.loads(l) for l in text.splitlines()[:-1] if l.strip()] + "
        "parse_lines(text.splitlines()[-1] if text.strip() else '')\n")]),
    ("read_result_missing_is_an_empty_dict", [(RL, 'if path.exists() else None', 'if path.exists() else {}')]),
    ("read_memo_leaves_values_encoded", [(RL, "{k: json.loads(v) for k, v in", "{k: v for k, v in")]),
    ("skipped_line_wrong_text", [(RL, 'f"events skipped: {skipped}"', 'f"skipped events: {skipped}"')]),
    ("skipped_is_always_zero", [(RL, "    return events, sum(1 for line in text.splitlines() if line.strip()) - len(events)\n",
                                 "    return events, 0\n")]),
    ("skipped_line_printed_when_zero", [(RL, 'return f"events skipped: {skipped}" if skipped else None',
                                         'return f"events skipped: {skipped}"')]),
    ("skipped_counts_blank_lines", [(RL, "sum(1 for line in text.splitlines() if line.strip()) - len(events)",
                                     "len(text.splitlines()) - len(events)")]),
    # audit_run.py
    ("audit_zero_calls_reads_calls0", [(AU, 'ref = hl.ModelRef.parse(calls[0]["model"]) if calls else None',
                                        'ref = hl.ModelRef.parse(calls[0]["model"])')]),
    ("audit_offers_tools_even_when_none", [(AU, 'if result["tools"] is not None:', "if True:")]),
    ("audit_iterates_without_calls", [(AU, 'range(contract["limits"].get("max_iterations", 5) if calls else 0)',
                                      'range(contract["limits"].get("max_iterations", 5))')]),
    ("audit_drops_the_skipped_line", [(AU, "if runlog.skipped_line(skipped):\n    print(runlog.skipped_line(skipped))\n", "")]),
    ("audit_changes_the_hash_word", [(AU, "'ok' if ok else 'MISMATCH'", "'OK' if ok else 'MISMATCH'")]),
    ("audit_changes_a_truncation", [(AU, "json.dumps(c['args'])[:160]", "json.dumps(c['args'])[:150]")]),
    ("audit_skipped_line_first", [(AU, 'print("effective tools", result["tools"])\n',
                                   'print("effective tools", result["tools"])\nif runlog.skipped_line(runlog.read_events(run_dir)[1]):\n'
                                   '    print(runlog.skipped_line(runlog.read_events(run_dir)[1]))\n')]),
    # failure_trace.py
    ("trace_stops_at_a_missing_result", [(FT, '        print(f"##### {Path(rd).name}: no result.json")\n        continue\n',
                                          '        print(f"##### {Path(rd).name}: no result.json")\n        break\n')]),
    ("trace_changes_the_missing_message", [(FT, ": no result.json", ": no result")]),
    ("trace_changes_the_tools_truncation", [(FT, "[:150]", "[:160]")]),
    ("trace_changes_the_text_truncation", [(FT, "[:400]", "[:300]")]),
    ("trace_drops_the_skipped_line", [(FT, "    if runlog.skipped_line(skipped):\n        print(runlog.skipped_line(skipped))\n", "")]),
    ("trace_header_uses_the_found_dir", [(FT, 'print(f"##### {Path(rd).name}")', 'print(f"##### {run.name}")')]),
    # pilot_report.py
]


def run(item):
    name, edits = item
    wt = ROOT.parent / f"p3mut_{name}"
    subprocess.run(["git", "worktree", "add", "-q", "--detach", str(wt), BASE], cwd=ROOT, check=True)
    try:
        subprocess.run(["git", "apply", str(PATCH)], cwd=wt, check=True)
        shutil.copy(TEST, wt / "tests" / "test_run_inspectors.py")
        shutil.copy(TEST.parent / "new_test_data.py", wt / "tests" / "test_run_inspectors_data.py")
        for f in (".sandbox_image", ".sandbox_image_argus"):
            if (ROOT / f).exists():
                shutil.copy(ROOT / f, wt / f)
        for f, old, new in edits:
            text = (wt / f).read_text(encoding="utf-8")
            assert text.count(old) == 1, f"{name}: {old[:60]!r} found {text.count(old)} times"
            (wt / f).write_text(text.replace(old, new), encoding="utf-8")
        r = subprocess.run([PY, "-m", "pytest", "tests/test_run_inspectors.py", "tests/test_run_inspectors_data.py", "-q", "-p", "no:cacheprovider", "-x"],
                           cwd=wt, capture_output=True, text=True, timeout=900)
        last = [l for l in r.stdout.splitlines() if l.startswith("FAILED")][:1]
        return name, r.returncode == 1, (last[0][:150] if last else r.stdout.strip().splitlines()[-1][:150])
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(wt)], cwd=ROOT)


with ThreadPoolExecutor(4) as pool:
    results = []
    for name, dead, why in pool.map(run, M):
        results.append(dead)
        print(f"{'KILLED  ' if dead else 'SURVIVED'} {name}: {why}", flush=True)
print(f"{sum(results)}/{len(M)} mutants killed")
sys.exit(0 if all(results) else 1)
