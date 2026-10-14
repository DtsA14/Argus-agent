"""Phase 3b: the fact table, the canonical number rules and the writer model (scripted fakes: no network, no cost).

Contract: docs/MILESTONE3_PLAN.md 3.6. What must hold: every number a model writes (in `text` and in `action`)
matches a fact it references, in one canonical format; the harness, not the model, builds the facts and the
report; a truncated or invalid reply is never used; a committed reply is never bought again."""
import copy
import json
from decimal import Decimal

import pytest
from langchain_core.messages import HumanMessage, ToolMessage

import dataset
from harness.events import EventLog
from harness.llm import LLMCaller
from harness.memo import Memo
from models.fake import ScriptedChatModel, reply
from nodes.evaluator import run_checks
from nodes.facts import build_facts, check_numbers, round_half_up, validate_recommendations
from nodes.synthesize import make_llm_synthesize, template_recommendations
from runner import load_config, run_task
from tools.registry import ToolGate

T = dataset.truth()
TOP3, TREND = [list(x) for x in T["top3"]], [list(x) for x in T["trend"]]
FACTS = build_facts(TOP3, TREND)
SHARE = FACTS["top3.top2_share_of_top3_pct"]["value"]
GROWTH = FACTS["trend.first_to_last_growth_pct"]["value"]
(M1, V1), (M6, V6) = TREND[0], TREND[-1]
P1, P2 = TOP3[0][0], TOP3[1][0]


def good_recs():
    return [{"text": f"{P1} and {P2} bring {round_half_up(SHARE, 1)}% of the revenue of the three leaders.",
             "action": f"Bundle {P1} with {P2}.", "facts": ["top3.1.product", "top3.2.product",
                                                             "top3.top2_share_of_top3_pct"]},
            {"text": f"Revenue rose from {V1} in {M1} to {V6} in {M6}, up {round_half_up(GROWTH, 0)}%.",
             "action": "Order more stock before peak months.",
             "facts": [f"trend.{M1}.revenue", f"trend.{M6}.revenue", "trend.first_to_last_growth_pct"]}]


# ---- the fact table ------------------------------------------------------------------------------

def test_facts_are_built_by_the_harness_with_exact_decimals():
    total = sum(v for _, v in TOP3)
    assert SHARE == (Decimal(TOP3[0][1]) + Decimal(TOP3[1][1])) / Decimal(total) * 100
    assert GROWTH == (Decimal(V6) - Decimal(V1)) / Decimal(V1) * 100
    assert FACTS[f"trend.{M1}.revenue"] == {"id": f"trend.{M1}.revenue", "value": V1, "unit": "IDR",
                                            "source": "trend", "month": M1}
    assert isinstance(SHARE, Decimal) and isinstance(GROWTH, Decimal)


def test_a_zero_denominator_leaves_the_derived_fact_out():
    facts = build_facts([["A", 0], ["B", 0], ["C", 0]], [["2026-01", 0], ["2026-02", 5]])
    assert "top3.top2_share_of_top3_pct" not in facts and "trend.first_to_last_growth_pct" not in facts
    assert check_numbers("up 5%", facts, ["trend.first_to_last_growth_pct"]) == ["5% matches no referenced percentage fact"]


def test_negative_growth_is_a_fact_and_may_be_written_with_a_minus():
    facts = build_facts([], [["2026-01", 200], ["2026-02", 193]])
    assert facts["trend.first_to_last_growth_pct"]["value"] == Decimal("-3.5")
    assert check_numbers("down -3.5% since 2026-01", facts, ["trend.first_to_last_growth_pct", "trend.2026-01.revenue"]) == []


# ---- canonical numbers -----------------------------------------------------------------------------

REFS = ["top3.1.revenue", "top3.top2_share_of_top3_pct", f"trend.{M1}.revenue"]


@pytest.mark.parametrize("text", [
    f"{P1} earned {TOP3[0][1]}.",
    f"Share {round_half_up(SHARE, 1)}%, about {round_half_up(SHARE, 0)}%.",
    f"In {M1} revenue was {V1}, and {P1} {TOP3[0][1]}, {round_half_up(SHARE, 1)}%.",
    "No numbers at all.",
])
def test_canonical_numbers_that_match_referenced_facts_pass(text):
    assert check_numbers(text, FACTS, REFS) == []


@pytest.mark.parametrize("text, error", [
    (f"{round_half_up(SHARE, 1)}".replace(".", ",") + "%", "not canonical"),                 # decimal comma
    ("{:,}".format(TOP3[0][1]).replace(",", "."), "not canonical"),                         # 4.200.000
    ("{:,}".format(TOP3[0][1]), "not canonical"),                                           # 4,200,000
    (f"{round_half_up(SHARE, 1)}0%", "not canonical"),                                      # two decimals
    (f"{TOP3[0][1]}.5", "not canonical"),                                                   # decimal rupiah
    (f"{round_half_up(SHARE, 0)} percent", "matches no referenced fact"),                   # a percentage needs %
    (f"{round_half_up(SHARE, 0) + 1}%", "matches no referenced percentage fact"),
    (f"Rp{TOP3[0][1] + 1}", "matches no referenced fact"),                                  # glued to letters
    ("the top3 products", "matches no referenced fact"),
    (f"{V6} in {M6}", "is not one of the referenced trend facts"),                          # month not referenced
    ("2026-13", "is not a month"),
    (f"{TOP3[1][1]}", "matches no referenced fact"),                                        # a fact, not referenced
])
def test_anything_else_is_rejected_with_a_reason(text, error):
    errors = check_numbers(text, FACTS, REFS)
    assert errors and any(error in e for e in errors), errors


# GPT review 3b: product names that contain digits.
DIGIT_TOP3 = [["iPhone 15", 4200000], ["Model 3", 3100000], ["Galaxy S24", 2800000]]
DIGIT_FACTS = build_facts(DIGIT_TOP3, TREND)
NAMES = ["top3.1.product", "top3.2.product", "top3.top2_share_of_top3_pct"]
DIGIT_SHARE = round_half_up(DIGIT_FACTS["top3.top2_share_of_top3_pct"]["value"], 1)


def test_digits_inside_a_referenced_product_name_are_backed_by_that_fact():
    assert check_numbers(f"iPhone 15 and Model 3 bring {DIGIT_SHARE}% of the leaders' revenue.", DIGIT_FACTS, NAMES) == []
    assert check_numbers("Bundle iPhone 15 with Model 3.", DIGIT_FACTS, NAMES) == []
    recs = template_recommendations(DIGIT_TOP3, TREND)               # the template writer, same rules
    assert validate_recommendations({"recommendations": recs}, DIGIT_FACTS) == (recs, [])
    # one name inside another: the longer is masked first, or "2024" would be left over
    nested = build_facts([["Model 3", 5], ["Model 3 2024", 4], ["X", 1]], [])
    assert check_numbers("Model 3 2024 trails Model 3.", nested, ["top3.1.product", "top3.2.product"]) == []


@pytest.mark.parametrize("text, refs, bad", [
    ("Model 3 sold 4 more units.", NAMES, "4"),                          # an unrelated number is still checked
    ("Galaxy S24 is third.", NAMES, "24"),                               # a product name that is not referenced
    ("Model 30 is next.", NAMES, "0"),                                   # not the exact name
    ("model 3 leads.", NAMES, "3"),                                      # re-cased: not the exact name
    ("iPhone 15 Pro leads.", ["top3.1.product"], None),                  # longer text around an exact name: fine
    ("iPhone 15 and iPhone 16.", ["top3.1.product"], "16"),
])
def test_only_exact_referenced_names_are_masked(text, refs, bad):
    errors = check_numbers(text, DIGIT_FACTS, refs)
    if bad is None:
        assert errors == []
    else:
        assert errors and any(e.startswith(bad) or f"'{bad}'" in e for e in errors), errors


def test_numbers_in_the_action_are_checked_too():
    # GPT review P1: action is rendered, so it is validated like text.
    recs = good_recs()
    recs[0]["action"] = f"Cut the {P1} price by 10% for a week."
    out, errors = validate_recommendations({"recommendations": recs}, FACTS)
    assert out is None and any(e.startswith("recommendation 1 action:") for e in errors)


@pytest.mark.parametrize("mutate, error", [
    (lambda r: r[:1], "1 recommendations"),
    (lambda r: r * 3, "6 recommendations"),
    (lambda r: [r[0], dict(r[0])], "repeats an earlier"),
    (lambda r: [dict(r[0], facts=[]), r[1]], "at least one fact id"),
    (lambda r: [dict(r[0], facts=r[0]["facts"] + ["top3.9.revenue"]), r[1]], "unknown fact ids"),
    (lambda r: [dict(r[0], text="two\nlines"), r[1]], "single lines"),
    (lambda r: [dict(r[0], action=""), r[1]], "'action' must be"),
])
def test_recommendation_structure_is_validated(mutate, error):
    out, errors = validate_recommendations({"recommendations": mutate(good_recs())}, FACTS)
    assert out is None and any(error in e for e in errors), errors


def test_the_template_writer_obeys_the_same_rules():
    recs = template_recommendations(TOP3, TREND)
    assert validate_recommendations({"recommendations": recs}, FACTS) == (recs, [])


# ---- the writer model ------------------------------------------------------------------------------

def submit(recs, id="w1", **kw):
    return reply("", input_tokens=1500, output_tokens=400, **kw,
                 tool_calls=[{"name": "SubmitRecommendations", "args": {"recommendations": recs}, "id": id}])


def state(top3=TOP3, trend=TREND):
    results = {"a": {"output": "top3", "value": top3, "iteration": 0},
               "b": {"output": "trend", "value": trend, "iteration": 0}}
    return {"iteration": 0, "goal": "Analyze penjualan.csv", "results": results}


def writer(tmp_path, script, attempts=3):
    cfg = copy.deepcopy(load_config())
    cfg["roles"]["writer"]["model"] = "fake:scripted"
    cfg["llm"]["base_delay"] = 0
    log = EventLog(tmp_path / "e.jsonl")
    model = ScriptedChatModel(script=list(script))
    fn = make_llm_synthesize(LLMCaller(cfg, "writer", log, model=model), ToolGate("orchestrator", ["write_file"], log),
                             Memo(tmp_path / "memo.sqlite"), log, str(tmp_path), tokens=20_000, usd=1.0,
                             attempts=attempts)
    return fn, model, log


def kinds(log, event):
    return [e for e in log.read() if e["event"] == event]


def failing(tmp_path):
    return {c["id"] for c in run_checks(tmp_path / "laporan.md", T) if not c["ok"]}


def test_valid_recommendations_make_a_report_that_passes_every_check(tmp_path):
    fn, model, log = writer(tmp_path, [submit(good_recs())])
    out = fn(state())
    assert len(model.calls) == 1 and out["tokens_used"] == 1900
    assert failing(tmp_path) == set()
    prov = json.loads((tmp_path / "laporan.provenance.json").read_text())
    assert prov["writer"] == "fake:scripted" and prov["recommendations"] == good_recs()
    text = (tmp_path / "laporan.md").read_text()
    assert f"- {P1}: {TOP3[0][1]}" in text and " Aksi: " in text
    assert len(kinds(log, "recs_accepted")) == 1


def test_rejected_numbers_go_back_to_the_model_with_the_errors(tmp_path):
    bad = good_recs()
    bad[0]["text"] = bad[0]["text"].replace(f"{round_half_up(SHARE, 1)}%", "80%")
    fn, model, log = writer(tmp_path, [submit(bad), submit(good_recs(), id="w2")])
    fn(state())
    assert len(model.calls) == 2
    answer = model.calls[1]["messages"][-1]
    assert isinstance(answer, ToolMessage) and "80% matches no referenced percentage fact" in answer.content
    assert [e["step"] for e in kinds(log, "recs_invalid")] == [0] and failing(tmp_path) == set()


def test_a_reply_without_the_tool_is_answered_and_costs_an_attempt(tmp_path):
    fn, model, _ = writer(tmp_path, [reply("Here are my ideas..."), submit(good_recs())])
    fn(state())
    assert isinstance(model.calls[1]["messages"][-1], HumanMessage) and failing(tmp_path) == set()


def test_invalid_every_time_writes_no_recommendations_and_says_why(tmp_path):
    bad = good_recs()[:1]
    fn, model, log = writer(tmp_path, [submit(bad, id=f"w{i}") for i in range(3)])
    fn(state())
    assert len(model.calls) == 3
    (failed,) = kinds(log, "synthesize_failed")
    assert "invalid after 3 attempts" in failed["reason"]
    assert "## Rekomendasi\n" in (tmp_path / "laporan.md").read_text()
    assert {"recs_count", "recs_rubric"} <= failing(tmp_path)


def test_a_truncated_reply_is_not_used_and_not_retried(tmp_path):
    fn, model, log = writer(tmp_path, [submit(good_recs(), stop_reason="max_tokens"), submit(good_recs())])
    fn(state())
    assert len(model.calls) == 1
    assert "output_truncated" in kinds(log, "synthesize_failed")[0]["reason"]
    assert json.loads((tmp_path / "laporan.provenance.json").read_text())["recommendations"] == []


def test_no_model_call_when_a_worker_output_is_missing(tmp_path):
    fn, model, log = writer(tmp_path, [submit(good_recs())])
    out = fn(state(trend=[]))
    assert model.calls == [] and out["tokens_used"] == 0 and len(kinds(log, "synthesize_skipped")) == 1


def test_a_committed_reply_is_replayed_not_bought_again(tmp_path):
    bad = good_recs()[:1]
    fn, model, log = writer(tmp_path, [submit(bad), submit(good_recs(), id="w2")])
    fn(state())
    report = (tmp_path / "laporan.md").read_text()
    fn(state())                                     # same node run again, e.g. after a crash
    assert len(model.calls) == 2 and (tmp_path / "laporan.md").read_text() == report
    assert [e["step"] for e in kinds(log, "step_replayed")] == [0, 1]


def test_a_replayed_truncated_reply_stays_unused(tmp_path):
    fn, model, log = writer(tmp_path, [submit(good_recs(), stop_reason="max_tokens")])
    fn(state())
    fn(state())
    assert len(model.calls) == 1 and len(kinds(log, "synthesize_failed")) == 2
    assert json.loads((tmp_path / "laporan.provenance.json").read_text())["recommendations"] == []


def test_recommendations_grounded_in_wrong_worker_values_fail_against_the_data(tmp_path):
    # The writer is checked against the workers' facts; the evaluator re-checks against the data.
    wrong_top3 = [TOP3[0], [TOP3[1][0], TOP3[1][1] + 300_000], TOP3[2]]
    wrong_share = build_facts(wrong_top3, TREND)["top3.top2_share_of_top3_pct"]["value"]
    recs = good_recs()
    recs[0]["text"] = recs[0]["text"].replace(f"{round_half_up(SHARE, 1)}%", f"{round_half_up(wrong_share, 1)}%")
    fn, _, log = writer(tmp_path, [submit(recs)])
    fn(state(top3=wrong_top3))
    assert len(kinds(log, "recs_accepted")) == 1                 # consistent with what the workers said
    assert {"recs_grounded", "top3_amounts"} <= failing(tmp_path)  # but not with the data


# ---- in the graph ------------------------------------------------------------------------------

def test_llm_synthesize_runs_in_the_graph_and_is_budgeted(tmp_path):
    from harness.budget import node_usd_estimates
    cfg = copy.deepcopy(load_config())
    assert node_usd_estimates(cfg)["synthesize"] == 0.0           # fake: no model call, M1/M2 figures unchanged
    cfg["impl"]["synthesize"] = "llm"
    cfg["roles"]["writer"]["model"] = "fake:scripted"
    cfg["llm"]["base_delay"] = 0
    assert node_usd_estimates(cfg)["synthesize"] == pytest.approx(8000 * 5.00 / 1e6)   # fake:scripted, output rate
    model = ScriptedChatModel(script=[submit(good_recs())])
    r = run_task(goal="x", scenario="pass", run_id="t", runs_dir=tmp_path, cfg=cfg, models={"writer": model})
    assert r["status"] == "DONE" and len(model.calls) == 1
    evs = [json.loads(l) for l in (tmp_path / "t" / "events.jsonl").read_text().splitlines()]
    (call,) = [e for e in evs if e["event"] == "llm_call"]
    assert call["node"] == "synthesize" and call["role"] == "writer"
