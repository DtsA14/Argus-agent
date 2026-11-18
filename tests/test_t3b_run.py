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
    assert (s["planned"], s["calls"], s["recorded"], s["unusable"], s["refused"]) == (20, 20, 20, 0, 0) and s["stopped"] is None and s["billed_usd"] > 0
    reads = t3.read_all(root)
    assert len(reads) == 20 and {r["run"] for r in reads} == {1} and all(r["reader"].startswith("argus:openrouter:z-ai/glm") for r in reads)
    assert len(model.calls) == 20 and (t3.keydir(root) / tr.LEDGER).exists()


def test_the_reader_is_given_the_instruction_and_one_bundle_and_nothing_about_the_key(root, cfg):
    s, model = run(root, cfg, lambda m: reply(), limit=3)
    for c in model.calls:
        system, human = c["messages"][0].content, c["messages"][1].content
        assert system == tr.INSTRUCTION and "You are the domain reader of an Argus plan" in human
        assert "planted" not in human.lower() and "t3b" not in human.lower() and ".key" not in human and "good set" not in human.lower()
        assert len(c["messages"]) == 2


def test_the_cap_is_never_passed_a_call_starts_only_if_billed_plus_its_worst_case_fits(root, cfg):
    s, model = run(root, cfg, lambda m: reply(), cap_usd=0.05, max_output=6000)
    assert s["stopped"] and "cost cap" in s["stopped"] and s["calls"] < 20 and s["billed_usd"] <= 0.05
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
    assert s["planned"] == 15 and len(t3.read_all(root)) == 20
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


def test_a_timeout_that_uses_up_the_reservation_is_a_failed_call_not_a_crash(root, cfg):
    from harness.errors import TransientError
    s, model = run(root, cfg, lambda m: TransientError("timeout"), limit=5)
    assert s["calls"] >= 1 and s["recorded"] == 0
    errs = (t3.keydir(root) / tr.ERRORS).read_text()
    assert "call failed" in errs and "Traceback" not in errs


def test_a_reply_cut_at_the_output_limit_is_not_a_reading_and_says_so(root, cfg):
    cut = AIMessage(content=json.dumps({"verdict": "concerns", "sources": ["permintaan Atha"], "note": "x"}),
                    usage_metadata={"input_tokens": 3000, "output_tokens": 6000, "total_tokens": 9000},
                    response_metadata={"finish_reason": "length", "token_usage": {"prompt_tokens": 3000, "completion_tokens": 6000, "cost": 0.03}})
    s, model = run(root, cfg, lambda m: cut, limit=2)
    assert s["unusable"] == 2 and s["recorded"] == 0 and t3.read_all(root) == []
    e = json.loads((t3.keydir(root) / tr.ERRORS).read_text().splitlines()[0])
    assert e["why"] == "the reply was cut at the output limit" and e["finish_reason"] == "length" and e["output_tokens"] == 6000


def test_the_worst_case_of_a_call_is_input_at_the_input_price_plus_the_output_limit_at_the_output_price(cfg):
    ref = tr.ModelRef.parse(cfg["roles"][tr.ROLE]["model"])
    p = cfg["prices"][str(ref)]
    assert tr.worst_usd(cfg, ref, 2500, 6000) == pytest.approx(1000 * p["input"] / 1e6 + 6000 * p["output"] / 1e6)
    assert tr.worst_usd(cfg, ref, 0, 0) == 0 and tr.CHARS_PER_TOKEN == 2.5


def test_the_cap_is_total_across_the_two_runs(root, cfg):
    s1, _ = run(root, cfg, lambda m: reply(tokens=(3000, 5000)), limit=2, cap_usd=0.10)
    spent = s1["billed_usd"]
    assert spent > 0
    s2, model = run(root, cfg, lambda m: reply(tokens=(3000, 5000)), run_no=2, cap_usd=spent + 0.001)
    assert s2["calls"] == 0 and "cost cap" in s2["stopped"] and s2["billed_usd"] == pytest.approx(spent)


def test_a_call_that_just_fits_is_sent_and_one_that_does_not_is_not(root, cfg):
    ref = tr.ModelRef.parse(cfg["roles"][tr.ROLE]["model"])
    first = sorted(p.name for p in (root / "jobs").iterdir())[0]
    w = tr.worst_usd(cfg, ref, len(tr.INSTRUCTION) + len(t3.bundle(root, first)[0]), 6000)
    s, model = run(root, cfg, lambda m: reply(), limit=1, cap_usd=w)
    assert s["calls"] == 1                                                  # exactly equal to the cap: allowed (billed 0 + worst == cap)
    root2 = root.parent / "t3b_b"
    t3.build(root2, seed=1)
    first2 = sorted(p.name for p in (root2 / "jobs").iterdir())[0]
    w2 = tr.worst_usd(cfg, ref, len(tr.INSTRUCTION) + len(t3.bundle(root2, first2)[0]), 6000)
    s, model = run(root2, cfg, lambda m: reply(), limit=1, cap_usd=w2 - 0.0005)
    assert s["calls"] == 0


def test_the_instruction_points_at_the_rules_before_the_first_data_header_and_the_template_keeps_rule_1():
    from router import examples_read as er
    assert "before its first DATA header" in tr.INSTRUCTION
    assert "Rules 1 to 4 still hold." in er.TEMPLATE and "6. Numbers are written in the Indonesian style" in er.TEMPLATE


def test_a_reply_as_a_list_of_text_parts_is_read():
    class M:
        content = [{"type": "text", "text": "{\"verdict\": \"ok\", "}, {"type": "text", "text": "\"sources\": [], \"note\": \"n\"}"}]
    assert tr.text_of(M()) == '{"verdict": "ok", "sources": [], "note": "n"}'


def test_a_success_between_failures_resets_the_count_of_failures_in_a_row(root, cfg):
    calls = []

    def respond(m):
        calls.append(1)
        return RuntimeError("down") if len(calls) % 3 != 0 else reply()
    s, model = run(root, cfg, respond, limit=9)
    assert s["calls"] == 9 and s["recorded"] == 3 and s["stopped"] is None


def test_the_head_of_an_unusable_reply_is_cut_at_200_characters(root, cfg):
    run(root, cfg, lambda m: AIMessage(content="x" * 1000, usage_metadata={"input_tokens": 3000, "output_tokens": 300, "total_tokens": 3300}), limit=1)
    assert len(json.loads((t3.keydir(root) / tr.ERRORS).read_text().splitlines()[0])["head"]) == 200


def test_the_last_fenced_object_of_a_reply_is_the_answer():
    text = ('```json\n{"verdict": "ok", "sources": [], "note": "first"}\n```\nI changed my mind:\n'
            '```json\n{"verdict": "concerns", "sources": [], "note": "last"}\n```')
    assert tr.parse_answer(text) == ("concerns", [], "last")


@pytest.mark.parametrize("kw,ok", [({"cap_usd": 5}, True), ({"cap_usd": 6}, False), ({"max_output": 500}, True), ({"max_output": 499}, False),
                                   ({"max_output": 32000}, True), ({"max_output": 32001}, False)])
def test_the_limits_of_the_numbers(root, cfg, kw, ok):
    if ok:
        run(root, cfg, lambda m: reply(), limit=1, **kw)
    else:
        with pytest.raises(rj.Refused):
            run(root, cfg, lambda m: reply(), limit=1, **kw)


def test_the_reservation_of_a_call_covers_the_input_the_output_limit_and_a_margin():
    r = tr.reservation(2500, 6000, 0.03)
    assert r.tokens == 1000 + 6000 + 2000 and r.usd == 0.03


def test_the_run_stops_when_the_ledger_is_not_complete(root, cfg, monkeypatch):
    real = tr.reconcile_ledger
    monkeypatch.setattr(tr, "reconcile_ledger", lambda ev: (real(ev)[0], {**real(ev)[1], "usd_complete": False}))
    s, model = run(root, cfg, lambda m: reply())
    assert s["calls"] == 0 and "not complete" in s["stopped"]


def test_an_error_line_holds_the_type_of_the_exception_never_its_text(root, cfg):
    run(root, cfg, lambda m: RuntimeError("boom sk-or-v1-testkey1234567890abcdef"), limit=1)
    line = (t3.keydir(root) / tr.ERRORS).read_text()
    assert "LLMCallFailed" in line and "boom" not in line and "sk-or-v1" not in line


def test_the_copy_of_the_config_carries_the_output_limit_and_the_cap_into_the_caller(root, cfg, monkeypatch):
    seen = []
    real = tr.LLMCaller

    def spy(c, role, log, model=None):
        seen.append((c["roles"][role]["max_output_tokens"], c["budget"]["max_usd"], role))
        return real(c, role, log, model=model)
    monkeypatch.setattr(tr, "LLMCaller", spy)
    run(root, cfg, lambda m: reply(), limit=1, max_output=3000, cap_usd=0.37)
    assert seen == [(3000, 0.37, "code_judge")]


def test_a_reading_the_path_refuses_with_a_system_exit_is_counted_as_refused(root, cfg, monkeypatch):
    def refuse(*a, **k):
        raise SystemExit("already recorded")
    monkeypatch.setattr(tr.t3, "record", refuse)
    s, model = run(root, cfg, lambda m: reply(), limit=2)
    assert s["refused"] == 2 and s["recorded"] == 0


def test_the_human_message_is_exactly_the_bundle(root, cfg):
    s, model = run(root, cfg, lambda m: reply(), limit=3)
    ids = sorted(p.name for p in (root / "jobs").iterdir())[:3]
    assert [c["messages"][1].content for c in model.calls] == [t3.bundle(root, j)[0] for j in ids]


def spy_params(monkeypatch):
    seen = []
    real = tr.LLMCaller

    def spy(c, role, log, model=None):
        seen.append(c["roles"][role].get("params"))
        return real(c, role, log, model=model)
    monkeypatch.setattr(tr, "LLMCaller", spy)
    return seen


@pytest.mark.parametrize("effort", ["low", "medium", "high"])
def test_the_effort_goes_into_the_copy_of_the_config_as_the_providers_reasoning_effort(root, cfg, monkeypatch, effort):
    seen = spy_params(monkeypatch)
    run(root, cfg, lambda m: reply(), limit=1, effort=effort)
    assert seen == [{"extra_body": {"reasoning": {"effort": effort}}}]
    assert "params" not in cfg["roles"][tr.ROLE]                                  # config.yaml's role is untouched


def test_without_effort_the_role_keeps_its_own_params_and_adds_none(root, cfg, monkeypatch):
    seen = spy_params(monkeypatch)
    run(root, cfg, lambda m: reply(), limit=1)
    assert seen == [cfg["roles"][tr.ROLE].get("params")]


def test_an_effort_keeps_the_other_params_and_extra_body_of_the_role(root, cfg, monkeypatch):
    cfg["roles"][tr.ROLE]["params"] = {"temperature": 0.2, "extra_body": {"foo": 1}}
    seen = spy_params(monkeypatch)
    run(root, cfg, lambda m: reply(), limit=1, effort="low")
    assert seen == [{"temperature": 0.2, "extra_body": {"foo": 1, "reasoning": {"effort": "low"}}}]
    assert cfg["roles"][tr.ROLE]["params"] == {"temperature": 0.2, "extra_body": {"foo": 1}}


def test_an_unknown_effort_is_refused_before_anything_is_sent(root, cfg):
    model = CallableChatModel(respond=lambda m: reply())
    with pytest.raises(rj.Refused, match="--effort"):
        tr.run(root, 1, cfg=cfg, deps=deps(), model=model, effort="max")
    assert model.calls == []


def test_the_screen_names_the_effort_or_says_the_provider_default(root, cfg):
    shown = []
    run(root, cfg, lambda m: reply(), limit=1, deps=deps(shown), effort="low")
    run(root, cfg, lambda m: reply(), limit=1, deps=deps(shown), run_no=2)
    assert "reasoning effort: low" in shown[0] and "the provider default" in shown[1]
