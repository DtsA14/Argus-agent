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


def test_a_concerns_of_the_first_needs_no_second_call_and_closes(world):
    env, sha = world
    ms = models(reply("concerns", "it writes ~/.shop_audit"), reply())
    s = go(env, ms)
    assert s["final"] == "concerns" and ms["ds1017"].calls == [] and pr.load(env.job().dir, "a1", sha)[0] == "concerns"


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
    for kw in ({"cap_usd": 0}, {"cap_usd": 3}, {"max_output": 10}):
        with pytest.raises(rj.Refused):
            go(env, ms, **kw)


def test_only_a_job_with_a_review_package_is_read_and_the_ledger_is_beside_the_job(world, env):
    env, sha = world
    go(env, models(reply(), reply()))
    assert (env.job().dir / prr.LEDGER).exists()
    assert "patch_read_ledger" not in json.dumps(env.job().data)                           # nothing is added to job.json or its log
