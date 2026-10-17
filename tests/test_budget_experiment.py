"""The budget experiment (docs/reviews/DESIGN_BUDGET_45K.md): the two arms differ only in attempt_tokens, the contract
copies only in their id and run cap, and the harness's own admission gives both arms the same attempts except in the
pathological case the design names."""
import copy
import json
import tempfile
from pathlib import Path

import pytest
import yaml

from evals import runner as ev

ROOT = Path(__file__).resolve().parent.parent
EXP = ROOT / "evals" / "budget_v1"
NANO = 1_000_000_000


def config(name):
    return yaml.safe_load((EXP / f"config_{name}.yaml").read_text(encoding="utf-8"))


def without(c, *paths):
    c = copy.deepcopy(c)
    for section, key in paths:
        del c[section][key]
    return c


def test_the_arms_differ_from_config_yaml_only_in_attempt_tokens_and_the_run_cap():
    base = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    # Keys added to config.yaml after the experiment ran; the arms' configs are kept as they were run.
    # sandbox.environments: M6 W1 (named sandbox environments, unused by these arms' contracts).
    del base["sandbox"]["environments"]
    keys = [("code_task", "attempt_tokens"), ("budget", "max_usd")]
    for name, tokens in (("30k", 30000), ("45k", 45000)):
        c = config(name)
        assert c["code_task"]["attempt_tokens"] == tokens and c["budget"]["max_usd"] == 1.0
        assert without(c, *keys) == without(base, *keys), name
    assert without(config("30k"), keys[0]) == without(config("45k"), keys[0])     # the single variable


def test_the_contract_copies_differ_only_in_id_and_run_cap():
    for k in "abc":
        orig = json.loads((ROOT / f"fixtures/contracts/ledger_terms_{k}.json").read_text(encoding="utf-8"))
        cap1 = json.loads((ROOT / f"fixtures/contracts/ledger_cap1_{k}.json").read_text(encoding="utf-8"))
        assert cap1["contract"] == f"ledger_cap1_{k}" and cap1["limits"]["max_usd"] == 1.0
        for c in (orig, cap1):
            c.pop("contract")
            c["limits"].pop("max_usd")
        assert cap1 == orig, k


def test_the_manifest_reuses_the_search_v1_scripts_and_keeps_labels_out_of_the_contracts():
    m = ev.load_manifest(EXP / "manifest.json")
    s = {t["id"][-1]: t for t in ev.load_manifest(ROOT / "evals/search_v1/manifest.json")["tasks"]}
    assert [t["id"] for t in m["tasks"]] == ["ledger_cap1_a", "ledger_cap1_b", "ledger_cap1_c"]
    for t in m["tasks"]:
        assert t["reference"] == s[t["id"][-1]]["reference"] and t["wrong"] == s[t["id"][-1]]["wrong"]
        text = (ROOT / t["contract"]).read_text(encoding="utf-8")
        for word in (t["category"], "expected", "reference", "wrong"):
            assert word not in text
    assert ev.benchmark_hash(EXP / "manifest.json") != ev.benchmark_hash(ROOT / "evals/search_v1/manifest.json")


# ---- admission with the harness's own functions (design section 3) ----------------------------------------------

def lim(name):
    from codetask.run import settings
    c = config(name)
    c["roles"]["coder"]["model"] = "anthropic:claude-sonnet-5-5"
    contract = json.loads((ROOT / "fixtures/contracts/ledger_cap1_a.json").read_text(encoding="utf-8"))
    return settings(c, contract)


def admitted(limits, spends):
    """Is one more attempt admitted after earlier attempts that spent `spends` (USD) by the ledger?"""
    from codetask.run import admission
    from harness.events import EventLog
    with tempfile.TemporaryDirectory() as t:
        log = EventLog(Path(t) / "e.jsonl")
        for i, usd in enumerate(spends):
            log.emit("llm_call_started", call_id=f"c{i}", node="agent", task="x", iteration=i, step=0,
                     worst_tokens=1, worst_usd_nano=round(usd * NANO))
            log.emit("llm_call", call_id=f"c{i}", status="ok", node="agent", task="x", iteration=i, step=0,
                     tokens=1000, usd_nano=round(usd * NANO))
        return admission(log, limits) is None


@pytest.mark.parametrize("name,reservation,edge", [("30k", 0.30, 0.70), ("45k", 0.45, 0.55)])
def test_one_more_attempt_is_admitted_exactly_while_the_actual_spend_fits(name, reservation, edge):
    limits = lim(name)
    assert limits["attempt_usd"] == pytest.approx(reservation) and limits["max_usd"] == 1.0
    assert admitted(limits, [edge]) and not admitted(limits, [edge + 0.01])
    assert admitted(limits, [edge / 2, edge / 2])                  # spend, not earlier reservations, is what counts


def test_both_arms_get_three_attempts_at_a_plausible_spend_and_only_the_pathological_45k_case_loses_the_third():
    plausible = {"30k": 30000 * (0.95 * 2 + 0.05 * 10) / 1e6, "45k": 45000 * (0.95 * 2 + 0.05 * 10) / 1e6}
    for name in ("30k", "45k"):
        assert admitted(lim(name), [plausible[name]] * 2), name
    assert admitted(lim("30k"), [0.30, 0.30])                      # pathological: all billed at the output price
    assert not admitted(lim("45k"), [0.45, 0.45])
