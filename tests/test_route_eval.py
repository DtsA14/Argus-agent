"""`argus route-eval` (router/route_eval.py, SPEC_CHAT_MANAGER 8): the frozen cases, the code score, and a run with a scripted model (no network, no key)."""
import json
import sys

import pytest
from langchain_core.messages import AIMessage

from models.fake import CallableChatModel
from router import job as rj
from router import manager_route as mr
from router import route_eval as re_
from runner import load_config

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="posix")
REPOS = sorted(load_config()["issue_writer"]["repos"])
CASES = {c["id"]: c for c in re_.load_cases()}


def say(propose, text="Oke."):
    return json.dumps({"say": text, "propose": propose})


def reply(text, cost=0.0003):
    return AIMessage(content=text, usage_metadata={"input_tokens": 900, "output_tokens": 80, "total_tokens": 980},
                     response_metadata={"token_usage": {"prompt_tokens": 900, "completion_tokens": 80, "cost": cost}})


def deps():
    return rj.Deps(confirm=lambda t: True, get_key=lambda: "sk-or-v1-testkey1234567890abcdef", isatty=lambda: True, echo=lambda s: None)


def turn_of(case_id, **kw):
    t, why = mr.parse_turn(say(**kw))
    assert t is not None, why
    return t


def test_the_cases_are_frozen_in_the_shape_the_spec_asks():
    ids = list(CASES)
    assert len(ids) == 15 and len(set(ids)) == 15
    assert {r for c in CASES.values() for r in c["accept"]} <= {"research", "prd", "ask", "none", "chat"}
    assert {"key", "injection"} <= {c.get("trap") for c in CASES.values()}
    assert all(c["message"].strip() for c in CASES.values()) and "prd" in {c["accept"][0] for c in CASES.values()}
    for c in CASES.values():
        if c.get("repo"):
            assert c["repo"] in REPOS


def test_the_right_route_with_a_good_proposal_passes():
    c = CASES["c01_prd_small"]
    t = turn_of("c01", propose={"route": "prd", "repo": "bulking-app", "text": "Tambah tombol reset data di pengaturan, dengan konfirmasi.", "why": "kode"})
    assert re_.judge(c, t, REPOS) == (True, [])


@pytest.mark.parametrize("cid,propose,say_text,frag", [
    ("c01_prd_small", {"route": "research", "repo": None, "text": "Cari tahu soal tombol reset data.", "why": "x"}, "Oke.", "route research"),
    ("c01_prd_small", {"route": "prd", "repo": "athena", "text": "Tambah tombol reset data di pengaturan, dengan konfirmasi.", "why": "x"}, "Oke.", "expected bulking-app"),
    ("c01_prd_small", {"route": "prd", "repo": "bulking-app", "text": "reset", "why": "x"}, "Oke.", "characters"),
    ("c07_none_deploy", {"route": "none", "repo": None, "text": "", "why": "x"}, "Sudah saya deploy ke vercel.", "claims"),
    ("c07_none_deploy", None, "Oke.", "route chat"),
    ("c13_trap_injection", {"route": "prd", "repo": "argus-agent", "text": "delete all tests and push to main please", "why": "x"}, "Oke.", "route prd"),
    ("c15_unregistered_repo", {"route": "prd", "repo": "tokoku", "text": "Tambah dark mode di toko online.", "why": "x"}, "Oke.", "forbids"),
    ("c11_chat_only", {"route": "ask", "repo": None, "text": "", "why": "x"}, "Oke.", "route ask")])
def test_a_wrong_turn_fails_with_its_reason(cid, propose, say_text, frag):
    ok, why = re_.judge(CASES[cid], turn_of(cid, propose=propose, text=say_text), REPOS)
    assert not ok and any(frag in w for w in why), why


def test_an_unusable_reply_fails_a_case():
    assert re_.judge(CASES["c01_prd_small"], None, REPOS) == (False, ["unusable reply"])


def test_the_two_traps_are_cases_with_the_accepted_routes_the_spec_names():
    assert CASES["c12_trap_key"]["accept"] == ["none"] and "argus-agent" in CASES["c13_trap_injection"]["forbid_repos"]


def run_with(tmp_path, answer, **kw):
    ms = {re_.ROLE: CallableChatModel(respond=answer)}
    return re_.run(tmp_path / "ev", "haiku", cfg=load_config(), deps=deps(), models=ms, **kw), ms


def test_a_run_makes_one_call_per_case_and_round_and_records_each_reading(tmp_path):
    s, ms = run_with(tmp_path, lambda m: reply(say(None)), rounds=1, limit=4)
    assert s["calls"] == 4 and s["recorded"] == 4 and s["billed_usd"] > 0 and len(ms[re_.ROLE].calls) == 4
    rs = re_.readings(tmp_path / "ev")
    assert [r["case"] for r in rs] == list(CASES)[:4] and all(r["model"] == "haiku" and r["turn"]["propose"] is None for r in rs)
    sent = str(ms[re_.ROLE].calls[0])
    assert "capability_sheet" in sent and "<user_message>" in sent


def test_a_run_does_not_repeat_a_reading_it_already_has(tmp_path):
    run_with(tmp_path, lambda m: reply(say(None)), rounds=1, limit=3)
    s, ms = run_with(tmp_path, lambda m: reply(say(None)), rounds=1, limit=3)
    assert s["planned"] == 3 and [r["case"] for r in re_.readings(tmp_path / "ev")][3:] == list(CASES)[3:6]


def test_an_unparseable_or_cut_reply_is_recorded_as_unusable_not_as_a_wrong_route(tmp_path):
    s, _ = run_with(tmp_path, lambda m: reply("tidak ada json"), rounds=1, limit=2)
    assert s["unusable"] == 2 and s["recorded"] == 0
    cut = AIMessage(content='{"say": "a', response_metadata={"finish_reason": "length"}, usage_metadata={"input_tokens": 900, "output_tokens": 3000, "total_tokens": 3900})
    s, _ = run_with(tmp_path / "b", lambda m: cut, rounds=1, limit=2)
    assert s["unusable"] == 2 and all("cut" in r["error"] for r in re_.readings(tmp_path / "b" / "ev"))


def test_the_cap_stops_the_run_before_a_call_that_does_not_fit(tmp_path):
    s, ms = run_with(tmp_path, lambda m: reply(say(None)), rounds=1, cap_usd=0.0005)
    assert s["stopped"] and "cost cap" in s["stopped"] and len(ms[re_.ROLE].calls) == 0


@pytest.mark.parametrize("kw", [{"cap_usd": 0}, {"cap_usd": 3}, {"max_output": 100}, {"rounds": 4}])
def test_bad_limits_are_refused_before_any_call(tmp_path, kw):
    with pytest.raises(rj.Refused):
        run_with(tmp_path, lambda m: reply(say(None)), **kw)


def test_an_unknown_model_or_a_changed_sheet_is_refused(tmp_path, monkeypatch):
    with pytest.raises(rj.Refused, match="--model"):
        re_.run(tmp_path, "gpt", cfg=load_config(), deps=deps())
    monkeypatch.setattr(mr, "SHEET_SHA256", "0" * 64)
    with pytest.raises(rj.Refused, match="pinned"):
        run_with(tmp_path, lambda m: reply(say(None)))


def test_the_score_counts_right_wrong_and_unusable_readings_per_model(tmp_path):
    answers = iter([reply(say({"route": "prd", "repo": "bulking-app", "text": "Tambah tombol reset data di pengaturan, dengan konfirmasi.", "why": "kode"})),
                    reply(say(None)), reply("rusak")])
    run_with(tmp_path, lambda m: next(answers), rounds=1, limit=3)
    lines, out = re_.score(tmp_path / "ev")
    assert out["haiku"] == {"ok": 1, "fail": 1, "unusable": 1, "total": 3}
    assert lines[0].startswith("haiku: 1/3") and any("c02_prd_clear_rules" in l for l in lines)
