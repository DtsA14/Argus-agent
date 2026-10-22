"""D1 (docs/reviews/DESIGN_ATTEMPT_USD.md): a budget profile may reserve an attempt in USD (attempt_usd) instead of pricing
its cumulative tokens as if all were output, and may cap the input of each call (max_input_tokens). Before D1, pilot3a's
attempt 0 stopped at 42,951 tokens having paid $0.1128 of the $0.45 reserved for it.

The model is scripted and the token counter is fixed per test, so every reservation decision is exact. fake:scripted is
priced $1/M input and $5/M output (config.yaml)."""
import copy
import json
import math
import sys
from pathlib import Path

import pytest

import harness.llm as llm
from codetask import run as run_module
from codetask import status as st
from codetask.run import admission, apply_profile, run_code_task, settings
from harness.events import EventLog
from models.fake import StrictScriptedChatModel, reply
from runner import load_config

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="the path jail needs openat; the VM runs these")

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = json.loads((ROOT / "fixtures" / "contracts" / "fix_divide.json").read_text(encoding="utf-8"))
CALC = (ROOT / "fixtures" / "repos" / "calc" / "src" / "calc.py").read_text(encoding="utf-8")
TEST = (ROOT / "fixtures" / "repos" / "calc" / "tests" / "test_calc.py").read_text(encoding="utf-8")
FIXED = CALC.replace("    if b == 0:\n        return 0\n", "")
CLAIMS = [{"claim": "tests_pass", "evidence": "validation:unit"},
          {"claim": "issue_fixed", "evidence": "validation:target"},
          {"claim": "file_changed", "path": "src/calc.py"}]
LARGE_USD = {"attempt_tokens": 400000, "attempt_usd": 0.45, "max_input_tokens": 40000, "max_output_tokens": 8192}
IN = 9000                       # input tokens of every call: counted before sending and billed after, the same number


def call(name, args, id):
    return reply(tool_calls=[{"name": name, "args": args, "id": id}], input_tokens=IN, output_tokens=100)


def reads(n):
    return [call("ReadFile", {"path": "src/calc.py"}, f"r{i}") for i in range(n)]


WRITE = call("WriteFile", {"path": "src/calc.py", "content": FIXED}, "w1")
FINISH = call("Finish", {"claims": CLAIMS, "summary": "divide raises on zero"}, "f1")


def fake_validate(spec, workspace, sandbox_cfg, log=None):
    ws = Path(workspace)
    ok = (ws / "src" / "calc.py").read_text() == FIXED and (ws / "tests" / "test_calc.py").read_text() == TEST
    return {"id": f"validation:{spec['id']}", "layer": "C", "status": "pass" if ok else "fail",
            "reason": "" if ok else "exit code 1; unittest outcome FAILED",
            "evidence": {"must_pass": {t: "ok" if ok else "FAIL" for t in spec.get("must_pass", [])},
                         "tests_run": 7, "failures": 0 if ok else 1, "output_tail": ""}}


def cfg(max_tokens=1_200_000, **profiles):
    """The test config. max_tokens 1,200,000 is the pilot config of K3 (3 attempts x 400,000)."""
    c = load_config()
    c["roles"]["coder"]["model"] = "fake:scripted"
    c["budget"]["max_tokens"] = max_tokens
    c["code_task"]["profiles"].update(profiles)
    return c


def contract(profile, **limits):
    c = copy.deepcopy(CONTRACT)
    c["budget_profile"] = profile
    c["limits"].update(limits)
    return c


@pytest.fixture
def counter(monkeypatch):
    """Replaces the provider's token counter with fn(messages) (default: IN for every call)."""
    def use(fn=lambda messages: IN):
        monkeypatch.setattr(llm, "provider_counter", lambda model, margin: (lambda m, t: fn(m), True))
    use()
    return use


def run(tmp_path, script, *, contract, config):
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(contract), encoding="utf-8")
    model = StrictScriptedChatModel(script=list(script))
    r = run_code_task(contract_path=path, run_id="t", runs_dir=tmp_path / "runs", cfg=config,
                      models={"coder": model}, validate=fake_validate, preflight=lambda: (True, "ok"))
    return r, model, tmp_path / "runs" / "t"


def events(d, kind=None):
    evs = [json.loads(l) for l in (d / "events.jsonl").read_text().splitlines()]
    return [e for e in evs if kind is None or e["event"] == kind]


def ends(d):
    return [(e["iteration"], e["reason"], e["steps"]) for e in events(d, "attempt_end")]


def sonnet(c, cap):
    c["roles"]["coder"]["model"] = "anthropic:claude-sonnet-5-5"
    c["budget"]["max_usd"] = cap
    return c


def admitted_after(limits, spends, tmp_path):
    log = EventLog(tmp_path / f"e{len(list(tmp_path.iterdir()))}.jsonl")
    for i, usd in enumerate(spends):
        log.emit("llm_call_started", call_id=f"c{i}", node="agent", task="x", iteration=i, step=0,
                 worst_tokens=1, worst_usd_nano=round(usd * 1e9))
        log.emit("llm_call", call_id=f"c{i}", status="ok", node="agent", task="x", iteration=i, step=0,
                 tokens=1000, usd_nano=round(usd * 1e9))
    return admission(log, limits) is None


# ---- the profile (K1, K2) -------------------------------------------------------------------------------------

def test_the_configured_large_usd_profile_is_the_decided_one():
    assert load_config()["code_task"]["profiles"]["large_usd"] == LARGE_USD


def test_a_declared_attempt_usd_is_the_attempt_reservation_whatever_the_price():
    for model in ("fake:scripted", "anthropic:claude-sonnet-5-5"):
        c = load_config()
        c["roles"]["coder"]["model"] = model
        lim = settings(apply_profile(c, "large_usd"))
        assert lim["attempt_usd"] == 0.45 and lim["attempt_tokens"] == 400000 and lim["max_input_tokens"] == 40000


def test_a_profile_without_attempt_usd_keeps_the_old_formula():   # T6
    c = sonnet(load_config(), 0.5)
    assert "large_usd" in c["code_task"]["profiles"]
    assert settings(c)["attempt_usd"] == pytest.approx(30000 * 10 / 1e6)
    assert settings(apply_profile(c, "large"))["attempt_usd"] == pytest.approx(45000 * 10 / 1e6)
    # applying another profile drops what large_usd declared: nothing leaks from one profile into the next
    again = settings(apply_profile(apply_profile(c, "large_usd"), "default"))
    assert again["attempt_usd"] == pytest.approx(30000 * 10 / 1e6) and again["max_input_tokens"] is None


# ---- the attempt (T1, T2) ---------------------------------------------------------------------------------------

def test_an_attempt_runs_past_45k_tokens_while_its_usd_fits(tmp_path, counter):   # T1, T5
    # 7 calls x 9,100 tokens = 63,700 tokens, $0.0665 at fake prices: under large_usd every call is sent
    r, model, d = run(tmp_path, reads(5) + [WRITE, FINISH], contract=contract("large_usd"), config=cfg())
    assert r["status"] == st.DONE and len(model.calls) == 7 and r["attempts"] == 1
    assert ends(d) == [(0, "finished", 6)] and not events(d, "estimate_overrun")
    assert sum(e["tokens"] for e in events(d, "llm_call")) == 63700 > 45000
    assert r["budget_profile"] == {"name": "large_usd", **LARGE_USD}


def test_the_same_calls_under_large_stop_at_45k_tokens(tmp_path, counter):          # T1, the old behaviour
    r, model, d = run(tmp_path, reads(5) + [WRITE, FINISH], contract=contract("large", max_iterations=1),
                      config=cfg(max_tokens=200000))
    assert len(model.calls) == 4 and ends(d) == [(0, "reservation_exhausted", 4)]    # 4 x 9,100 = 36,400; 9,000 + 64 > 8,600
    assert r["budget_profile"] == {"name": "large", "attempt_tokens": 45000, "max_output_tokens": 8192}


def test_attempt_usd_bounds_every_call_before_it_is_sent(tmp_path, counter):          # T2
    tight = {"attempt_tokens": 400000, "attempt_usd": 0.02, "max_output_tokens": 8192}
    r, model, d = run(tmp_path, reads(5), contract=contract("tight", max_iterations=1), config=cfg(tight=tight))
    started = events(d, "llm_call_started")
    # $0.02 - $0.009 input leaves $0.011 for output at $5/M = 2,200 tokens; then $0.0105 - $0.009 = 300; then nothing
    assert [e["max_tokens"] for e in started] == pytest.approx([2200, 300], abs=1) and len(model.calls) == 2
    refused = [e for e in events(d, "llm_call") if e["status"] == "refused"]
    assert len(refused) == 1 and refused[0]["step"] == 2 and refused[0].get("reason") != "input_limit"
    assert ends(d) == [(0, "reservation_exhausted", 2)]
    billed = [e["usd_nano"] for e in events(d, "llm_call") if e["status"] == "ok"]
    assert started[0]["worst_usd_nano"] <= 0.02e9 and started[1]["worst_usd_nano"] <= 0.02e9 - billed[0]
    assert sum(billed) <= 0.02e9


# ---- the input limit (T3, K5) -----------------------------------------------------------------------------------

def test_a_call_over_the_input_limit_is_refused_before_sending_and_ends_the_attempt(tmp_path, counter):
    counter(lambda messages: 8999 + len(messages) // 2)       # step 0: 2 messages -> 9,000; step 1: 4 -> 9,001
    small = {"attempt_tokens": 400000, "attempt_usd": 0.45, "max_input_tokens": 9000, "max_output_tokens": 8192}
    r, model, d = run(tmp_path, reads(3), contract=contract("small", max_iterations=1), config=cfg(small=small))
    started = events(d, "llm_call_started")
    assert [e["est_input"] for e in started] == [9000] and len(model.calls) == 1        # exactly at the limit: sent
    refused = [e for e in events(d, "llm_call") if e["status"] == "refused"]
    assert [(e["reason"], e["est_input"], e["max_input"], e["step"]) for e in refused] == [("input_limit", 9001, 9000, 1)]
    assert ends(d) == [(0, "context_limit", 1)]
    assert r["status"] == st.FAILED_ACCEPTANCE and r["stop_reason"] == "max_iterations"
    assert r["budget_profile"]["max_input_tokens"] == 9000


def test_without_an_input_limit_the_same_call_is_sent(tmp_path, counter):
    counter(lambda messages: 8999 + len(messages) // 2)
    r, model, d = run(tmp_path, reads(1) + [WRITE, FINISH], contract=contract("large"), config=cfg())
    assert r["status"] == st.DONE and len(model.calls) == 3
    assert not [e for e in events(d, "llm_call") if e["status"] == "refused"]


# ---- admission (T4, K3) and the guard (T5) ----------------------------------------------------------------------

def test_admission_with_large_usd_at_a_75_cent_cap(tmp_path):
    c = sonnet(load_config(), 0.75)
    c["budget"]["max_tokens"] = 1_200_000
    lim = settings(apply_profile(c, "large_usd"), contract("large_usd", max_usd=0.75))
    assert lim["attempt_usd"] == 0.45 and lim["max_usd"] == 0.75
    assert admitted_after(lim, [], tmp_path)
    # a second attempt only after a first one of at most $0.30 (K2), to the nano-dollar
    assert admitted_after(lim, [0.30], tmp_path) and not admitted_after(lim, [0.300000001], tmp_path)


def test_large_usd_with_the_default_token_limit_stops_before_any_model_call(tmp_path, counter):   # K3: fails closed
    model = StrictScriptedChatModel(script=[FINISH])
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(contract("large_usd")), encoding="utf-8")
    r = run_code_task(contract_path=path, run_id="t", runs_dir=tmp_path / "runs", cfg=cfg(max_tokens=200000),
                      models={"coder": model}, validate=fake_validate, preflight=lambda: (True, "ok"))
    assert r["status"] == st.FAILED_BUDGET and r["stop_reason"].startswith("max_tokens") and len(model.calls) == 0


def test_the_agent_node_is_guarded_with_the_profile_values(tmp_path, counter, monkeypatch):
    seen, real = {}, run_module.guard

    def spy(name, fn, **kw):
        seen[name] = kw
        return real(name, fn, **kw)
    monkeypatch.setattr(run_module, "guard", spy)
    r, model, d = run(tmp_path, [WRITE, FINISH], contract=contract("large_usd"), config=cfg())
    assert r["status"] == st.DONE
    assert seen["agent"]["estimate"] == 400000 and math.isclose(seen["agent"]["usd_estimate"], 0.45)
