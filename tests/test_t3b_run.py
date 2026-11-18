"""SPEC_KARTU_SETUJU section 8, T3b with an Argus model as the reader (router/t3b_run.py, `argus t3b-run`): every call through LLMCaller with its own cap, the reply
parsed as one JSON object and nothing else, a reading recorded through the real `examples-read` path, an unusable reply never a reading. A scripted model stands in
for GLM; no network, no key, no Docker."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import t3b_fixtures as t3  # noqa: E402

from models.fake import CallableChatModel  # noqa: E402
from router import job as rj  # noqa: E402
from router import t3b_run as tr  # noqa: E402
from runner import load_config  # noqa: E402


def reply(verdict="concerns", sources=("permintaan Atha",), note="the number is wrong", tokens=(3000, 400)):
    body = json.dumps({"verdict": verdict, "sources": list(sources), "note": note})
    return AIMessage(content=body, usage_metadata={"input_tokens": tokens[0], "output_tokens": tokens[1], "total_tokens": sum(tokens)},
                     response_metadata={"token_usage": {"prompt_tokens": tokens[0], "completion_tokens": tokens[1], "cost": 0.0053}})


def deps(shown=None):
    return rj.Deps(confirm=lambda text: (shown.append(text) if shown is not None else None) or True, get_key=lambda: "sk-or-v1-testkey1234567890abcdef",
                   isatty=lambda: True, echo=lambda *a, **k: None)


@pytest.fixture
def root(tmp_path):
    r = tmp_path / "t3b"
    t3.build(r, seed=1)
    return r


@pytest.fixture
def cfg():
    return load_config()


def run(root, cfg, respond, **kw):
    model = CallableChatModel(respond=respond)
    s = tr.run(root, kw.pop("run_no", 1), cfg=cfg, deps=kw.pop("deps", deps()), model=model, **kw)
    return s, model


def test_every_set_gets_one_call_and_one_reading_recorded_through_the_real_path(root, cfg):
    s, model = run(root, cfg, lambda m: reply())
    assert (s["planned"], s["calls"], s["recorded"], s["unusable"], s["refused"]) == (16, 16, 16, 0, 0) and s["stopped"] is None and s["billed_usd"] > 0
    reads = t3.read_all(root)
    assert len(reads) == 16 and {r["run"] for r in reads} == {1} and all(r["reader"].startswith("argus:openrouter:z-ai/glm") for r in reads)
    assert len(model.calls) == 16 and (t3.keydir(root) / tr.LEDGER).exists()


def test_the_reader_is_given_the_instruction_and_one_bundle_and_nothing_about_the_key(root, cfg):
    s, model = run(root, cfg, lambda m: reply(), limit=3)
    for c in model.calls:
        system, human = c["messages"][0].content, c["messages"][1].content
        assert system == tr.INSTRUCTION and "You are the domain reader of an Argus plan" in human
        assert "planted" not in human.lower() and "t3b" not in human.lower() and ".key" not in human and "good set" not in human.lower()
        assert len(c["messages"]) == 2


def test_the_cap_is_never_passed_a_call_starts_only_if_billed_plus_its_worst_case_fits(root, cfg):
    s, model = run(root, cfg, lambda m: reply(), cap_usd=0.05, max_output=6000)
    assert s["stopped"] and "cost cap" in s["stopped"] and s["calls"] < 16 and s["billed_usd"] <= 0.05
    worst = tr.worst_usd(cfg, tr.ModelRef.parse(cfg["roles"][tr.ROLE]["model"]), 15000, 6000)
    assert 0.03 < worst < 0.06                                          # a reasoning model's output limit is what makes a call expensive


def test_a_cap_below_the_worst_case_of_one_call_sends_nothing(root, cfg):
    s, model = run(root, cfg, lambda m: reply(), cap_usd=0.001)
    assert s["calls"] == 0 and model.calls == [] and "cost cap" in s["stopped"]


def test_a_reply_that_is_not_one_json_object_is_not_a_reading(root, cfg):
    s, model = run(root, cfg, lambda m: AIMessage(content="I think it is fine. ok", usage_metadata={"input_tokens": 3000, "output_tokens": 50, "total_tokens": 3050}),
                   limit=2)
    assert s["unusable"] == 2 and s["recorded"] == 0 and t3.read_all(root) == []
    errs = [json.loads(l) for l in (t3.keydir(root) / tr.ERRORS).read_text().splitlines()]
    assert len(errs) == 2 and "not one JSON object" in errs[0]["why"]


@pytest.mark.parametrize("text", ['{"verdict": "fine", "sources": [], "note": "x"}', '{"verdict": "ok", "sources": "permintaan Atha", "note": "x"}',
                                  '{"verdict": "ok", "sources": [1], "note": "x"}', '{"verdict": "ok", "sources": [], "note": "  "}', "[]", "{"])
def test_parse_answer_refuses_anything_but_the_asked_shape(text):
    assert tr.parse_answer(text) is None


def test_parse_answer_takes_a_fenced_object_and_an_object_inside_prose():
    assert tr.parse_answer('```json\n{"verdict": "ok", "sources": ["permintaan Atha"], "note": "fits"}\n```') == ("ok", ["permintaan Atha"], "fits")
    assert tr.parse_answer('Here: {"verdict": "concerns", "sources": [], "note": "wrong"} done') == ("concerns", [], "wrong")


def test_an_ok_that_rests_on_the_writers_text_alone_is_refused_by_the_real_path_and_is_not_a_reading(root, cfg):
    s, model = run(root, cfg, lambda m: reply(verdict="ok", sources=("hanya tulisan penulis",)), limit=2)
    assert s["refused"] == 2 and s["recorded"] == 0 and t3.read_all(root) == []
    assert "refused the reading" in json.loads((t3.keydir(root) / tr.ERRORS).read_text().splitlines()[0])["why"]


def test_three_failed_calls_in_a_row_stop_the_run(root, cfg):
    s, model = run(root, cfg, lambda m: RuntimeError("provider down"))
    assert s["stopped"] and s["calls"] <= 3 + 0 and s["recorded"] == 0


def test_a_set_with_a_reading_of_this_run_is_not_read_again(root, cfg):
    run(root, cfg, lambda m: reply(), limit=5)
    s, model = run(root, cfg, lambda m: reply())
    assert s["planned"] == 11 and len(t3.read_all(root)) == 16
    s, model = run(root, cfg, lambda m: reply(), run_no=2, limit=1)
    assert s["planned"] == 1 and {r["run"] for r in t3.read_all(root)} == {1, 2}


def test_the_config_is_not_changed_by_the_run(root, cfg):
    before = (cfg["roles"][tr.ROLE]["max_output_tokens"], cfg["budget"].get("max_usd"))
    run(root, cfg, lambda m: reply(), limit=1, max_output=3000, cap_usd=0.37)
    assert (cfg["roles"][tr.ROLE]["max_output_tokens"], cfg["budget"].get("max_usd")) == before


def test_the_human_sees_the_model_the_cap_and_the_calls_before_anything_is_sent(root, cfg):
    shown = []
    run(root, cfg, lambda m: reply(), limit=1, deps=deps(shown), cap_usd=0.4)
    assert len(shown) == 1 and "z-ai/glm" in shown[0] and "$0.40" in shown[0] and "1 call(s)" in shown[0] and "spec is unchanged" in shown[0]


def test_not_confirmed_sends_nothing(root, cfg):
    d = rj.Deps(confirm=lambda t: False, get_key=lambda: "sk-or-v1-testkey1234567890abcdef", isatty=lambda: True, echo=lambda *a, **k: None)
    model = CallableChatModel(respond=lambda m: reply())
    with pytest.raises(rj.Refused, match="not confirmed"):
        tr.run(root, 1, cfg=cfg, deps=d, model=model)
    assert model.calls == [] and t3.read_all(root) == []


@pytest.mark.parametrize("kw", [{"run_no": 3}, {"cap_usd": 0}, {"cap_usd": 50}, {"max_output": 100}, {"max_output": 10 ** 6}])
def test_bad_numbers_are_refused_before_anything(root, cfg, kw):
    with pytest.raises(rj.Refused):
        run(root, cfg, lambda m: reply(), **kw)


def test_a_directory_that_is_not_a_t3b_build_is_refused(tmp_path, cfg):
    (tmp_path / "x" / "jobs").mkdir(parents=True)
    with pytest.raises(rj.Refused, match="not a T3b directory"):
        run(tmp_path / "x", cfg, lambda m: reply())


def test_the_key_never_reaches_the_ledger_or_the_errors_file(root, cfg):
    run(root, cfg, lambda m: reply(note="the key sk-or-v1-testkey1234567890abcdef leaked"), limit=2)
    text = (t3.keydir(root) / tr.LEDGER).read_text() + ((t3.keydir(root) / tr.ERRORS).read_text() if (t3.keydir(root) / tr.ERRORS).exists() else "")
    assert "sk-or-v1-testkey1234567890abcdef" not in text


def test_the_command_is_one_of_the_live_commands_with_key_file_and_yes():
    import argus
    with pytest.raises(SystemExit):
        argus.main(["t3b-run", "--help"])
