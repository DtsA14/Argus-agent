"""The paired number reader trial (C9, 2026-11-24): the hard sets (`build --sets v2`), `score --pair` and `t3b-run --reader-model`. No model, no Docker; the readings here are written by the tests."""
import json
import sys
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import t3b_fixtures as t3  # noqa: E402

from models.fake import CallableChatModel  # noqa: E402
from router import job as rj  # noqa: E402
from router import t3b_run as tr  # noqa: E402
from runner import load_config  # noqa: E402

DEFECTS = ["d6", "k1", "k2", "k3", "k4", "k5", "k6", "k7", "k8", "k9", "h1", "h2"]
GOODS = [f"m{i}" for i in range(1, 11)] + ["g9", "g10"]


@pytest.fixture
def built(tmp_path):
    root = tmp_path / "t3b2"
    ids, h = t3.build(root, seed=1, sets="v2")
    return root, ids, h, json.loads((t3.keydir(root) / t3.KEY_FILE).read_text())["sets"]


def sha_of(root, jid):
    return t3.bundle(root, jid)[1]["bundle_sha256"]


def read(root, key, run, verdict_of):
    for jid, k in key.items():
        v = verdict_of(k)
        src = ["hanya tulisan penulis" if k["set"] in ("k8",) and v == "concerns" else "permintaan Atha"]
        note = f"the right number is {t3.NEED[k['set']][0]}" if v == "concerns" and k["kind"] == "defect" else "checked"
        t3.record(root, jid, run, sha_of(root, jid), v, src, note, f"reader-{run}")


def right(k):
    return "concerns" if k["kind"] == "defect" else "ok"


def score(root, h, **kw):
    return t3.score(root, h, pair=True, **kw)


def test_the_hard_sets_are_twelve_defects_and_twelve_good_with_opaque_ids_and_the_real_history_sets(built):
    root, ids, h, key = built
    assert len(ids) == 24 and len(set(ids)) == 24
    assert sorted(k["set"] for k in key.values() if k["kind"] == "defect") == sorted(DEFECTS)
    assert sorted(k["set"] for k in key.values() if k["kind"] == "good") == sorted(GOODS)
    assert not any(k["set"] in str(Path(root)) for k in key.values())


def test_every_example_of_the_hard_sets_is_computed_from_the_shop_code_defects_differ_and_good_ones_match():
    ns = {}
    exec(t3.SHOP2, ns)
    for spec in t3.SETS_V2:
        if spec[8:] and spec[8].get("history") or not (spec[8:] and spec[8].get("shop") == "v2"):
            continue
        e = spec[7][0]
        assert (eval(e["run"], ns) == e["expect"]) is (spec[1] == "good"), spec[0]


def test_what_a_defect_reading_must_say_is_the_true_value_of_its_example():
    ns = {}
    exec(t3.SHOP2, ns)
    for spec in t3.SETS_V2:
        if spec[1] != "defect" or not (spec[8:] and spec[8].get("shop") == "v2") or spec[0] in ("k8", "k9"):
            continue
        true = eval(spec[7][0]["run"], ns)
        need = t3.NEED[spec[0]]
        assert any(t in str(int(true)) for t in need) and str(true) != str(spec[7][0]["expect"]), spec[0]


def test_a_hard_set_job_carries_the_hard_shop_and_readme_and_a_history_set_keeps_its_own(built):
    root, ids, h, key = built
    by = {k["set"]: jid for jid, k in key.items()}
    src = lambda jid: root / "jobs" / jid / "runs" / f"{jid}-w1" / "source"  # noqa: E731
    assert "def holding_days" in (src(by["k1"]) / "src" / "shop.py").read_text() and "Hari tahan" in (src(by["k1"]) / "README.md").read_text()
    assert (src(by["h1"]) / "risk_management" / "risk_manager.py").exists() and not (src(by["h1"]) / "src").exists()
    assert "def remaining" in (src(by["d6"]) / "src" / "shop.py").read_text()


def test_the_v1_sets_are_what_build_makes_without_sets(tmp_path):
    ids, h = t3.build(tmp_path / "a", seed=1)
    assert len(ids) == len(t3.SETS)


def test_a_defect_caught_by_one_of_the_two_readers_passes_the_pair(built):
    root, ids, h, key = built
    read(root, key, 1, lambda k: "ok" if k["set"] == "k5" else right(k))                     # reader 1 misses k5
    read(root, key, 2, right)
    ok, lines = score(root, h)
    assert ok is True and lines[-1] == "PASS" and any("run 1 1, run 2 0" in l for l in lines)


def test_a_defect_both_readers_miss_fails_the_pair(built):
    root, ids, h, key = built
    for run in (1, 2):
        read(root, key, run, lambda k: "ok" if k["set"] == "d6" else right(k))
    ok, lines = score(root, h)
    assert ok is False and any(l.startswith("d6 ") and "MISSED" in l for l in lines) and any(l.startswith("FAIL (a)") for l in lines)


def test_the_misses_of_one_reader_are_not_a_condition_in_pair_mode_but_are_in_the_single_rule(built):
    root, ids, h, key = built
    read(root, key, 1, lambda k: "ok" if k["set"] in ("k1", "k2", "k3") else right(k))      # reader 1 misses three, reader 2 catches all
    read(root, key, 2, right)
    assert score(root, h)[0] is True
    assert t3.score(root, h)[0] is False                                                       # the single rule: 3 of 24 readings of defects missed, above 5%


def test_two_good_sets_flagged_pass_and_three_fail_in_pair_mode(built):
    root, ids, h, key = built
    flagged = {"m1", "m5"}
    read(root, key, 1, lambda k: "concerns" if k["set"] in flagged else right(k))
    read(root, key, 2, right)
    ok, lines = score(root, h)
    assert ok is True and any("good sets flagged: at most 2" in l and "got 2" in l for l in lines)
    root2 = root.parent / "t3b3"
    ids2, h2 = t3.build(root2, seed=2, sets="v2")
    key2 = json.loads((t3.keydir(root2) / t3.KEY_FILE).read_text())["sets"]
    three = {"m1", "m5", "m9"}
    read(root2, key2, 1, lambda k: "concerns" if k["set"] in three else right(k))
    read(root2, key2, 2, right)
    ok2, lines2 = score(root2, h2)
    assert ok2 is False and any(l.startswith("FAIL (c)") for l in lines2)


def test_the_pair_rule_still_needs_the_real_history_sets_and_the_printed_hash(built):
    root, ids, h, key = built
    read(root, key, 1, right)
    read(root, key, 2, right)
    assert score(root, "0" * 64)[0] is False
    assert score(root, h, min_history=3)[0] is False


# ---- t3b-run --reader-model ---------------------------------------------------------------------------------------------------------------------

def reply(verdict="ok", note="checked"):
    body = json.dumps({"verdict": verdict, "sources": ["permintaan Atha"], "note": note})
    return AIMessage(content=body, usage_metadata={"input_tokens": 3000, "output_tokens": 300, "total_tokens": 3300},
                     response_metadata={"token_usage": {"prompt_tokens": 3000, "completion_tokens": 300, "cost": 0.004}})


def deps(shown):
    return rj.Deps(confirm=lambda t: (shown.append(t), True)[1], get_key=lambda: "sk-or-v1-testkey1234567890abcdef", isatty=lambda: True, echo=lambda *a, **k: None)


def test_the_reader_model_replaces_the_roles_model_with_its_price_and_is_named_in_the_screen_and_the_reading(built):
    root, ids, h, key = built
    shown = []
    model = CallableChatModel(respond=lambda m: reply())
    s = tr.run(root, 1, cfg=load_config(), deps=deps(shown), model=model, reader_model="hy4flash", limit=2, max_output=6000)
    assert s["calls"] == 2 and s["recorded"] == 2 and "tencent/hy4-flash" in shown[0] and s["model"].endswith("tencent/hy4-flash")
    reads = t3.read_all(root)
    assert {r["reader"] for r in reads} == {"argus:openrouter:tencent/hy4-flash"}


def test_an_unknown_reader_model_is_refused_before_any_call(built):
    root, ids, h, key = built
    model = CallableChatModel(respond=lambda m: reply())
    with pytest.raises(rj.Refused, match="--reader-model"):
        tr.run(root, 1, cfg=load_config(), deps=deps([]), model=model, reader_model="gpt")
    assert model.calls == []


def test_without_a_reader_model_the_roles_own_model_is_used(built):
    root, ids, h, key = built
    shown = []
    tr.run(root, 1, cfg=load_config(), deps=deps(shown), model=CallableChatModel(respond=lambda m: reply()), limit=1)
    assert "tencent/hy4-flash" not in shown[0] and "z-ai/glm-5.3" in shown[0]
