"""`argus patch-read-run` (router/patch_read_run.py, SPEC_KARTU_SETUJU 13.5): the patch reader of a job is Hy4 Flash, then (only on `ok`) DeepSeek 1017; both through
LLMCaller with a cap; the readings are written through patch_read.record. Scripted models stand in; no network, no key."""
import json
import sys
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_router as tr  # noqa: E402
from test_apply_cmd import edit_shop, env, package  # noqa: E402,F401
from test_patch_trial import deps as _deps  # noqa: E402,F401
from models.fake import CallableChatModel  # noqa: E402
from router import job as rj  # noqa: E402
from router import patch_read as pr  # noqa: E402
from router import patch_read_run as prr  # noqa: E402
from router import patch_trial as pt  # noqa: E402
from runner import load_config  # noqa: E402

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="posix")


def reply(verdict="ok", note="every changed line is explained by the issue", tokens=(2000, 200)):
    return AIMessage(content=json.dumps({"verdict": verdict, "note": note}),
                     usage_metadata={"input_tokens": tokens[0], "output_tokens": tokens[1], "total_tokens": sum(tokens)},
                     response_metadata={"token_usage": {"prompt_tokens": tokens[0], "completion_tokens": tokens[1], "cost": 0.0003}})


def models(first, second):
    return {prr.FIRST: CallableChatModel(respond=lambda m: first() if callable(first) else first),
            prr.SECOND: CallableChatModel(respond=lambda m: second() if callable(second) else second)}


def go(env, ms, **kw):
    from test_router import Env  # noqa: F401
    d = kw.pop("deps", None)
    return prr.run("jtest", cfg=load_config(), deps=d or env.deps, jobs_dir=env.jobs, models=ms, **kw)


@pytest.fixture
def world(env, tmp_path):
    patch, sha = package(env, tmp_path, edit_shop())
    env.deps.get_key = lambda: "sk-or-v1-testkey1234567890abcdef"
    env.deps.confirm = lambda text: True
    env.deps.isatty = lambda: True
    return env, sha


def test_both_say_ok_and_the_patch_is_ok_with_two_argus_readers(world):
    env, sha = world
    ms = models(reply(), reply())
    s = go(env, ms)
    assert s["final"] == "ok" and [r["reader"] for r in s["readings"]] == [prr.reader_id("hy4flash"), prr.reader_id("ds1017")] and s["billed_usd"] > 0
    kind, rec = pr.load(env.job().dir, "a1", sha)
    assert kind == "ok" and rec["reader"] == {"kind": "argus", "id": "argus:openrouter:tencent/hy4-flash"}
    assert rec["second"]["reader"]["id"] == "argus:openrouter:deepseek/deepseek-v4.1-flash-1017"
    assert len(ms["hy4flash"].calls) == 1 and len(ms["ds1017"].calls) == 1


def cut():
    return AIMessage(content='{"verdict": "ok", "no', response_metadata={"finish_reason": "length"},
                     usage_metadata={"input_tokens": 2000, "output_tokens": 200, "total_tokens": 2200})


def test_a_concerns_of_the_first_does_not_stop_the_second_and_both_findings_are_kept(world):
    """2026-11-19, a real patch: the first reader found one thing, the second found a second, real bug that the first had missed."""
    env, sha = world
    ms = models(reply("concerns", "it writes ~/.shop_audit"), reply("concerns", "int() of a unicode digit raises"))
    s = go(env, ms)
    kind, rec = pr.load(env.job().dir, "a1", sha)
    assert s["final"] == "concerns" and kind == "concerns" and len(ms["ds1017"].calls) == 1
    assert [n for _, n in pr.findings(rec)] == ["it writes ~/.shop_audit", "int() of a unicode digit raises"]
    with pytest.raises(rj.Refused, match="shop_audit.*unicode digit"):
        pr.require_ok(env.job(), "a1", sha)


def test_the_second_is_asked_after_a_concerns_of_the_first_even_when_it_says_ok_and_the_patch_stays_closed(world):
    env, sha = world
    ms = models(reply("concerns", "it writes ~/.shop_audit"), reply())
    s = go(env, ms)
    kind, rec = pr.load(env.job().dir, "a1", sha)
    assert s["final"] == "concerns" and len(ms["ds1017"].calls) == 1 and [n for _, n in pr.findings(rec)] == ["it writes ~/.shop_audit"]


def test_an_unusable_first_reading_ends_the_run_and_the_second_is_not_asked(world):
    env, sha = world
    ms = models(cut(), reply())
    s = go(env, ms)
    assert s["readings"][0]["usable"] is False and ms["ds1017"].calls == [] and s["final"] == "none"


def test_a_first_concerns_with_no_second_is_resumed_with_the_second_only(world):
    env, sha = world
    first = models(reply("concerns", "it writes ~/.shop_audit"), cut())
    s = go(env, first)
    assert s["final"] == "concerns" and s["readings"][1]["usable"] is False                   # the second was cut: only the first is on record
    again = models(reply("ok"), reply("concerns", "default changed"))
    s = go(env, again)
    kind, rec = pr.load(env.job().dir, "a1", sha)
    assert again["hy4flash"].calls == [] and len(again["ds1017"].calls) == 1 and kind == "concerns"
    assert [n for _, n in pr.findings(rec)] == ["it writes ~/.shop_audit", "default changed"]
    s = go(env, models(reply(), reply()))
    assert "nothing is read again" in s["stopped"]                                              # both readings are there now


def test_the_default_output_limit_leaves_room_for_a_reasoning_model():
    import inspect
    assert inspect.signature(prr.run).parameters["max_output"].default == 64000


def test_a_concerns_of_the_second_closes_and_both_are_kept(world):
    env, sha = world
    s = go(env, models(reply(), reply("concerns", "default changed")))
    kind, rec = pr.load(env.job().dir, "a1", sha)
    assert s["final"] == "concerns" and kind == "concerns" and rec["note"] == "default changed"


def test_the_reader_is_given_the_template_the_issue_the_touched_files_and_the_patch_and_nothing_else(world):
    env, sha = world
    ms = models(reply(), reply())
    go(env, ms)
    c = ms["hy4flash"].calls[0]["messages"]
    assert len(c) == 2 and c[0].content == pt.INSTRUCTION and c[1].content.startswith(pr.TEMPLATE)
    human = c[1].content
    assert "=== DATA issue ===" in human and "=== DATA touches ===" in human and "=== DATA patch ===" in human and "  +++ b/" in human
    touched = human.split("=== DATA touches ===")[1].split("===")[0].strip()
    assert touched.endswith(".py") and "\n" not in touched and f"+++ b/{touched}" in human.replace("  +++", "+++")
    assert "t3b" not in human.lower() and "reader_tests" not in human


@pytest.mark.parametrize("bad", [AIMessage(content="looks fine. ok", usage_metadata={"input_tokens": 2000, "output_tokens": 20, "total_tokens": 2020}),
                                 AIMessage(content='{"verdict": "fine", "note": "x"}', usage_metadata={"input_tokens": 2000, "output_tokens": 20, "total_tokens": 2020})])
def test_a_reply_that_is_not_the_asked_json_is_not_a_reading_and_nothing_is_written(world, bad):
    env, sha = world
    s = go(env, models(bad, reply()))
    assert s["final"] == "none" and s["readings"][0]["usable"] is False and not (env.job().dir / "patch_read_a1.json").exists()


def test_a_failed_second_call_leaves_the_first_reading_and_a_new_run_asks_only_the_second(world):
    env, sha = world
    s = go(env, models(reply(), AIMessage(content="not json", usage_metadata={"input_tokens": 2000, "output_tokens": 5, "total_tokens": 2005})))
    assert s["final"] == "one" and pr.load(env.job().dir, "a1", sha)[0] == "one"
    ms = models(reply(), reply())
    s = go(env, ms)
    assert s["final"] == "ok" and ms["hy4flash"].calls == [] and len(ms["ds1017"].calls) == 1


def test_a_patch_with_a_final_reading_is_not_read_again(world):
    env, sha = world
    go(env, models(reply(), reply()))
    ms = models(reply(), reply())
    s = go(env, ms)
    assert ms["hy4flash"].calls == [] and ms["ds1017"].calls == [] and "already has a final reading" in s["stopped"]


def test_the_cap_is_total_for_the_job_and_a_call_starts_only_if_it_fits(world):
    env, sha = world
    ms = models(reply(), reply())
    s = go(env, ms, cap_usd=0.0001)
    assert s["stopped"] and "cost cap" in s["stopped"] and ms["hy4flash"].calls == [] and ms["ds1017"].calls == []
    for kw in ({"cap_usd": 0}, {"cap_usd": 3}, {"max_output": 10}, {"max_output": 100001}):
        with pytest.raises(rj.Refused):
            go(env, ms, **kw)


def test_a_reasoning_model_may_be_given_up_to_100000_output_tokens_and_the_defaults_leave_room(world):
    """The second reader (a reasoning model) spent 29,993 and 31,993 tokens on thinking alone on a 27 KB patch (2026-11-19): the ceiling is 100,000."""
    env, sha = world
    import inspect
    assert inspect.signature(prr.run).parameters["max_output"].default == 64000
    assert inspect.signature(prr.run).parameters["cap_usd"].default == 0.20
    s = go(env, models(reply(), reply()), max_output=100000, cap_usd=0.5)
    assert s["final"] == "ok" and s["stopped"] is None


def test_only_a_job_with_a_review_package_is_read_and_the_ledger_is_beside_the_job(world, env):
    env, sha = world
    go(env, models(reply(), reply()))
    assert (env.job().dir / prr.LEDGER).exists()
    assert "patch_read_ledger" not in json.dumps(env.job().data)                           # nothing is added to job.json or its log


def test_a_first_note_written_by_a_claude_session_with_the_ids_of_the_pair_is_not_resumed_as_the_pairs(world):
    env, sha = world
    pr.record("jtest", sha, "ok", "claude says", "claude", prr.reader_id("hy4flash"), deps=env.deps, jobs_dir=env.jobs)
    ms = models(reply(), reply())
    s = go(env, ms)
    assert len(ms["hy4flash"].calls) == 1                                                  # not resumed: the first reading is asked again
    kind, rec = pr.load(env.job().dir, "a1", sha)
    assert kind == "ok" and rec["reader"]["kind"] == "argus"


def test_a_note_of_a_model_under_another_template_is_stale_and_is_read_again(world):
    env, sha = world
    go(env, models(reply(), reply()))
    f = env.job().dir / "patch_read_a1.json"
    rec = json.loads(f.read_text())
    rec["template_sha256"] = "0" * 64
    f.write_text(json.dumps(rec))
    assert pr.load(env.job().dir, "a1", sha)[0] == "stale"
    ms = models(reply(), reply())
    s = go(env, ms)
    assert s["final"] == "ok" and len(ms["hy4flash"].calls) == 1 and len(ms["ds1017"].calls) == 1
    assert json.loads(f.read_text())["template_sha256"] == pr.TEMPLATE_SHA256


def test_the_cap_stops_before_the_second_call_when_the_first_was_billed(world, monkeypatch):
    env, sha = world
    monkeypatch.setattr(prr.tr, "worst_usd", lambda cfg, ref, chars, out: 0.06 if "deepseek" in ref.model else 0.03)
    ms = models(reply(), reply())
    s = go(env, ms, cap_usd=0.05)
    assert len(ms["hy4flash"].calls) == 1 and ms["ds1017"].calls == [] and "cost cap" in s["stopped"] and s["final"] == "one"


def test_a_reading_the_job_refuses_to_take_is_reported_not_raised_after_the_money_was_spent(world, monkeypatch):
    env, sha = world
    real = pr.record

    def refuse(*a, **k):
        raise rj.Refused("job jtest: a fresh `concerns` of this very patch is not written over; nothing was written")
    monkeypatch.setattr(prr.pr, "record", refuse)
    s = go(env, models(reply(), reply()))
    assert s["readings"][0]["usable"] is False and "not written" in s["readings"][0]["why"] and s["billed_usd"] > 0
    monkeypatch.setattr(prr.pr, "record", real)


def test_the_status_line_says_how_to_get_the_readings_and_that_one_is_not_enough(world):
    env, sha = world
    out = "\n".join(rj.status("jtest", jobs_dir=env.jobs) if isinstance(rj.status("jtest", jobs_dir=env.jobs), list) else [rj.status("jtest", jobs_dir=env.jobs)])
    assert "patch-read-run jtest" in out
    pr.record("jtest", sha, "ok", "n", "claude", "a", deps=env.deps, jobs_dir=env.jobs)
    out = str(rj.status("jtest", jobs_dir=env.jobs))
    assert "a second reading is needed" in out


def test_a_file_with_a_second_reading_of_the_same_id_is_not_resumed_and_the_first_is_asked_again(world):
    env, sha = world
    go(env, models(reply(), reply()))
    f = env.job().dir / "patch_read_a1.json"
    rec = json.loads(f.read_text())
    rec["second"]["reader"]["id"] = rec["reader"]["id"]                                      # one id twice: `one`, with a second reading present
    f.write_text(json.dumps(rec))
    assert pr.load(env.job().dir, "a1", sha)[0] == "one"
    ms = models(reply(), reply())
    s = go(env, ms)
    assert len(ms["hy4flash"].calls) == 1 and s["final"] == "ok"


def test_a_ledger_that_holds_a_call_without_a_price_stops_the_run(world):
    env, sha = world
    with open(env.job().dir / prr.LEDGER, "w") as f:
        f.write(json.dumps({"ts": 0.5, "event": "llm_call_started", "call_id": "abc", "worst_tokens": 100, "worst_usd_nano": 1000}) + "\n")
        f.write(json.dumps({"ts": 1.0, "event": "llm_call", "node": "patch_reader", "task": "x", "iteration": 1, "step": 0, "role": "code_judge",
                            "model": "openrouter:tencent/hy4-flash", "call_id": "abc", "status": "ok", "attempt": 1, "input_tokens": 10, "output_tokens": 5, "tokens": 15}) + "\n")
    ms = models(reply(), reply())
    s = go(env, ms)
    assert "not complete" in (s["stopped"] or "") and ms["hy4flash"].calls == [] and s["final"] == "none"


def test_the_readers_can_be_chosen_and_the_model_named_first_is_asked_first(world):
    """`--first ds1017 --second hy4flash` (a measurement: the pair is then not the tested one): the model named first is asked first; the other is asked after it."""
    env, sha = world
    ms = models(reply(), reply("concerns", "web.py: methods other than the five named still give 501"))
    ms = {prr.FIRST: ms[prr.FIRST], prr.SECOND: ms[prr.SECOND]}
    s = go(env, {"ds1017": ms[prr.SECOND], "hy4flash": ms[prr.FIRST]}, first="ds1017", second="hy4flash")
    assert s["final"] == "concerns" and [r["reader"] for r in s["readings"]] == [prr.reader_id("ds1017"), prr.reader_id("hy4flash")]
    assert len(ms[prr.FIRST].calls) == 1 and len(ms[prr.SECOND].calls) == 1


def test_an_unknown_reader_name_is_refused(world):
    env, sha = world
    with pytest.raises(KeyError):
        go(env, models(reply(), reply()), first="nope")
