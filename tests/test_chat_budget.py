"""SPEC_BUDGET_V2 part 1: the read only route of the meters and the page that shows them (text only, unknown never zero)."""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import test_budget as tb  # noqa: E402
import test_chat_actions as t  # noqa: E402
from router import budget as bg  # noqa: E402

JS = (HERE.parent / "router" / "chat_static" / "app.js").read_text()
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def svc_with(tmp_path, budget):
    cfg = json.loads(json.dumps(t.CFG))
    if budget is not None:
        cfg["chat"] = {**cfg.get("chat", {}), "budget": budget}
    return t.Service(tmp_path, cfg=cfg)


def test_the_route_answers_off_without_the_section_and_with_the_numbers_with_it(tmp_path):
    s = svc_with(tmp_path, None)
    try:
        assert s.request("GET", "/api/budget")[1] == {"off": True}
    finally:
        s.stop()
    (tmp_path / "b").mkdir()
    s = svc_with(tmp_path / "b", {"daily_usd": 1.0, "monthly_usd": 30.0, "warn_at": 0.8})
    try:
        now = s.clock()
        tb.ledger(s.jobs, "j20261128_090000_aaaa", [tb.started("a", now - 5, 5), tb.done("a", now - 4, 250_000_000)])
        status, out = s.request("GET", "/api/budget")
        assert status == 200 and out["day"]["limit_usd"] == 1.0 and out["month"]["limit_usd"] == 30.0 and out["unknown"] is None
        assert out["day"]["spent_usd"] == pytest.approx(0.25) and out["month"]["spent_usd"] == pytest.approx(0.25) and "listed sources" in out["note"]
    finally:
        s.stop()


def test_a_bad_section_turns_the_meters_off_with_the_reason_and_nothing_else_breaks(tmp_path):
    s = svc_with(tmp_path, {"daily_usd": 5.0, "monthly_usd": 1.0, "warn_at": 0.8})
    try:
        status, out = s.request("GET", "/api/budget")
        assert status == 200 and out["off"] is True and "above monthly_usd" in out["problem"]
        assert s.request("GET", "/api/cap")[0] == 200                      # the old cap still answers
    finally:
        s.stop()


def test_the_route_is_read_only_and_the_meters_never_write_into_a_ledger(tmp_path):
    s = svc_with(tmp_path, {"daily_usd": 1.0, "monthly_usd": 30.0, "warn_at": 0.8})
    try:
        p = tb.ledger(s.jobs, "j20261128_090000_aaaa", [tb.started("a", s.clock() - 5, 5)], newline=False)          # a ledger the harness would repair by writing a newline
        before = p.read_bytes()
        s.request("GET", "/api/budget")
        assert p.read_bytes() == before
        assert s.request("POST", "/api/budget", {})[0] in (404, 405)
    finally:
        s.stop()


def test_serve_warms_the_ledgers_before_it_listens():
    src = (HERE.parent / "router" / "chat.py").read_text()
    serve = src.split("def serve(")[1]
    assert serve.index("actions.budget.warm()") < serve.index("srv.serve_forever()") and "except Exception" in serve.split("srv = server(")[0]


def test_the_page_reads_the_route_and_draws_only_text(tmp_path):
    assert 'get("/api/budget")' in JS and "budget-chip" in JS
    block = JS.split("function budgetWindow")[1].split("var capInfo")[0]
    assert "innerHTML" not in block and "innerHTML" not in JS
    assert "does not stop anything yet" in block and "It is not zero." in block


@needs_node
def test_the_cost_tab_shows_both_meters_and_never_draws_unknown_as_zero():
    out = json.loads(subprocess.run(["node", str(HERE / "chat_ui_smoke_nav.js"), str(HERE.parent / "router" / "chat_static" / "app.js")], capture_output=True, text=True, timeout=60).stdout)
    assert out["chip"] == ["", "", "Today $0.35 of $1.00", "Today ?", "Today ?"]
    assert "Spent (daily and monthly budget)" in out["budgetNull"] and "Loading" in out["budgetNull"]
    assert "The budget meters are off." in out["budgetOff"]
    ok = out["budgetOk"]
    assert "Today: $0.35 of $1.00" in ok and "This month: $7.55 of $30.00" in ok and "does not stop anything yet" in ok and "<progress.pbar>" in ok
    assert "By platform: OpenRouter $0.15 · DeepSeek under $0.01" in ok and "By source: Argus jobs $0.15 · Experiments $0.20" in ok and "Not found: Gone" in ok
    assert "pbar warn" in out["budgetWarn"] and "Today: $0.90 of $1.00" in out["budgetWarn"] and out["budgetWarn"].count("pbar warn") == 1
    u = out["budgetUnknown"]
    assert "Today: unknown" in u and "This month: unknown" in u and "It is not zero." in u and "unpriced call, j<b>1</b>" in u and "$0.00" not in u.split("Spent (daily")[1].split("Recorded")[0]
