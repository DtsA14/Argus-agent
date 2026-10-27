"""SPEC_LOCATE_FROM_TRACEBACK (from SWE 21379): the error excerpt keeps the caller frames of each error, the first
attempt of every router agent stage is told the approved draft's red baseline, SearchFiles searches one file, and a
search that stopped at its limit does not say a bare "No matches."."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_agent_context as tac  # noqa: E402
import test_router as tr  # noqa: E402
from test_attempt_usd import counter  # noqa: E402,F401  (the fixture)
from test_router import env  # noqa: E402,F401  (the fixture)

from codetask import agent as ca  # noqa: E402
from codetask import run as ctrun  # noqa: E402
from codetask import status as st  # noqa: E402
from router import job as rj  # noqa: E402

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="the path jail and flock need posix; the VM runs these")

ROOT = Path(__file__).resolve().parent.parent
TAIL_21379 = (ROOT / "fixtures" / "feedback" / "swe_21379_verdict_0_target_tail.txt").read_text(encoding="utf-8")
LIMIT, FRAMES = 1200, 6                       # the spec's bounds, written out (not imported)
LABEL = "The failing validations on the code as it was before any change (from the draft check;"


def frames_tail(n, width=20):
    """n caller frames f0 (outermost) .. f<n-1>, then the error block and pytest's summary, as pytest --tb=short."""
    out = [f"src/m{k}.py:{k + 1}: in f{k}\n    call_{k}{'x' * width}()\n" for k in range(n)]
    return "".join(out) + "src/deep.py:9: in deep\n    raise KeyError(k)\nE   KeyError: 'k'\n" \
        "==== 1 failed in 0.10s ====\n"


# ---- 2.1 the call path in the error excerpt -------------------------------------------------------------------------

def test_the_real_21379_excerpt_shows_where_the_error_was_called_from():
    x = ca.error_excerpt(TAIL_21379)
    assert "sympy/core/mod.py:169: in eval\n    G = gcd(p, q)" in x                   # the line the fix changes
    assert "E   sympy.polys.polyerrors.PolynomialError: Piecewise generators do not make sense" in x
    assert "E   AssertionError: subs raised PolynomialError" in x
    assert x.splitlines()[-1].startswith("=====") and "1 failed" in x.splitlines()[-1]
    assert len(x) <= LIMIT and all(len(line) <= 160 for line in x.splitlines())


def test_the_nearest_six_frames_are_kept_in_order_each_with_its_code_line():
    x = ca.error_excerpt(frames_tail(10))
    kept = [line.split(":")[0] for line in x.splitlines() if line.startswith("src/m")]
    assert kept == [f"src/m{k}.py" for k in range(10 - FRAMES, 10)]
    assert "src/m9.py:10: in f9\n    call_9" in x and "src/deep.py:9: in deep\nE   KeyError: 'k'" in x


def test_frames_that_do_not_fit_go_first_outermost_first_and_never_an_e_line():
    tail = frames_tail(6, width=120)
    x = ca.error_excerpt(tail, limit=500)
    assert "E   KeyError: 'k'" in x and x.splitlines()[-1] == "==== 1 failed in Xs ===="
    kept = [line.split(":")[0] for line in x.splitlines() if line.startswith("src/m")]
    assert kept and kept == [f"src/m{k}.py" for k in range(6 - len(kept), 6)] and len(kept) < 6
    assert len(x) <= 500


def test_a_repeated_error_is_still_shown_once_with_the_frames_of_its_first_block():
    one = "src/a.py:1: in a\n    b()\nsrc/b.py:2: in b\n    raise KeyError(k)\nE   KeyError: 'k'\n"
    two = "src/c.py:3: in c\n    b()\nsrc/b.py:2: in b\n    raise KeyError(k)\nE   KeyError: 'k'\n"
    x = ca.error_excerpt(one + two + "==== 2 failed in 0.10s ====\n")
    assert x.count("E   KeyError") == 1 and "src/a.py:1: in a" in x and "src/c.py" not in x


# ---- 2.2 the approved draft's red baseline in the first attempt of each agent stage --------------------------------

def test_approve_records_the_red_baseline_and_the_first_attempt_is_told_it(env):  # noqa: F811
    env.code()
    job, r = env.approve()
    base = job.data["approval"]["baseline"]
    assert r["status"] == "DONE" and [e["id"] for e in base] == ["validation:target"]
    assert "tests/test_new.py:5: in test_total_never_negative" in base[0]["excerpt"]
    first = tr.first_request(env.coder)
    assert LABEL in first and "test_total_never_negative" in first.split(LABEL)[1]
    assert "regression" not in first.split(LABEL)[1].split("\\n\", \"cache_control")[0]   # green: not shown


def test_a_retry_is_told_the_baseline_and_how_the_last_stage_ended(env, monkeypatch):  # noqa: F811
    tr.failed_a1(env, monkeypatch)
    job, _ = tr.retry(env)
    first = tr.first_request(env.coder)
    assert LABEL in first and "How the previous run of this task ended" in first
    assert first.index(LABEL) < first.index("How the previous run of this task ended")
    assert job.data["stages"]["a2"]["carry"]["carried"] is True                           # the carry is unchanged


def test_a_resumed_stage_is_told_what_was_recorded_at_approve(env, monkeypatch):  # noqa: F811
    env.code()
    real, calls = ctrun.run_code_task, []

    def crash_once(**kw):
        calls.append(kw)
        if len(calls) == 1:
            raise RuntimeError("simulated crash")
        return real(**kw)
    monkeypatch.setattr(ctrun, "run_code_task", crash_once)
    with pytest.raises(RuntimeError):
        env.approve()
    recorded = env.job().data["approval"]["baseline"]
    assert calls[0]["initial_feedback"] == {"baseline": recorded}
    rj.resume("jtest", cfg=env.cfg, deps=env.deps, sandbox_cfg={}, jobs_dir=env.jobs)
    assert calls[1]["initial_feedback"] == calls[0]["initial_feedback"]


def test_a_job_approved_before_the_baseline_was_recorded_is_told_what_it_always_was():
    carry = {"carried": True, "from": "a1", "stopped": {"end": "max_steps", "steps": 12, "wrote": False, "read": []}}
    assert rj.stage_feedback({"draft_sha256": "x"}, {"kind": "agent"}) is None
    assert rj.stage_feedback({"draft_sha256": "x"}, {"carry": carry}) == carry
    assert rj.stage_feedback({"baseline": []}, {"carry": carry}) == carry                   # a green baseline
    contract = json.loads((ROOT / "fixtures" / "contracts" / "fix_divide.json").read_text(encoding="utf-8"))
    assert LABEL not in ca.task_prompt(contract, carry)
    with_base = ca.task_prompt(contract, {**carry, "baseline": [{"id": "validation:t", "excerpt": "E   KeyError"}]})
    assert with_base.replace(f"\n\n{ca.BASELINE_LABEL}\n  validation:t:\n    E   KeyError", "") \
        == ca.task_prompt(contract, carry)


def test_only_failing_validations_with_output_give_a_baseline_at_most_three():
    report = {"baseline": {f"v{k}": {"status": "fail", "output_tail": "src/a.py:1: in a\nE   KeyError: 'k'\n"}
                           for k in range(5)}}
    report["baseline"]["ok"] = {"status": "pass", "output_tail": "src/a.py:1: in a\nE   KeyError: 'k'\n"}
    report["baseline"]["quiet"] = {"status": "fail", "output_tail": "  "}
    assert [e["id"] for e in ca.baseline_errors(report)] == ["validation:v0", "validation:v1", "validation:v2"]
    assert ca.baseline_errors({}) == []


def test_audit_run_rebuilds_a_first_prompt_with_the_baseline(tmp_path, counter):  # noqa: F811
    tac.per_message(counter)
    fb = {"baseline": [{"id": "validation:target", "excerpt": "src/calc.py:3: in divide\nE   ZeroDivisionError"}]}
    model = tac.StrictScriptedChatModel(script=[tac.tau.WRITE, tac.tau.FINISH])
    r, d = tac.go(tmp_path, model, tac.config(20000), initial_feedback=fb)
    assert r["status"] == st.DONE and ca.BASELINE_LABEL in tac.text(model.calls[0])
    assert "prompt_hash checked 2, mismatches 0" in tac.audit(d)


# ---- 2.3, 2.4 SearchFiles -------------------------------------------------------------------------------------------

def test_searchfiles_searches_one_file_and_refuses_a_symlinked_one(tmp_path):
    import test_searchfiles as ts
    root = tmp_path / "ws"
    (root / "src").mkdir(parents=True)
    (root / "src" / "big.py").write_text("a = 1\ndef gcd(p, q):\n    return 1\n")
    (root / "src" / "other.py").write_text("def gcd(p, q):\n")
    (root / "src" / "link.py").symlink_to(root / "src" / "big.py")
    b = ts.box(root, tmp_path)
    assert ts.search(b, "def gcd", "src/big.py").splitlines() == ["src/big.py:2: def gcd(p, q):"]
    assert ts.search(b, "nothing", "src/big.py") == "No matches."
    assert ts.search(b, "def gcd", "src/link.py").startswith("Refused:")
    assert len(ts.search(b, "def gcd", "src").splitlines()) == 2                              # a directory: as before


def test_searchfiles_reports_a_file_too_large_to_search(tmp_path, monkeypatch):
    import test_searchfiles as ts
    from codetask import tools as ct
    root = tmp_path / "ws"
    (root / "src").mkdir(parents=True)
    (root / "src" / "big.py").write_text("x = 1\n" * 50)
    monkeypatch.setattr(ct, "SEARCH_MAX_FILE", 100)
    out = ts.search(ts.box(root, tmp_path), "x = 1", "src/big.py")
    assert out.startswith("No matches.") and "larger than 100 bytes were not searched: src/big.py" in out


def test_a_search_stopped_at_its_limit_says_how_many_files_it_searched(tmp_path, monkeypatch):
    import test_searchfiles as ts
    from codetask import tools as ct
    root = tmp_path / "ws"
    (root / "src").mkdir(parents=True)
    for k in range(3):
        (root / "src" / f"f{k}.py").write_text("x\n")
    monkeypatch.setattr(ct, "SEARCH_MAX_FILES", 2)
    out = ts.search(ts.box(root, tmp_path), "needle").splitlines()
    assert out[0] == "No matches in the 2 files searched." and out[1].startswith("... search stopped after 2 files")


def test_the_searchfiles_version_in_the_step_memo_keys_is_2():
    for path in ("codetask/run.py", "codetask/drafter.py"):
        assert '"SearchFiles": "2"' in (ROOT / path).read_text(encoding="utf-8"), path
