"""M6 pilot 3b: scripts/pilot_report.py, one JSON report over several code-task run directories (pilots/m6_pilot3/3b/SPEC.md).

The runs are the synthetic ones of tests/test_run_inspectors.py (build(): a scripted model, an injected validation; no Docker,
no money) plus copies with result.json changed. Expected reports are written here from the definitions of the issue: statuses,
attempts and calls as literals; each run's usd_billed is read from its own result.json (an input of the report) and every
aggregate is computed below with the issue's formulas, independently of the script."""
import json
import os
import shutil
import statistics
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_run_inspectors import build  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    out = build(ROOT, tmp_path_factory.mktemp("runs") / "b")
    base = out["f1"]
    for name, change in (("f6a", lambda r: r.update(usd_complete=False)),          # a partial cost: a lower bound only
                         ("f6b", lambda r: r.pop("usd_billed")),                     # no cost at all
                         ("f6c", lambda r: r.pop("usd_complete"))):                  # completeness not stated
        d = base.parent / name
        shutil.copytree(base, d)
        r = json.loads((d / "result.json").read_text(encoding="utf-8"))
        change(r)
        (d / "result.json").write_text(json.dumps(r), encoding="utf-8")
        out[name] = d
    return out


def report(*args):
    return subprocess.run([sys.executable, str(ROOT / "scripts" / "pilot_report.py"), *map(str, args)], cwd=ROOT,
                          env={**os.environ, "PYTHONPATH": str(ROOT)}, capture_output=True, text=True, timeout=120)


def usd(run):
    return json.loads((run / "result.json").read_text(encoding="utf-8")).get("usd_billed")


def row(run_id, status, attempts, calls, usd_billed, cost_known, skipped=0, minutes=None):
    return {"run_id": run_id, "status": status, "done": status == "DONE", "attempts": attempts, "llm_calls": calls,
            "usd_billed": usd_billed, "cost_known": cost_known, "events_skipped": skipped, "supervision_minutes": minutes}


def expected(rows):
    """The aggregate of the issue, computed from the rows."""
    known = [r for r in rows if r["cost_known"]]
    no_result = sum(r["status"] == "NO_RESULT" for r in rows)
    done = [r for r in rows if r["done"]]
    total_nano = sum(round(r["usd_billed"] * 1e9) for r in known)
    done_known = sum(r["done"] for r in known)
    att = [r["attempts"] for r in done]
    dist = {}
    for r in rows:
        if r["status"] != "NO_RESULT":
            dist[r["attempts"]] = dist.get(r["attempts"], 0) + 1
    mins = [r["supervision_minutes"] for r in rows if r["supervision_minutes"] is not None]
    return {"runs": rows, "runs_total": len(rows), "done": len(done), "no_result": no_result,
            "success_rate": round(len(done) / (len(rows) - no_result), 4) if len(rows) - no_result else None,
            "usd_known_total": round(total_nano / 1e9, 6), "usd_unknown_runs": len(rows) - len(known),
            "cost_per_success": round(total_nano / 1e9 / done_known, 6) if done_known else None,
            "cost_complete": len(known) == len(rows),
            "attempts": {"mean": round(statistics.mean(att), 3), "median": statistics.median(att)} if att else None,
            "attempts_distribution": {str(k): dist[k] for k in sorted(dist)},
            "supervision": {"runs_with_data": len(mins), "total": sum(mins) if mins else None,
                            "mean": round(statistics.mean(mins), 2) if mins else None},
            "events_skipped": sum(r["events_skipped"] for r in rows)}


def text(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def the_set(runs, minutes=None):
    m = minutes or {}
    return [row("f1", "DONE", 1, 4, usd(runs["f1"]), True, minutes=m.get("f1")),
            row("f2", "DONE", 2, 3, usd(runs["f2"]), True, minutes=m.get("f2")),
            row("f3", "FAILED_ACCEPTANCE", 2, 2, usd(runs["f3"]), True, minutes=m.get("f3")),
            row("f4", "BLOCKED", 0, 0, usd(runs["f4"]), True, minutes=m.get("f4")),
            row("f5c", "DONE", 1, 3, usd(runs["f5c"]), True, skipped=1, minutes=m.get("f5c")),
            row("f6a", "DONE", 1, 4, usd(runs["f6a"]), False, minutes=m.get("f6a")),
            row("f7", "NO_RESULT", None, None, None, False, minutes=m.get("f7"))]


SET = ("f1", "f2", "f3", "f4", "f5c", "f6a", "f7")


# ---- the report, exactly --------------------------------------------------------------------------------------------

def test_the_report_over_seven_kinds_of_run(runs):
    r = report(*(runs[n] for n in SET))
    assert r.returncode == 0, r.stderr[-500:]
    want = expected(the_set(runs))
    assert r.stdout == text(want)
    # the facts the definitions turn on, spelled out
    assert (want["done"], want["no_result"], want["success_rate"], want["usd_unknown_runs"]) == (4, 1, 0.6667, 2)
    assert want["attempts"] == {"mean": 1.25, "median": 1.0} and want["attempts_distribution"] == {"0": 1, "1": 3, "2": 2}
    assert want["cost_complete"] is False and want["events_skipped"] == 1


def test_the_report_with_supervision_minutes(runs, tmp_path):
    minutes = {"f1": 12, "f2": 30.5, "f3": 0, "f4": 5, "f5c": 7, "f6a": 3, "f7": 1}
    sup = tmp_path / "supervision.json"
    sup.write_text(json.dumps(minutes), encoding="utf-8")
    r = report(*(runs[n] for n in SET), "--supervision", sup)
    assert r.returncode == 0, r.stderr[-500:]
    want = expected(the_set(runs, minutes))
    assert r.stdout == text(want)
    assert want["supervision"] == {"runs_with_data": 7, "total": 58.5, "mean": 8.36}


def test_missing_minutes_are_null_and_a_zero_is_data(runs, tmp_path):
    sup = tmp_path / "s.json"
    sup.write_text(json.dumps({"f3": 0, "f2": 2.5}), encoding="utf-8")
    r = report(runs["f1"], runs["f2"], runs["f3"], "--supervision", sup)
    rows = [row("f1", "DONE", 1, 4, usd(runs["f1"]), True),
            row("f2", "DONE", 2, 3, usd(runs["f2"]), True, minutes=2.5),
            row("f3", "FAILED_ACCEPTANCE", 2, 2, usd(runs["f3"]), True, minutes=0)]
    assert r.returncode == 0 and r.stdout == text(expected(rows))
    assert json.loads(r.stdout)["supervision"] == {"runs_with_data": 2, "total": 2.5, "mean": 1.25}


def test_no_run_done(runs):
    r = report(runs["f3"], runs["f4"])
    want = expected([row("f3", "FAILED_ACCEPTANCE", 2, 2, usd(runs["f3"]), True),
                     row("f4", "BLOCKED", 0, 0, usd(runs["f4"]), True)])
    assert r.returncode == 0 and r.stdout == text(want)
    assert want["cost_per_success"] is None and want["attempts"] is None and want["success_rate"] == 0.0


def test_no_cost_known(runs):
    r = report(runs["f6a"], runs["f6b"], runs["f6c"])
    want = expected([row("f6a", "DONE", 1, 4, usd(runs["f6a"]), False),
                     row("f6b", "DONE", 1, 4, None, False),
                     row("f6c", "DONE", 1, 4, usd(runs["f6c"]), False)])
    assert r.returncode == 0 and r.stdout == text(want)
    assert want["usd_known_total"] == 0.0 and want["cost_per_success"] is None and want["cost_complete"] is False
    assert want["runs"][0]["usd_billed"] > 0                                  # shown as it is, never taken as the cost


def test_only_runs_without_a_result(runs):
    r = report(runs["f7"])
    want = expected([row("f7", "NO_RESULT", None, None, None, False)])
    assert r.returncode == 0 and r.stdout == text(want)
    assert want["success_rate"] is None and want["attempts_distribution"] == {}


# ---- refused: exit 2, one line on stderr, nothing on stdout ----------------------------------------------------------

def refused(r, *words):
    lines = r.stderr.strip().splitlines()
    assert r.returncode == 2 and r.stdout == "" and len(lines) == 1, (r.returncode, r.stdout[-300:], r.stderr[-300:])
    assert all(w in lines[0] for w in words), lines[0]


def test_no_run_is_refused():
    refused(report(), "no run directory given")


def test_an_argument_that_is_not_a_run_directory_is_refused(runs, tmp_path):
    missing = tmp_path / "nosuch"
    refused(report(runs["f1"], missing), str(missing), "not a run directory")
    refused(report(runs["wrap"]), str(runs["wrap"]), "not a run directory")          # a directory without events.jsonl
    f = tmp_path / "file.txt"
    f.write_text("x")
    refused(report(f), str(f), "not a run directory")


@pytest.mark.parametrize("content", [
    '{"f1": -1}', '{"f1": "12"}', '{"f1": true}', '[12]', '{"f1": NaN}', '{"nosuch": 3}', '{not json', '12'],
    ids=["negative", "string", "bool", "list", "nan", "unknown_run", "not_json", "number"])
def test_an_invalid_supervision_file_is_refused(runs, tmp_path, content):
    sup = tmp_path / "s.json"
    sup.write_text(content, encoding="utf-8")
    refused(report(runs["f1"], "--supervision", sup), "supervision file", str(sup))


def test_a_missing_supervision_file_is_refused(runs, tmp_path):
    refused(report(runs["f1"], "--supervision", tmp_path / "none.json"), "supervision file", str(tmp_path / "none.json"))
