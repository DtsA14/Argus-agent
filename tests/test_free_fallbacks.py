"""Free model fallbacks (SPEC_GATEWAY_PROVIDER, Atha 2026-11-04): a free role's next free model when the one before was
rate limited (HTTP 429) before the stage's first reply; the choice is kept for a resume; never a paid model. Also the
fetch time in REPORT.md. Models are fakes."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_research_job as t  # noqa: E402
import test_research_profiles as tp  # noqa: E402

from harness.events import EventLog  # noqa: E402
from harness.memo import Memo  # noqa: E402
from models import gateway  # noqa: E402
from models.fake import FakeHTTPError, StrictScriptedChatModel  # noqa: E402
from models.registry import ConfigError  # noqa: E402
from research import loop as rl  # noqa: E402
from research import report as rp  # noqa: E402
from router import job as rj  # noqa: E402
from router import research as rr  # noqa: E402

GEMMA31, GEMMA26 = "openrouter:google/gemma-4-31b-it:free", "openrouter:google/gemma-4-26b-a4b-it:free"
VL = "openrouter:nvidia/nemotron-3.5-super-vl:free"
PAID = "openrouter:deepseek/deepseek-v4.1-flash"
LIMITED = [FakeHTTPError(429, "rate-limited upstream")] * 3          # LLMCaller tries 3 times


def checker_env(tmp_path, first, second=(), third=()):
    env = tp.free_env(tmp_path, [t.PLAN, t.REPORT], tp.WORKED, list(first))
    env.models[f"free_checker@{GEMMA26}"] = StrictScriptedChatModel(script=list(second))
    env.models[f"free_checker@{VL}"] = StrictScriptedChatModel(script=list(third))
    env.cfg["llm"]["base_delay"] = 0
    return env


def events(job, sid, name):
    f = job.runs / job.data["stages"][sid]["run_id"] / "events.jsonl"
    return [e for e in EventLog(f).read() if e["event"] == name]


# ---- the chain ---------------------------------------------------------------------------------------------------

def test_a_free_role_lists_its_free_fallbacks():
    c = t.cfg()
    assert gateway.fallback_chain(c, "free_checker") == [GEMMA31, GEMMA26, VL]
    assert gateway.fallback_chain(c, "researcher") == ["fake:scripted"]          # no fallbacks: just the model


@pytest.mark.parametrize("role, fallbacks, problem", [
    ("free_checker", [PAID], "only free gateway models fall back"),
    ("or_deepseek", [VL], "only free gateway models fall back"),            # a paid model never falls back
    ("free_checker", [GEMMA26, GEMMA26], "repeats a model"),
    ("free_checker", [GEMMA31], "repeats a model"),
    ("free_checker", GEMMA26, "must be a list"),
    ("free_checker", ["openrouter:x/unlisted:free"], "not in gateway_models"),
    ("free_checker", ["other:some/model:free"], "not on openrouter"),
])
def test_a_bad_fallback_chain_is_refused(role, fallbacks, problem):
    c = t.cfg()
    c["providers"]["other"] = {**c["providers"]["openrouter"], "api_key_env": "OTHER_KEY"}
    c["gateway_models"]["other:some/model:free"] = {"upstream": ["x"], "free": True}
    c["prices"]["other:some/model:free"] = {"input": 0, "output": 0}
    c["roles"][role]["fallback_models"] = fallbacks
    with pytest.raises(ConfigError, match=problem):
        gateway.fallback_chain(c, role)


def test_a_paid_fallback_creates_no_job(tmp_path):
    env = tp.free_env(tmp_path, [], [], [])
    env.cfg["roles"]["free_checker"]["fallback_models"] = [PAID]
    with pytest.raises(rj.Refused, match="only free gateway models fall back"):
        env.start(profile="free")
    assert env.confirms == []


# ---- falling back ------------------------------------------------------------------------------------------------

def test_a_rate_limited_checker_moves_to_its_next_free_model(tmp_path):
    env = checker_env(tmp_path, LIMITED, [t.CHECK])
    job = env.start(profile="free")
    assert job.data["state"] == rr.REPORT_READY
    assert json.loads((job.dir / "check.json").read_text())["status"] == rp.CHECKED
    [fb] = events(job, "e1", "model_fallback")
    assert fb["model"] == GEMMA31 and fb["next"] == GEMMA26
    calls = [e for e in events(job, "e1", "llm_call")]
    assert [e["model"] for e in calls] == [GEMMA31] * 3 + [GEMMA26] and calls[-1]["status"] == "ok"


def test_the_whole_chain_rate_limited_blocks_the_job(tmp_path):
    env = checker_env(tmp_path, LIMITED, LIMITED, LIMITED)
    job = env.start(profile="free")
    assert job.data["state"] == rr.BLOCKED and len(events(job, "e1", "model_fallback")) == 2


def test_another_error_does_not_fall_back(tmp_path):
    env = checker_env(tmp_path, [FakeHTTPError(400, "bad request")], [t.CHECK])
    job = env.start(profile="free")
    assert job.data["state"] == rr.BLOCKED and events(job, "e1", "model_fallback") == []
    assert env.models[f"free_checker@{GEMMA26}"].calls == []


def test_a_limit_after_the_first_reply_does_not_fall_back(tmp_path):
    bad = t.call("SubmitCheck", t.check_args(ids=("P1",)), "c")                   # rejected: the loop goes on
    env = checker_env(tmp_path, [bad, *LIMITED], [t.CHECK])
    job = env.start(profile="free")
    assert job.data["state"] == rr.BLOCKED and events(job, "e1", "model_fallback") == []
    assert env.models[f"free_checker@{GEMMA26}"].calls == []


def test_a_resumed_stage_continues_on_the_model_it_fell_back_to(tmp_path):
    cfg = t.cfg()
    memo, log = Memo(tmp_path / "memo.sqlite"), EventLog(tmp_path / "events.jsonl")
    memo.put("model_choice:check:e1", GEMMA26)                 # committed before the crash: GEMMA26 is in use
    seen = []

    def loop(caller):
        seen.append(str(caller.ref))
        return {"end": "submitted", "steps": 0, "submits": 1, "tokens_used": 0, "usd_used": 0.0, "result": {}}
    rl.with_fallbacks(cfg, "free_checker", log, memo, node="check", task_id="e1",
                      models={f"free_checker@{GEMMA26}": StrictScriptedChatModel(script=[])}, loop=loop)
    assert seen == [GEMMA26]


def test_the_model_in_use_is_committed_before_its_first_call(tmp_path):
    cfg = t.cfg()
    memo, log = Memo(tmp_path / "memo.sqlite"), EventLog(tmp_path / "events.jsonl")
    choices = []

    def loop(caller):
        choices.append(memo.get("model_choice:check:e1"))
        if len(choices) == 1:
            return {"end": "llm_failed", "steps": 0, "submits": 0, "tokens_used": 0, "usd_used": 0.0, "http_status": 429}
        return {"end": "submitted", "steps": 0, "submits": 1, "tokens_used": 0, "usd_used": 0.0, "result": {}}
    rl.with_fallbacks(cfg, "free_checker", log, memo, node="check", task_id="e1",
                      models={"free_checker": StrictScriptedChatModel(script=[]),
                              f"free_checker@{GEMMA26}": StrictScriptedChatModel(script=[])}, loop=loop)
    assert choices == [None, GEMMA26]


# ---- REPORT.md -----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("stored, shown", [(1793767159.69, "2026-11-04T04:39:19Z"), ("2026-11-04T04:39:19Z",
                                                                                  "2026-11-04T04:39:19Z"), (None, None)])
def test_a_fetch_time_is_shown_as_utc(stored, shown):
    assert rp._when(stored) == shown


def test_an_unpriced_fallback_creates_no_job(tmp_path):
    env = tp.free_env(tmp_path, [], [], [])
    del env.cfg["prices"][GEMMA26]
    with pytest.raises(rj.Refused, match="gemma-4-26b"):
        env.start(profile="free")
    assert env.confirms == []


# ---- added from the code review ----------------------------------------------------------------------------------

def test_a_free_rate_limit_uses_none_of_the_reservation(tmp_path):
    env = checker_env(tmp_path, LIMITED, LIMITED, [t.CHECK])          # 6 refusals, then the third model answers
    env.cfg["research_job"]["checker"]["attempt_tokens"] = 30000       # less than one worst case per refusal
    job = env.start(profile="free")
    assert job.data["state"] == rr.REPORT_READY
    refused = [e for e in events(job, "e1", "llm_call") if e.get("http_status") == 429]
    assert len(refused) == 6 and all(e["tokens"] == 0 and e["usd_nano"] == 0 for e in refused)


def test_a_stage_resumed_on_a_model_no_longer_in_its_chain_stops(tmp_path):
    cfg = t.cfg()
    memo, log = Memo(tmp_path / "memo.sqlite"), EventLog(tmp_path / "events.jsonl")
    memo.put("model_choice:check:e1", "openrouter:gone/model:free")
    with pytest.raises(ConfigError, match="no longer in roles.free_checker"):
        rl.with_fallbacks(cfg, "free_checker", log, memo, node="check", task_id="e1", models={},
                          loop=lambda caller: pytest.fail("no call"))


def test_a_fallback_gets_its_own_output_cap(tmp_path):
    cfg = t.cfg()
    cfg["research_job"]["max_output_tokens_by_model"][GEMMA26] = 7000
    memo, log = Memo(tmp_path / "memo.sqlite"), EventLog(tmp_path / "events.jsonl")
    memo.put("model_choice:check:e1", GEMMA26)
    caps = []
    rl.with_fallbacks(cfg, "free_checker", log, memo, node="check", task_id="e1",
                      models={f"free_checker@{GEMMA26}": StrictScriptedChatModel(script=[])},
                      loop=lambda c: caps.append(c.max_output) or {"end": "submitted", "steps": 0, "result": {}})
    assert caps == [7000]


def test_the_confirmation_shows_the_fallbacks(tmp_path):
    env = checker_env(tmp_path, [t.CHECK])
    env.start(profile="free")
    screen = env.confirms[0]
    assert f"checker {GEMMA31} -> {GEMMA26} -> {VL}" in screen and GEMMA26 in screen.split("free models (")[1]


def test_a_fallback_whose_limits_do_not_hold_creates_no_job(tmp_path):
    env = tp.free_env(tmp_path, [], [], [])
    env.cfg["prices"][GEMMA26]["long_context_above"] = 1000
    with pytest.raises(rj.Refused, match="research checker"):
        env.start(profile="free")
    assert env.confirms == []


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), 1e20])
def test_a_bad_fetch_time_is_shown_as_stored(bad):
    assert rp._when(bad) is bad
