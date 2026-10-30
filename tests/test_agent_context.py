"""docs/reviews/SPEC_AGENT_CONTEXT_RETRY.md, the agent's side: the next attempt is told how the previous one ended
(and, after one that ran out of context without writing, what it read and what it may write); one context notice in
an attempt that nears its input limit without having written; max_input_tokens per coder model; and the feedback a
router retry carries into the first attempt of a new run. Router pilot #3: both attempts read 8-9 files, wrote
nothing, and ended context_limit; the second did not know why the first had stopped.

The token counter is replaced (test_attempt_usd's `counter`): 1,000 per message, so every decision is exact."""
import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_attempt_usd as tau  # noqa: E402
from test_attempt_usd import counter  # noqa: E402,F401  (the fixture)

from codetask import status as st  # noqa: E402
from codetask import agent as ca  # noqa: E402
from codetask.agent import feedback_from, task_prompt  # noqa: E402
from codetask.run import run_code_task  # noqa: E402
from models.fake import CallableChatModel, StrictScriptedChatModel  # noqa: E402
from runner import load_config  # noqa: E402

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="the path jail needs openat; the VM runs these")

PER = 1000                                     # estimated input tokens per message
BAD = tau.call("WriteFile", {"path": "src/calc.py", "content": tau.CALC + "\n# not the fix\n"}, "b1")
HINT = "It ran out of context before changing any file."
ENDED = "How the previous attempt ended:"


class Crash(BaseException):
    pass


def config(max_input, notice=None, model="fake:scripted"):
    c = tau.cfg(small={"attempt_tokens": 400000, "attempt_usd": 0.45, "max_input_tokens": max_input,
                       "max_output_tokens": 1024})
    c["roles"]["coder"]["model"] = model
    c["code_task"]["context_notice_at"] = notice
    return c


def go(tmp_path, model, cfg, *, resume=False, initial_feedback=None, profile="small"):
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "contract.json"
    if not path.exists():
        path.write_text(json.dumps(tau.contract(profile)), encoding="utf-8")
    r = run_code_task(contract_path=path, run_id="t", runs_dir=tmp_path / "runs", cfg=cfg, models={"coder": model},
                      validate=tau.fake_validate, preflight=lambda: (True, "ok"), resume=resume,
                      initial_feedback=initial_feedback)
    return r, tmp_path / "runs" / "t"


def text(request):
    return "\n".join(m.content if isinstance(m.content, str) else json.dumps(m.content) for m in request["messages"])


def crashing(script, crash_at):
    seen = []

    def respond(messages):
        seen.append(messages)
        if len(seen) - 1 == crash_at:
            raise Crash()
        return script[len(seen) - 1]
    return CallableChatModel(respond=respond)


def per_message(counter):
    counter(lambda messages: PER * len(messages))


# ---- 2.1 the next attempt is told how the previous one ended ------------------------------------------------------

def test_after_running_out_of_context_without_writing_the_next_attempt_is_told_what_it_read(tmp_path, counter):
    per_message(counter)
    # max_input 10,000: steps 0-4 send 2,000 ... 10,000; step 5 (12,000) is refused: context_limit after 5 steps
    model = StrictScriptedChatModel(script=tau.reads(5) + [tau.WRITE, tau.FINISH])
    r, d = go(tmp_path, model, config(10000))
    assert tau.ends(d)[0] == (0, "context_limit", 5) and r["status"] == st.DONE
    first = text(model.calls[5])                                 # attempt 1, step 0
    assert f"{ENDED} context_limit after 5 steps; it changed no file." in first
    assert f"{HINT} Files it read: src/calc.py." in first
    assert "The workspace is kept between attempts. Read only what the change needs, then write it: the writable " \
           "files are src/**." in first


def test_an_attempt_that_wrote_is_told_how_it_ended_without_the_context_hint(tmp_path, counter):
    per_message(counter)
    model = StrictScriptedChatModel(script=[BAD, tau.FINISH, tau.WRITE, tau.FINISH])
    r, d = go(tmp_path, model, config(100000))
    assert r["status"] == st.DONE
    first = text(model.calls[2])
    assert f"{ENDED} finished after 1 steps; it changed files." in first and HINT not in first


def test_an_attempt_that_wrote_and_then_ran_out_of_context_is_told_to_start_from_the_validations(tmp_path, counter):
    # argus-ledger 010b (fast lane): it used to get no hint, and the next attempt read the same whole files again
    per_message(counter)
    model = StrictScriptedChatModel(script=[BAD] + tau.reads(4) + [tau.WRITE, tau.FINISH])
    r, d = go(tmp_path, model, config(10000))
    assert tau.ends(d)[0] == (0, "context_limit", 5) and r["status"] == st.DONE
    first = text(model.calls[5])
    assert f"{ENDED} context_limit after 5 steps; it changed files." in first and HINT not in first
    assert "It ran out of context after changing files. Its changes are kept in the workspace: start with " \
           "RunValidation" in first


def test_feedback_without_a_stop_gives_the_prompt_it_always_gave():                            # guard
    fb = {"unmet": ["validation:unit: exit code 1"], "checks": ["files changed from the original: none"]}
    out = task_prompt(tau.CONTRACT, fb)
    assert out.endswith("  - files changed from the original: none") and ENDED not in out
    assert "stopped" not in feedback_from({"criteria": []})                  # no attempt given: none added


def test_the_files_read_are_in_order_unique_and_bounded():
    s = {"end": "context_limit", "steps": 9, "wrote": False, "read": [f"f{i}.py" for i in range(30)]}
    fb = feedback_from({"criteria": []}, attempt=s)
    assert fb["stopped"]["read"] == [f"f{i}.py" for i in range(20)]


def test_the_attempt_records_what_it_read_and_whether_it_wrote(tmp_path, counter):
    per_message(counter)
    other = tau.call("ReadFile", {"path": "tests/test_calc.py"}, "r9")
    model = StrictScriptedChatModel(script=tau.reads(1) + [other] + tau.reads(3) + [tau.WRITE, tau.FINISH])
    r, d = go(tmp_path, model, config(10000))
    assert [e["wrote"] for e in tau.events(d, "attempt_summary")] == [False, True]
    assert all("wrote" not in e for e in tau.events(d, "attempt_end"))            # its fields are as they were
    first = text(model.calls[5])
    assert "Files it read: src/calc.py, tests/test_calc.py." in first


def test_a_resumed_run_tells_the_next_attempt_the_same(tmp_path, counter):
    per_message(counter)
    script = tau.reads(5)
    with pytest.raises(Crash):
        go(tmp_path, crashing(script, crash_at=5), config(10000))        # dies in attempt 1's first request
    crashed = [e for e in tau.events(tmp_path / "runs" / "t", "llm_call_started")][-1]
    model = StrictScriptedChatModel(script=[tau.WRITE, tau.FINISH])
    r, d = go(tmp_path, model, config(10000), resume=True)
    assert r["status"] == st.DONE and len(model.calls) == 2                   # attempt 0 is not bought again
    again = [e for e in tau.events(d, "llm_call_started") if e["ts"] > crashed["ts"]]
    assert again[0]["prompt_hash"] == crashed["prompt_hash"] and HINT in text(model.calls[0])


# ---- 2.2 one context notice ----------------------------------------------------------------------------------------

def notice_text(model):
    return [i for i, c in enumerate(model.calls) if "Context: the next call is about" in text(c)]


def test_one_notice_when_the_input_nears_its_limit_and_nothing_was_written(tmp_path, counter):
    per_message(counter)
    # max 20,000, notice past 45% (9,000): after step 3 the next call is 10,000 -> one notice, then 11,000 ...
    model = StrictScriptedChatModel(script=tau.reads(4) + [tau.WRITE, tau.FINISH])
    r, d = go(tmp_path, model, config(20000, notice=0.45))
    assert r["status"] == st.DONE and notice_text(model) == [4, 5]          # shown from step 4 on, added once
    assert ca.CONTEXT_NOTICE.format(p=50, est=10000, max=20000) in text(model.calls[4])
    assert text(model.calls[5]).count("Context: the next call is about") == 1
    assert [e["shown"] for e in tau.events(d, "context_notice")] == [False, False, False, True]


def test_no_notice_after_a_write_without_a_limit_or_when_off(tmp_path, counter):
    per_message(counter)
    for i, (cfg, profile) in enumerate([(config(20000, notice=0.45), "small"),
                                        (config(20000, notice=None), "small"),
                                        (config(20000, notice=0.45), "large")]):
        script = ([BAD] if i == 0 else []) + tau.reads(4) + [tau.WRITE, tau.FINISH]
        model = StrictScriptedChatModel(script=script)
        r, d = go(tmp_path / str(i), model, cfg, profile=profile)
        assert r["status"] == st.DONE and notice_text(model) == [], i
        assert (tau.events(d, "context_notice") == []) == (i > 0), i         # off or no limit: nothing decided


def test_a_committed_notice_is_taken_from_the_memo_on_resume(tmp_path, counter):
    per_message(counter)
    with pytest.raises(Crash):                            # the notice after step 3, the fix at step 4, dies at 5
        go(tmp_path, crashing(tau.reads(4) + [tau.WRITE], crash_at=5), config(20000, notice=0.45))
    crashed = [e for e in tau.events(tmp_path / "runs" / "t", "llm_call_started")][-1]
    model = StrictScriptedChatModel(script=[tau.FINISH])   # the workspace is past the notice: it has the fix now
    r, d = go(tmp_path, model, config(20000, notice=0.45), resume=True)
    assert r["status"] == st.DONE and len(model.calls) == 1
    again = [e for e in tau.events(d, "llm_call_started") if e["ts"] > crashed["ts"]]
    assert again[0]["prompt_hash"] == crashed["prompt_hash"]


# ---- 2.3 max_input_tokens per model --------------------------------------------------------------------------------

def test_deepseek_gets_its_own_input_limit_and_sonnet_keeps_the_profiles():
    c = load_config()
    by_model = c["code_task"]["max_input_tokens_by_model"]
    assert by_model == {"deepseek:deepseek-flash": 60000, "deepseek:deepseek-v4-pro": 60000}
    assert c["code_task"]["context_notice_at"] == 0.7
    for model, want in (("deepseek:deepseek-flash", 60000), ("deepseek:deepseek-v4-pro", 60000),
                        ("anthropic:claude-sonnet-5-5", 40000)):
        x = copy.deepcopy(c)
        x["roles"]["coder"]["model"] = model
        assert tau.applied(x, "large_usd")["code_task"]["max_input_tokens"] == want, model
        assert tau.applied(x, "large")["code_task"].get("max_input_tokens") is None, model   # no input limit


def test_the_input_limit_of_the_model_is_the_one_the_run_uses_and_records(tmp_path, counter):
    per_message(counter)
    c = config(10000)
    c["code_task"]["max_input_tokens_by_model"] = {"fake:scripted": 14000}
    model = StrictScriptedChatModel(script=tau.reads(7) + [tau.WRITE, tau.FINISH])
    r, d = go(tmp_path, model, c)
    assert r["budget_profile"]["max_input_tokens"] == 14000 and tau.ends(d)[0] == (0, "context_limit", 7)


# ---- 2.4 a retry's first attempt is told how the previous run ended ------------------------------------------------

CARRY = {"carried": True, "from": "a1",
         "stopped": {"end": "context_limit", "steps": 5, "wrote": False, "read": ["src/calc.py", "README.md"]}}


def test_the_first_attempt_of_a_retried_run_is_told_how_the_previous_run_ended(tmp_path, counter):
    per_message(counter)
    model = StrictScriptedChatModel(script=[tau.WRITE, tau.FINISH])
    r, d = go(tmp_path, model, config(10000), initial_feedback=CARRY)
    first = text(model.calls[0])
    assert r["status"] == st.DONE
    assert "How the previous run of this task ended (this is a new run: the workspace starts again from the " \
           "original):\nits last attempt ended context_limit after 5 steps; it changed no file." in first
    assert f"{HINT} Files it read: src/calc.py, README.md." in first and "The workspace is kept" not in first
    assert "the writable files are src/**" in first


def test_the_carried_feedback_is_frozen_at_setup(tmp_path, counter):
    per_message(counter)
    with pytest.raises(Crash):
        go(tmp_path, crashing([], crash_at=0), config(10000), initial_feedback=CARRY)
    crashed = tau.events(tmp_path / "runs" / "t", "llm_call_started")[-1]
    model = StrictScriptedChatModel(script=[tau.WRITE, tau.FINISH])
    r, d = go(tmp_path, model, config(10000), resume=True, initial_feedback=None)     # setup is not run again
    again = [e for e in tau.events(d, "llm_call_started") if e["ts"] > crashed["ts"]]
    assert r["status"] == st.DONE and again[0]["prompt_hash"] == crashed["prompt_hash"]


# ---- scripts/audit_run.py rebuilds every prompt the agent got ------------------------------------------------------

def audit(run_dir):
    import os
    import subprocess
    root = Path(__file__).resolve().parent.parent
    out = subprocess.run([sys.executable, str(root / "scripts" / "audit_run.py"), str(run_dir)], capture_output=True,
                         text=True, cwd=root, env={**os.environ, "PYTHONPATH": str(root)})
    assert out.returncode == 0, out.stderr[-800:]
    return out.stdout


def test_audit_run_rebuilds_the_stop_feedback_the_notice_and_the_carried_feedback(tmp_path, counter):
    per_message(counter)
    # attempt 0: a notice after step 1 (6,000 > 5,400), then out of context at step 5 (13,000 > 12,000); attempt 1
    # is told so and fixes it (five calls leave the contract's $0.50 room for its attempt)
    model = StrictScriptedChatModel(script=tau.reads(5) + [tau.WRITE, tau.FINISH])
    r, d = go(tmp_path / "a", model, config(12000, notice=0.45))
    assert tau.ends(d)[0] == (0, "context_limit", 5), r["stop_reason"]
    assert r["status"] == st.DONE and HINT in text(model.calls[5]) and notice_text(model)[0] == 2
    out = audit(d)
    assert "prompt_hash checked 8, mismatches 0" in out and "(harness context notice after the step)" in out
    model = StrictScriptedChatModel(script=[tau.WRITE, tau.FINISH])
    r, d = go(tmp_path / "b", model, config(20000), initial_feedback=CARRY)
    assert r["status"] == st.DONE and "prompt_hash checked 2, mismatches 0" in audit(d)


# ---- SPEC_AGENT_OUTPUT_BUDGET: the output cap per model and the hint after a truncated reply -----------------------

def cut(id="c"):
    return tau.reply("long reasoning ...", stop_reason="max_tokens", input_tokens=tau.IN, output_tokens=100)


def test_deepseek_gets_a_larger_reply_on_usd_profiles_only_and_sonnet_keeps_its_own():
    c = load_config()
    assert c["code_task"]["max_output_tokens_by_model"] == {"deepseek:deepseek-flash": 32000,
                                                            "deepseek:deepseek-v4-pro": 32000}
    for model, profile, want in (("deepseek:deepseek-flash", "large_usd", 32000),
                                 ("deepseek:deepseek-v4-pro", "large_usd", 32000),
                                 ("deepseek:deepseek-flash", "large", 8192),        # a token profile: unchanged
                                 ("deepseek:deepseek-flash", "default", 4096),
                                 ("anthropic:claude-sonnet-5-5", "large_usd", 8192)):
        x = copy.deepcopy(c)
        x["roles"]["coder"]["model"] = model
        assert tau.applied(x, profile)["roles"]["coder"]["max_output_tokens"] == want, (model, profile)


def test_the_output_cap_of_the_model_is_the_one_the_run_uses_and_records(tmp_path, counter):
    per_message(counter)
    c = config(100000)
    c["code_task"]["max_output_tokens_by_model"] = {"fake:scripted": 3000}
    model = StrictScriptedChatModel(script=[tau.WRITE, tau.FINISH])
    r, d = go(tmp_path, model, c)
    assert r["status"] == st.DONE and r["budget_profile"]["max_output_tokens"] == 3000
    assert {e["max_tokens"] for e in tau.events(d, "llm_call") if e["status"] == "ok"} == {3000}


def test_a_larger_reply_is_still_bounded_by_the_attempts_usd(tmp_path, counter):
    # 32,000 output at $5/M is $0.16, over this attempt's $0.05: each call's cap is lowered to what fits (the caller's
    # rule since D1), so the run never pays more than its reservation
    per_message(counter)
    c = tau.cfg(small={"attempt_tokens": 400000, "attempt_usd": 0.05, "max_input_tokens": 100000,
                       "max_output_tokens": 1024})
    c["code_task"]["context_notice_at"] = None
    c["code_task"]["max_output_tokens_by_model"] = {"fake:scripted": 32000}
    model = StrictScriptedChatModel(script=[tau.WRITE, tau.FINISH])
    r, d = go(tmp_path, model, c)
    sent = [e for e in tau.events(d, "llm_call_started")]
    assert r["budget_profile"]["max_output_tokens"] == 32000
    assert sent and all(e["max_tokens"] < 32000 for e in sent)
    assert all(e["worst_usd_nano"] <= 0.05e9 for e in sent)


TRUNC = "Its last reply was cut at the output limit before any of its tool calls ran"


def test_after_a_truncated_reply_the_next_attempt_is_told_to_keep_replies_short(tmp_path, counter):
    per_message(counter)
    for i, script in enumerate(([cut()], [BAD, cut()])):            # before and after a write
        model = StrictScriptedChatModel(script=script + [tau.WRITE, tau.FINISH])
        r, d = go(tmp_path / str(i), model, config(100000))
        first = text(model.calls[len(script)])
        assert tau.ends(d)[0][1] == "output_truncated" and r["status"] == st.DONE, i
        assert f"{ENDED} output_truncated after {len(script) - 1} steps" in first and TRUNC in first, i
        assert "EditFile (one function or a few lines per call)" in first and HINT not in first, i


def test_the_truncation_hint_is_only_for_a_truncated_reply(tmp_path, counter):
    per_message(counter)
    model = StrictScriptedChatModel(script=[BAD, tau.FINISH, tau.WRITE, tau.FINISH])        # ended: finished
    go(tmp_path / "f", model, config(100000))
    assert TRUNC not in text(model.calls[2])
    model = StrictScriptedChatModel(script=tau.reads(5) + [tau.WRITE, tau.FINISH])          # ended: context_limit
    go(tmp_path / "c", model, config(10000))
    assert TRUNC not in text(model.calls[5]) and HINT in text(model.calls[5])


def test_a_retry_after_a_truncated_reply_is_told_too(tmp_path, counter):
    per_message(counter)
    carry = {"carried": True, "from": "a1", "stopped": {"end": "output_truncated", "steps": 3, "wrote": False,
                                                        "read": ["src/calc.py"]}}
    model = StrictScriptedChatModel(script=[tau.WRITE, tau.FINISH])
    r, d = go(tmp_path, model, config(100000), initial_feedback=carry)
    first = text(model.calls[0])
    assert r["status"] == st.DONE and TRUNC in first and "The workspace is kept" not in first


def test_audit_run_rebuilds_the_truncation_hint(tmp_path, counter):
    per_message(counter)
    model = StrictScriptedChatModel(script=[cut(), tau.WRITE, tau.FINISH])
    r, d = go(tmp_path, model, config(100000))
    assert r["status"] == st.DONE and TRUNC in text(model.calls[1])
    assert "prompt_hash checked 3, mismatches 0" in audit(d)


def test_audit_run_rebuilds_the_replies_the_harness_rejected(tmp_path, counter):
    # PENDING (audit_run without NUDGE): a reply without a tool call, an invalid call, and Finish beside another call
    per_message(counter)
    none = tau.reply("thinking aloud", input_tokens=tau.IN, output_tokens=50)
    bad = tau.reply(invalid_tool_calls=[{"name": "ReadFile", "args": "{not json", "id": "x1", "error": "bad json"}],
                    input_tokens=tau.IN, output_tokens=50)
    both = tau.reply(tool_calls=[{"name": "ReadFile", "args": {"path": "src/calc.py"}, "id": "r9"},
                                 {"name": "Finish", "args": {"claims": tau.CLAIMS, "summary": "x"}, "id": "f9"}],
                     input_tokens=tau.IN, output_tokens=50)
    model = StrictScriptedChatModel(script=[none, bad, both, tau.WRITE, tau.FINISH])
    r, d = go(tmp_path, model, config(100000))
    assert r["status"] == st.DONE and ca.NUDGE in text(model.calls[1])
    out = audit(d)
    assert "prompt_hash checked 5, mismatches 0" in out and out.count("reply rejected by the harness") == 3


# ---- SPEC_AGENT_BUDGET_GAPS 2.1: the hint after max_steps without writing --------------------------------------------

STEPS = "It used all of its steps without changing any file"


def cheap_reads(n):
    return [tau.reply(tool_calls=[{"name": "ReadFile", "args": {"path": "src/calc.py"}, "id": f"q{i}"}],
                      input_tokens=500, output_tokens=60) for i in range(n)]


def test_after_max_steps_without_writing_the_next_attempt_is_told_to_change_something_early(tmp_path, counter):
    per_message(counter)
    steps = load_config()["code_task"]["max_steps"]
    model = StrictScriptedChatModel(script=cheap_reads(steps) + [tau.WRITE, tau.FINISH])
    r, d = go(tmp_path, model, config(100000))
    assert tau.ends(d)[0] == (0, "max_steps", steps) and r["status"] == st.DONE
    first = text(model.calls[steps])
    assert STEPS in first and "with EditFile on the most likely place" in first
    assert "The workspace is kept between attempts." in first and TRUNC not in first and HINT not in first


def test_no_max_steps_hint_after_a_write_or_for_another_end(tmp_path, counter):
    per_message(counter)
    steps = load_config()["code_task"]["max_steps"]
    model = StrictScriptedChatModel(script=[BAD] + cheap_reads(steps - 1) + [tau.WRITE, tau.FINISH])
    go(tmp_path / "w", model, config(100000))
    assert STEPS not in text(model.calls[steps])
    model = StrictScriptedChatModel(script=tau.reads(5) + [tau.WRITE, tau.FINISH])                # context_limit
    go(tmp_path / "c", model, config(10000))
    assert STEPS not in text(model.calls[5]) and HINT in text(model.calls[5])


def test_a_retry_after_max_steps_without_writing_is_told_too(tmp_path, counter):
    per_message(counter)
    carry = {"carried": True, "from": "a1", "stopped": {"end": "max_steps", "steps": 12, "wrote": False, "read": []}}
    model = StrictScriptedChatModel(script=[tau.WRITE, tau.FINISH])
    r, d = go(tmp_path, model, config(100000), initial_feedback=carry)
    first = text(model.calls[0])
    assert r["status"] == st.DONE and STEPS in first and "The workspace is kept" not in first
    assert "prompt_hash checked 2, mismatches 0" in audit(d)
