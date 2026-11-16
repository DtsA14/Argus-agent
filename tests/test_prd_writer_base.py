"""SPEC_PRD_WRITER PR 1: what the PRD writer needs from the code that already exists, with no change for the jobs that
exist. (1) touches_problems takes `known` (names an earlier item creates) and `strict`; (2) the writer's settings and
preflight read a named config section; (3) router/job.py knows the kind "prd": its own legal moves, resume, status,
abandon. Nothing here calls a model."""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from codetask import issue_writer as iw  # noqa: E402
from router import issue as ri  # noqa: E402
from router import job as rj  # noqa: E402
from router import prd_job as pj  # noqa: E402
from runner import load_config  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def snap(tmp_path, extra_files=()):
    root = tmp_path / "snap"
    (root / "src").mkdir(parents=True)
    (root / "src" / "page.js").write_text("const H = ['stage', 'share']\n")
    for name in extra_files:
        (root / name).write_text("x\n")
    return root


def problems(root, touches, **kw):
    return iw.touches_problems({"touches": touches}, root, **kw)[0]


# ---- 1. known and strict ---------------------------------------------------------------------------------------

def test_a_touch_found_nowhere_is_refused_as_before(tmp_path):
    p = problems(snap(tmp_path), ["compute_time_stop_status"])
    assert len(p) == 1 and "occurs in no file" in p[0]


def test_a_touch_an_earlier_item_creates_is_accepted(tmp_path):
    assert problems(snap(tmp_path), ["compute_time_stop_status"], known=frozenset({"compute_time_stop_status"})) == []


def test_known_is_matched_exactly_after_strip_never_as_a_substring(tmp_path):
    root = snap(tmp_path)
    assert problems(root, ["compute_time_stop"], known=frozenset({"compute_time_stop_status"}))
    assert problems(root, ["  compute_time_stop_status  "], known=frozenset({"compute_time_stop_status"})) == []


def test_known_is_stripped_like_the_touch_and_a_string_is_refused(tmp_path):
    root = snap(tmp_path)
    assert problems(root, ["a_new_name"], known=frozenset({"  a_new_name  "})) == []
    with pytest.raises(TypeError):
        problems(root, ["a_new_name"], known="a_new_name")


def test_only_the_known_touch_is_excused_when_there_are_two(tmp_path):
    p = problems(snap(tmp_path), ["compute_time_stop_status", "no_such_text"], known=frozenset({"compute_time_stop_status"}))
    assert len(p) == 1 and "'no_such_text'" in p[0]


def test_every_touch_may_come_from_known_but_the_list_may_not_be_empty(tmp_path):
    root = snap(tmp_path)
    assert problems(root, ["a_new_name"], known=frozenset({"a_new_name"})) == []
    assert "touches must list 1 to" in problems(root, [], known=frozenset({"a_new_name"}))[0]


def test_an_unread_file_still_lets_a_missing_touch_pass_by_default(tmp_path, monkeypatch):
    root = snap(tmp_path)
    monkeypatch.setattr(iw, "SEARCH_MAX_FILE", 10)                    # page.js (36 bytes) is now unread
    assert problems(root, ["no_such_text"]) == []


def test_strict_refuses_a_missing_touch_even_with_an_unread_file(tmp_path, monkeypatch):
    root = snap(tmp_path)
    monkeypatch.setattr(iw, "SEARCH_MAX_FILE", 10)
    p = problems(root, ["no_such_text"], strict=True)
    assert len(p) == 1 and "was not found, and 1 file(s) went unread" in p[0]
    monkeypatch.undo()                                      # nothing unread: the plain message
    assert "occurs in no file" in problems(snap(tmp_path / "other"), ["no_such_text"], strict=True)[0]
    assert problems(root, ["no_such_text"], strict=True, known=frozenset({"no_such_text"})) == []


def test_strict_changes_nothing_when_the_touch_exists(tmp_path):
    assert problems(snap(tmp_path), ["'share'"], strict=True) == []


def test_the_issue_gate_passes_neither_known_nor_strict(tmp_path, monkeypatch):
    seen = {}
    real = iw.touches_problems
    monkeypatch.setattr(iw, "touches_problems", lambda *a, **k: seen.update(a=a, k=k) or real(*a, **k))
    iw.issue_gate({"reply": "ok", "issue": "x", "touches": ["'share'"]}, source=snap(tmp_path), environment="env")
    assert seen.get("k", {}) == {} and len(seen.get("a", ())) == 2 or not seen


def test_the_issue_gate_is_unchanged_by_the_new_parameters(tmp_path):
    import inspect
    assert inspect.signature(iw.touches_problems).parameters["known"].default == frozenset()
    assert inspect.signature(iw.touches_problems).parameters["strict"].default is False


# ---- 2. the config section -------------------------------------------------------------------------------------

def cfg_with_prd():
    cfg = load_config(str(ROOT / "config.yaml"))
    cfg["prd_writer"] = copy.deepcopy(cfg["issue_writer"])
    cfg["prd_writer"]["turn"]["cap_usd"] = 0.25
    cfg["prd_writer"]["max_usd"] = 1.5
    return cfg


def test_settings_read_the_named_section():
    cfg = cfg_with_prd()
    assert iw.settings(cfg)["attempt_usd"] == pytest.approx(0.1)
    assert iw.settings(cfg, "prd_writer")["attempt_usd"] == pytest.approx(0.25)
    assert iw.settings(cfg, section="issue_writer")["attempt_usd"] == pytest.approx(0.1)


def test_settings_without_the_section_fail():
    cfg = load_config(str(ROOT / "config.yaml"))
    with pytest.raises(KeyError):
        iw.settings(cfg, "prd_writer")


def test_the_job_settings_name_the_missing_section():
    cfg = load_config(str(ROOT / "config.yaml"))
    assert ri._settings(cfg)["role"] == cfg["issue_writer"]["role"]
    with pytest.raises(rj.Refused, match="no prd_writer section"):
        ri._settings(cfg, "prd_writer")


def test_the_preflight_checks_the_named_section():
    cfg = cfg_with_prd()
    ri._preflight(cfg, 1.5, "prd_writer")                              # a whole turn ($0.25) fits $1.50
    with pytest.raises(rj.Refused, match=r"does not fund one turn \(\$0\.25\)"):
        ri._preflight(cfg, 0.2, "prd_writer")
    ri._preflight(cfg, 0.2)                                            # the issue writer's turn is $0.10: unchanged
    cfg["prd_writer"]["role"] = "nobody"
    with pytest.raises(rj.Refused, match="prd_writer.role 'nobody' is not in the config"):
        ri._preflight(cfg, 1.5, "prd_writer")


def test_run_writer_takes_the_section_in_its_signature():
    import inspect
    assert inspect.signature(iw.run_writer).parameters["section"].default == "issue_writer"


# ---- 3. the kind "prd" in router/job.py ------------------------------------------------------------------------

def make_job(tmp_path, kind="prd", state=pj.AWAITING_HUMAN):
    job = rj.Job(tmp_path / "jobs" / "jp")
    job.dir.mkdir(parents=True)
    job.data = {"job": "jp", "kind": kind, "state": state, "created_at": "2026-11-16T00:00:00Z", "max_usd": 1.5,
                "inputs": {"repo": "/x", "repo_name": "demo", "commit": "a" * 40, "environment": "env"},
                "conversation": [], "stages": {}, "log": []}
    job.save()
    return job


def deps():
    return rj.Deps(confirm=lambda t: True, get_key=lambda: "k", isatty=lambda: True, models={},
                   clock=lambda: "2026-11-16T00:00:00Z", echo=lambda *_: None)


def test_the_legal_moves_of_the_kind_are_its_own():
    assert (pj.AWAITING_HUMAN, pj.WRITING) in pj.LEGAL and (pj.WRITE_FAILED, pj.WRITING) in pj.LEGAL
    assert pj.LEGAL == ri.LEGAL - {(ri.AWAITING_HUMAN, ri.HANDED_OFF)}      # the issue table, minus the hand-off
    assert pj.LEGAL == {("NEW", "WRITING"), ("NEW", "BLOCKED"), ("WRITING", "AWAITING_HUMAN"),
                        ("WRITING", "WRITE_FAILED"), ("WRITING", "BLOCKED"), ("AWAITING_HUMAN", "WRITING"),
                        ("WRITE_FAILED", "WRITING")} | {(s, "ABANDONED") for s in
                                                        ("NEW", "WRITING", "AWAITING_HUMAN", "WRITE_FAILED", "BLOCKED")}
    assert ("BLOCKED", "WRITING") not in pj.LEGAL and ("ABANDONED", "WRITING") not in pj.LEGAL


def test_move_uses_the_prd_table_for_kind_prd(tmp_path):
    job = make_job(tmp_path)
    with pytest.raises(rj.Refused):
        job.move(ri.HANDED_OFF, deps())                     # legal for an issue job, never for a PRD job
    assert job.data["state"] == pj.AWAITING_HUMAN
    job.move(pj.WRITING, deps())
    assert job.data["state"] == pj.WRITING


def test_the_same_move_is_still_legal_for_an_issue_job(tmp_path):
    job = make_job(tmp_path, kind="issue")
    job.move(ri.HANDED_OFF, deps())
    assert job.data["state"] == ri.HANDED_OFF


def test_a_prd_job_can_be_abandoned_from_every_open_state(tmp_path):
    for state in (pj.NEW, pj.WRITING, pj.AWAITING_HUMAN, pj.WRITE_FAILED, pj.BLOCKED):
        job = make_job(tmp_path / state, state=state)
        rj.abandon("jp", "no longer wanted", deps=deps(), jobs_dir=job.dir.parent)
        assert rj.open_job("jp", job.dir.parent).data["state"] == pj.ABANDONED
    done = make_job(tmp_path / "done", state=pj.ABANDONED)
    with pytest.raises(rj.Refused, match="nothing to abandon"):
        rj.abandon("jp", "again", deps=deps(), jobs_dir=done.dir.parent)


def test_resume_of_a_prd_job_goes_to_its_own_module(tmp_path, monkeypatch):
    job = make_job(tmp_path, state=pj.WRITING)
    seen = []
    monkeypatch.setattr(pj, "resume", lambda j, cfg, d: seen.append(j.id) or j)
    rj.resume("jp", cfg={}, deps=deps(), jobs_dir=job.dir.parent)
    assert seen == ["jp"]


def test_resume_of_a_prd_job_says_the_turn_is_not_built_yet(tmp_path):
    job = make_job(tmp_path, state=pj.WRITING)
    with pytest.raises(rj.Refused, match="not built yet"):
        rj.resume("jp", cfg={}, deps=deps(), jobs_dir=job.dir.parent)


def test_status_of_a_prd_job_says_prd_and_shows_the_money(tmp_path):
    job = make_job(tmp_path)
    job.data["stages"] = {"w1": {"kind": "write", "run_id": "jp-w1", "status": "WRITTEN", "cap_usd": 0.25, "usd": 0.0421}}
    job.save()
    text = rj.status("jp", jobs_dir=job.dir.parent)
    assert "  w1 write: WRITTEN cap $0.2500 spent $0.0421" in text
    assert "job jp: AWAITING_HUMAN (prd)" in text and "money: cap $1.50" in text
    assert "repository demo at " + "a" * 12 in text
    assert "(issue)" not in text


def test_run_writer_reads_its_role_and_limits_from_the_named_section(tmp_path):
    """No issue_writer section at all: the turn is funded and refused (cap 0: no model is called) from prd_writer."""
    cfg = cfg_with_prd()
    cfg["prd_writer"]["turn"]["cap_usd"] = 0.0
    del cfg["issue_writer"]
    r = iw.run_writer(run_id="rw1", runs_dir=tmp_path / "runs", cfg=cfg, section="prd_writer",
                      inputs={"repo": "demo", "commit": "a" * 40, "environment": "env", "conversation": []},
                      prepare=lambda run_dir: tmp_path)
    assert r["status"] == iw.FAILED_BUDGET
    with pytest.raises(KeyError):
        iw.run_writer(run_id="rw2", runs_dir=tmp_path / "runs", cfg=cfg, inputs={}, prepare=lambda d: tmp_path)


def test_the_preflight_checks_the_limits_of_the_named_section():
    """A prd_writer whose input limit the model cannot take is refused; the issue writer's own section is not asked."""
    cfg = cfg_with_prd()
    cfg["prd_writer"]["turn"]["max_input_tokens"] = 10 ** 9
    with pytest.raises(rj.Refused, match=r"prd writer \(role .*prd_writer\.turn.*nothing was started"):
        ri._preflight(cfg, 1.5, "prd_writer")
    ri._preflight(cfg, 1.5)                                            # the issue writer's section is untouched


def test_an_unpriced_model_is_refused_under_the_name_of_its_section():
    cfg = cfg_with_prd()
    cfg["roles"]["prd_role"] = {**cfg["roles"]["issue_writer"], "model": "openrouter:anthropic/model-nobody-priced"}
    cfg["prd_writer"]["role"] = "prd_role"
    with pytest.raises(rj.Refused, match=r"prd writer \(role 'prd_role'\)") as e:
        ri._preflight(cfg, 1.5, "prd_writer")
    assert "issue writer" not in str(e.value)                  # not even inside the pricing check's own words
    cfg["issue_writer"]["role"] = "prd_role"
    with pytest.raises(rj.Refused, match=r"issue writer \(role 'prd_role'\)"):
        ri._preflight(cfg, 1.5)
