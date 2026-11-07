"""drafter.red_question (pilots 021 t1 and prompt_injection_v0 V4, 2026-11-06): before a passing draft is accepted, the
drafter is shown why each required test fails now and asked once whether each is the behaviour the issue asks for; a
test failing on its own data can be revised. One question, shared with the scope question of SPEC_DRAFT_CALL_PATH."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_drafter as td  # noqa: E402
from test_draft_call_path import QUESTION, framed  # noqa: E402
from test_drafter import root  # noqa: E402,F401  (the fixture)

from codetask import drafter as dt  # noqa: E402

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="the path jail and flock need posix; the VM runs these")

V4 = "this test needs a CSV body of at least 1000 bytes, got 647"


def ON(**drafter):
    """test_drafter.cfg turns the question off for the older scripts; here it is on, as in config.yaml."""
    return td.cfg(red_question=True, **drafter)


def red_of(message):
    """fake_red with the given first message line: the red check's record as the drafter's question shows it."""
    def red(nodes, workspace, sandbox_cfg, **kw):
        out, extra = td.fake_red(nodes, workspace, sandbox_cfg, **kw)
        return {n: {**r, "message": message} for n, r in out.items()}, extra
    return red


def asked(d):
    return [e for e in td.events(d) if e["event"] == "draft_submitted" and e.get("red_question")]


def test_the_red_reasons_are_asked_once_then_the_same_draft_is_accepted(root, tmp_path):  # noqa: F811
    r, model, d = td.run(root, tmp_path, [td.SUBMIT, td.call("ReviseDraft", {}, "v1")], red=red_of(V4), config=ON())
    q = td.tool_texts(model, 1)[0]
    assert q.startswith(QUESTION) and V4 in q and "condition of its own" in q
    assert r["status"] == dt.DRAFTED and len(asked(d)) == 1
    assert json.loads((d / "result.json").read_text())["drafting"]["submits"] == 2


def test_every_required_test_is_listed_with_its_reason(root, tmp_path):  # noqa: F811
    r, model, d = td.run(root, tmp_path, [td.SUBMIT, td.call("ReviseDraft", {}, "v1")], red=red_of(V4), config=ON())
    draft = json.loads((d / "draft.json").read_text())
    required = [n for v in draft["contract"]["validation"] for n in v["must_pass"]
                if n.split("::", 1)[0] in {t["path"] for t in draft["new_tests"]}]
    q = td.tool_texts(model, 1)[0]
    assert required and all(f"- {n}: builtins.AssertionError" in q for n in required)
    assert asked(d)[0]["red_question"] == q.count(V4)


def test_a_draft_revised_after_the_question_is_checked_and_accepted(root, tmp_path):  # noqa: F811
    other = {"unverifiable": ["the CSV reads well in the importer"]}
    r, model, d = td.run(root, tmp_path, [td.SUBMIT, td.call("ReviseDraft", other, "v1")], red=red_of(V4), config=ON())
    assert r["status"] == dt.DRAFTED and len(asked(d)) == 1
    assert json.loads((d / "draft.json").read_text())["unverifiable"] == other["unverifiable"]


def test_with_red_question_off_a_passing_draft_is_accepted_at_once(root, tmp_path):  # noqa: F811
    r, model, d = td.run(root, tmp_path, [td.SUBMIT], red=red_of(V4), config=td.cfg(red_question=False))
    assert r["status"] == dt.DRAFTED and asked(d) == [] and len(model.calls) == 1


def test_no_question_on_the_last_submit(root, tmp_path):  # noqa: F811
    r, model, d = td.run(root, tmp_path, [td.SUBMIT], red=red_of(V4), config=ON(max_submits=1))
    assert r["status"] == dt.DRAFTED and asked(d) == [] and len(model.calls) == 1


def test_the_scope_and_the_red_reasons_share_one_question(root, tmp_path):  # noqa: F811
    r, model, d = td.run(root, tmp_path, [td.SUBMIT, td.call("ReviseDraft", {}, "v1")], validate=framed(),
                         red=red_of(V4), config=ON())
    q = td.tool_texts(model, 1)[0]
    assert V4 in q and "src/money.py:3 (in helper)" in q and q.count(QUESTION) == 1
    ev = [e for e in td.events(d) if e["event"] == "draft_submitted" and e.get("scope_question")]
    assert len(ev) == 1 and ev[0].get("red_question") and r["status"] == dt.DRAFTED


def test_config_yaml_turns_it_on():
    from runner import load_config
    assert load_config()["drafter"]["red_question"] is True


def test_a_required_test_the_red_check_did_not_record_is_rejected_before_any_question(root, tmp_path):  # noqa: F811
    """Review note: a test missing from the red check is never left out of the question silently, because such a draft
    does not pass its check (the harness rejects it first)."""
    def partial(nodes, workspace, sandbox_cfg, **kw):
        out, extra = red_of(V4)(nodes, workspace, sandbox_cfg, **kw)
        return {n: r for i, (n, r) in enumerate(sorted(out.items())) if i > 0}, extra
    r, model, d = td.run(root, tmp_path, [td.SUBMIT], red=partial, config=ON())
    assert asked(d) == [] and td.tool_texts(model, 1)[0].startswith("Draft rejected")


def test_the_policy_records_the_setting(root, tmp_path):  # noqa: F811
    r, model, d = td.run(root, tmp_path, [td.SUBMIT, td.call("ReviseDraft", {}, "v1")], config=ON())
    assert [e["red_question"] for e in td.events(d) if e["event"] == "drafter_policy"] == [True]


def test_a_held_draft_is_accepted_when_the_red_question_is_never_answered(root, tmp_path):  # noqa: F811
    r, model, d = td.run(root, tmp_path, [td.SUBMIT] + [td.READ] * 5, red=red_of(V4), config=ON(max_steps=4))
    assert r["status"] == dt.DRAFTED and V4 in td.tool_texts(model, 1)[0]
    assert [e["after"] for e in td.events(d) if e["event"] == "held_draft_accepted"] == ["max_steps"]
