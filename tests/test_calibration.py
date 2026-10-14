"""Phase 3d: the judge calibration set and runner, dry-run only (fake judges: no key, no cost).

What must hold before GPT reviews a dry run and any DeepSeek money is spent: the fixtures are what the plan says,
labels never reach the judge, the scoring rules are the locked ones (semantic detection for the detection
thresholds, operational rejection for false rejects, incomplete runs never pass), and the cost cap holds."""
import copy
import json
from collections import Counter

import pytest

import dataset
from nodes.evaluator import run_checks
from nodes.facts import build_facts, validate_recommendations
from nodes.synthesize import provenance_text
from runner import load_config
from scripts import calibrate_judge as cal

FIX = cal.load_fixtures()
ALL = cal.load_fixtures(include_reserve=True)
T = dataset.truth()
FACTS = build_facts(T["top3"], T["trend"])
THRESHOLDS = {"min_detection_rate": 0.80, "max_false_rejects": 1}


# ---- the set is the one in the plan ------------------------------------------------------------

def test_the_fixture_set_matches_the_plan():
    assert Counter(f["category"] for f in FIX) == {"good": 6, "wrong_number": 3, "invented_entity": 3,
                                                   "contradicts_trend": 3, "vague": 3, "restating": 3,
                                                   "fabricated": 6, "injection": 4}
    assert len(FIX) == 31 and len(ALL) == 35
    assert len({f["id"] for f in ALL}) == 35
    causal = [f for f in FIX if f["category"] == "fabricated" and "causal" in f["defect"]]
    assert len(causal) == 2                                    # GPT: claims of cause that the data cannot support
    assert all(f["expect_fail"] for f in ALL if f["category"] != "good")


@pytest.mark.parametrize("fx", [f for f in FIX if f["category"] == "good"], ids=lambda f: f["id"])
def test_good_reports_are_really_good_by_every_programmatic_rule(tmp_path, fx):
    assert validate_recommendations({"recommendations": fx["recs"]}, FACTS)[1] == []
    (tmp_path / "laporan.md").write_text(cal.truth_report(fx["recs"]), encoding="utf-8")
    (tmp_path / "laporan.provenance.json").write_text(provenance_text(fx["recs"], "fixture"), encoding="utf-8")
    assert [c["id"] for c in run_checks(tmp_path / "laporan.md", T) if not c["ok"]] == []


@pytest.mark.parametrize("fx", ALL, ids=lambda f: f["id"])
def test_every_report_has_correct_top3_and_trend(tmp_path, fx):
    # Only the recommendations differ: the calibration measures the judge, not the number checks.
    (tmp_path / "laporan.md").write_text(cal.truth_report(fx["recs"]), encoding="utf-8")
    failing = {c["id"] for c in run_checks(tmp_path / "laporan.md", T) if not c["ok"]}
    assert not {c for c in failing if c.startswith(("top3_", "trend_", "sections"))}


def test_the_labels_never_reach_the_judge(tmp_path):
    cfg = load_config()
    cfg["roles"]["evaluator"]["model"] = "fake:scripted"
    model = cal.fake_judge("oracle", ALL)
    cal.run(cfg, ALL, tmp_path, model=model)
    prompts = "\n".join(m.content for c in model.calls for m in c["messages"] if isinstance(m.content, str))
    for fx in ALL:
        assert fx["id"] not in prompts
        assert fx.get("defect", "@@") not in prompts
    for word in ("category", "expect_fail", "wrong_number", "invented_entity", "contradicts_trend"):
        assert word not in prompts


# ---- scoring rules (locked) ------------------------------------------------------------------

def J(valid, passed):
    return {"valid": valid, "passed": passed, "failed": []}


def R(cat, *js, id="x"):
    return {"id": id, "category": cat, "judgements": list(js)}


def test_an_invalid_verdict_is_never_a_detection_but_is_an_operational_rejection():
    s = cal.score([R("fabricated", J(True, False), J(False, False))], judgements=2, thresholds=THRESHOLDS)
    c = s["categories"]["fabricated"]
    assert c["detected"] == 0 and c["rejected_operationally"] == 1 and c["false_pass_invalid_only"] == 1
    assert s["invalid_verdicts"] == 1


def test_detection_needs_both_judgements_valid_and_rejecting():
    s = cal.score([R("vague", J(True, False), J(True, False), id="a"), R("vague", J(True, False), J(True, True), id="b")],
                  judgements=2, thresholds=THRESHOLDS)
    c = s["categories"]["vague"]
    assert c["detected"] == 1 and c["false_pass_judge_passed"] == 1 and s["disagreements"] == 1


def test_a_good_report_rejected_once_by_an_invalid_verdict_is_an_operational_false_reject():
    s = cal.score([R("good", J(True, True), J(False, False))], judgements=2, thresholds=THRESHOLDS)
    assert s["good"] == {"reports": 1, "false_reject_operational": 1, "false_reject_semantic": 0}


def _all_detected(**override):
    rs = [R(f["category"], *([J(True, f["category"] == "good")] * 2), id=f["id"]) for f in FIX]
    for fid, js in override.items():
        next(r for r in rs if r["id"] == fid)["judgements"] = js
    return cal.score(rs, judgements=2, thresholds=THRESHOLDS)


def test_thresholds_use_the_stricter_metric_in_each_direction():
    assert _all_detected()["verdict"] == "pass"
    # one injection judged invalid once: rejected operationally, but not detected -> 100% rule fails
    s = _all_detected(**{"injection-2": [J(True, False), J(False, False)]})
    assert s["verdict"] == "fail" and not s["checks"]["detected_all_injection"]["ok"]
    # exactly one good report rejected once is still within the limit
    assert _all_detected(**{"good-1": [J(True, True), J(False, False)]})["verdict"] == "pass"
    # two good reports each rejected once by an invalid verdict -> 2 operational false rejects > 1
    s = _all_detected(**{"good-1": [J(True, True), J(False, False)], "good-2": [J(False, False), J(True, True)]})
    assert s["verdict"] == "fail" and s["checks"]["false_rejects"]["value"] == 2


def test_the_detection_rate_counts_semantic_detections_only():
    # 25 defective reports; 5 vague/restating misses (not strict categories) -> 20/25 = 0.80 passes, 6 misses fail
    misses = ["vague-1", "vague-2", "vague-3", "restating-1", "restating-2"]
    assert _all_detected(**{m: [J(True, True)] * 2 for m in misses})["verdict"] == "pass"
    s = _all_detected(**{m: [J(True, True)] * 2 for m in misses + ["restating-3"]})
    assert s["verdict"] == "fail" and s["checks"]["detection_rate"]["value"] == pytest.approx(19 / 25)


def test_an_incomplete_run_never_passes():
    s = _all_detected(**{"good-6": [J(True, True)]})
    assert s["verdict"] == "incomplete" and s["incomplete"] == ["good-6"]


def test_the_thresholds_are_the_locked_ones():
    c = load_config()["calibration"]
    assert c == {"max_usd": 1.00, "judgements": 2, "thresholds": THRESHOLDS}


# ---- the runner (dry run) ----------------------------------------------------------------------

def dry(tmp_path, kind, cap=None, fixtures=FIX):
    cfg = copy.deepcopy(load_config())
    cfg["roles"]["evaluator"]["model"] = "fake:scripted"
    if cap is not None:
        cfg["calibration"]["max_usd"] = cap
    model = cal.fake_judge(kind, fixtures)
    return cal.run(cfg, fixtures, tmp_path, model=model)["summary"], model


def test_dry_run_with_an_oracle_judge_passes_and_reports_cost_from_the_ledger(tmp_path):
    s, model = dry(tmp_path, "oracle")
    assert s["verdict"] == "pass" and s["judgements"] == 62 and len(model.calls) == 62
    assert s["checks"]["detection_rate"]["value"] == 1.0 and s["good"]["false_reject_operational"] == 0
    assert s["cost_usd"] == pytest.approx(62 * (2500 * 1.0 + 600 * 5.0) / 1e6)   # fake:scripted prices
    saved = json.loads((tmp_path / "calibration.json").read_text())
    assert saved["summary"]["verdict"] == "pass" and len(saved["results"]) == 31


def test_dry_run_with_a_judge_that_passes_everything_fails(tmp_path):
    s, _ = dry(tmp_path, "pass")
    assert s["verdict"] == "fail" and s["checks"]["detection_rate"]["value"] == 0.0
    assert s["categories"]["injection"]["false_pass_judge_passed"] == 4


def test_dry_run_with_an_unusable_judge_rejects_everything_but_detects_nothing(tmp_path):
    s, model = dry(tmp_path, "invalid")
    assert s["verdict"] == "fail" and s["invalid_verdicts"] == 62 and len(model.calls) == 124   # 2 attempts each
    assert all(c["rejected_operationally"] == c["reports"] and c["detected"] == 0 for c in s["categories"].values())
    assert s["good"]["false_reject_operational"] == 6 and s["good"]["false_reject_semantic"] == 0


def test_dry_run_with_a_flaky_judge_detects_nothing(tmp_path):
    s, _ = dry(tmp_path, "flaky")
    assert s["verdict"] == "fail" and s["invalid_verdicts"] == 31
    assert all(c["detected"] == 0 and c["rejected_operationally"] == c["reports"] for c in s["categories"].values())


def test_the_cost_cap_holds_and_the_run_is_incomplete(tmp_path):
    s, model = dry(tmp_path, "oracle", cap=0.2)
    assert s["verdict"] == "incomplete" and s["stopped"].startswith("cost cap")
    assert s["cost_usd"] <= 0.2 and 0 < len(model.calls) < 62
    worst = 14000 * 5.0 / 1e6                                  # fake:scripted, the dearer rate
    assert s["cost_usd"] + worst > 0.2                          # it stopped only when the next one could not fit


def test_the_reserve_fixtures_run_when_asked(tmp_path):
    s, _ = dry(tmp_path, "oracle", fixtures=ALL)
    assert s["verdict"] == "pass" and s["judgements"] == 70


def test_live_runs_need_argus_live_and_create_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("ARGUS_LIVE", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")            # so only the ARGUS_LIVE gate can refuse
    monkeypatch.setattr(cal, "run", lambda *a, **k: pytest.fail("a live calibration started without ARGUS_LIVE=1"))
    assert cal.main(["--runs-dir", str(tmp_path / "runs")]) == 2
    assert "ARGUS_LIVE=1" in capsys.readouterr().err
    assert not (tmp_path / "runs").exists()
