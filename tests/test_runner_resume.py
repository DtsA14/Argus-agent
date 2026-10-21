"""runner.py and a line of events.jsonl that was cut by a crash (docs/reviews/INVESTIGATION_RUNNER_RESUME.md).

A process killed while writing an event leaves a line that is not valid JSON; after a resume it stands in the middle of the
file (EventLog restores the newline). runner.py used to read the log with json.loads per line, so the run's final
accounting raised after the graph had finished, no result.json was written, and every further --resume failed the same way.
It now reads the log like everything else (harness.events.parse_lines), reports how many lines it could not decode in
result.json (events_skipped), and never lets a skipped line hide a cost: a call whose final line was cut is still charged at
its worst case by reconcile_ledger (unknown_after_crash)."""
import json
import subprocess
import sys
from pathlib import Path

from runner import actual_spend, ledger_totals, read_event_log

ROOT = Path(__file__).resolve().parent.parent
CUT = '{"ts": 2.5, "event": "llm_ca'                       # what a process killed mid-write leaves behind


def ev(event, **fields):
    return json.dumps({"ts": 1.0, "event": event, **fields})


def write_log(path, lines):
    path.write_text("".join(line + "\n" for line in lines), encoding="utf-8")
    return path


def one_call(cid, usd_nano):
    return [ev("llm_call_started", call_id=cid, worst_tokens=100, worst_usd_nano=usd_nano * 2),
            ev("llm_call", call_id=cid, status="ok", tokens=80, usd_nano=usd_nano)]


LOG = [ev("body_done", node="worker", tokens=5), *one_call("a", 3000), ev("body_done", node="worker", tokens=7),
       *one_call("b", 4000), ev("budget_violation", source="node")]


# ---- the readers --------------------------------------------------------------------------------------------------

def test_a_line_cut_in_the_middle_changes_no_figure(tmp_path):
    clean = write_log(tmp_path / "clean.jsonl", LOG)
    damaged = write_log(tmp_path / "damaged.jsonl", LOG[:4] + [CUT] + LOG[4:])
    (ce, cs), (de, ds) = read_event_log(clean), read_event_log(damaged)
    assert (cs, ds) == (0, 1) and ce == de
    assert actual_spend(de) == actual_spend(ce) == 12
    assert ledger_totals(de) == ledger_totals(ce) and ledger_totals(de)["usd_nano"] == 7000


def test_events_skipped_counts_every_line_that_does_not_decode_wherever_it_is(tmp_path):
    lines = [CUT, ev("body_done", tokens=1), "", CUT, ev("body_done", tokens=2), "   ", CUT]
    events, skipped = read_event_log(write_log(tmp_path / "e.jsonl", lines))
    assert skipped == 3 and [e["tokens"] for e in events] == [1, 2]                     # blank lines are not lines lost
    assert read_event_log(write_log(tmp_path / "m.jsonl", LOG[:2] + [CUT] + LOG[2:]))[1] == 1     # only in the middle
    assert read_event_log(write_log(tmp_path / "ok.jsonl", LOG))[1] == 0


def test_a_cut_final_line_is_never_a_skipped_cost(tmp_path):
    cut_end = '{"ts": 1, "event": "llm_call", "call_id": "a", "status": "ok", "tok'
    events, skipped = read_event_log(write_log(tmp_path / "e.jsonl", [one_call("a", 3000)[0], cut_end]))
    totals = ledger_totals(events)
    assert skipped == 1
    assert (totals["calls"], totals["unknown_after_crash"], totals["usd_nano"]) == (1, 1, 6000)   # the worst case, not 0
    assert totals["usd"] == 6000 / 1e9 and totals["usd_complete"] is True


def test_a_cut_started_line_means_no_request_was_sent_and_nothing_is_charged(tmp_path):
    events, skipped = read_event_log(write_log(tmp_path / "e.jsonl", ['{"ts": 1, "event": "llm_call_star']))
    totals = ledger_totals(events)
    assert skipped == 1 and (totals["calls"], totals["unknown_after_crash"], totals["usd_nano"]) == (0, 0, 0)


# ---- a real run, a real crash, a real resume ----------------------------------------------------------------------

def main_py(tmp_path, name, *flags):
    return subprocess.run([sys.executable, "main.py", "--scenario", "fail_then_pass", "--run-id", "rc", "--runs-dir",
                           str(tmp_path / name), "--quiet", *flags], cwd=ROOT, capture_output=True, text=True, timeout=300)


def crashed(tmp_path, name):
    r = main_py(tmp_path, name, "--crash-at", "evaluator")
    assert r.returncode == 42, r.stderr[-400:]
    assert not (tmp_path / name / "rc" / "result.json").exists()           # it really died mid-run
    return tmp_path / name / "rc"


def result_of(run_dir):
    return json.loads((run_dir / "result.json").read_text(encoding="utf-8"))


FIGURES = ("status", "iteration", "tokens_used", "tokens_spent", "usd_billed", "llm_calls", "llm_calls_unknown",
           "budget_violations")


def test_a_resume_after_a_cut_line_writes_the_same_result_as_one_without(tmp_path):
    control_dir = crashed(tmp_path, "control")
    r = main_py(tmp_path, "control", "--resume")
    assert r.returncode == 0, r.stderr[-400:]
    control = result_of(control_dir)

    run_dir = crashed(tmp_path, "cut")
    with open(run_dir / "events.jsonl", "a", encoding="utf-8") as f:
        f.write(CUT)                                                         # the process died while writing an event
    r = main_py(tmp_path, "cut", "--resume")
    assert r.returncode == 0, r.stderr[-600:]
    result = result_of(run_dir)
    assert {k: result[k] for k in FIGURES} == {k: control[k] for k in FIGURES}
    assert (control["events_skipped"], result["events_skipped"]) == (0, 1)
    lines = (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
    assert CUT in lines and lines.index(CUT) < len(lines) - 1               # in the middle, not the last line
    assert json.loads(lines[-1])["event"] == "run_end"


def test_a_run_whose_graph_finished_but_has_no_result_is_recovered_by_a_plain_resume(tmp_path):
    first = main_py(tmp_path, "stuck")
    assert first.returncode == 0, first.stderr[-400:]
    run_dir = tmp_path / "stuck" / "rc"
    done = result_of(run_dir)
    (run_dir / "result.json").unlink()                                       # what the old code left behind: graph done,
    with open(run_dir / "events.jsonl", "a", encoding="utf-8") as f:         # no result, and a cut line in the log
        f.write(CUT)
    assert not (run_dir / "result.json").exists()
    for attempt in (1, 2):                                                   # and it stays recoverable
        r = main_py(tmp_path, "stuck", "--resume")
        assert r.returncode == 0, (attempt, r.stderr[-600:])
        result = result_of(run_dir)
        assert result["status"] == "DONE" and result["events_skipped"] == 1
        assert {k: result[k] for k in ("iteration", "tokens_used", "usd_billed", "llm_calls")} == \
               {k: done[k] for k in ("iteration", "tokens_used", "usd_billed", "llm_calls")}
        (run_dir / "result.json").unlink()                                   # make the second pass prove it again
