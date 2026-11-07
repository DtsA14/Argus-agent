"""SPEC_GATEWAY_PROVIDER PR 1: the gateway provider kind (models/gateway.py, harness/llm.py). The real ChatOpenAI client
talks to a fake OpenRouter on 127.0.0.1; the money goes through the real LLMCaller ledger."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from langchain_core.messages import HumanMessage

from harness.errors import LLMCallFailed
from harness.events import EventLog
from harness.llm import LLMCaller, Reservation, reconcile_ledger
from models import gateway
from models.registry import ConfigError, build_chat_model
from runner import load_config

KEY = "sk-or-v1-test-key-never-logged"
PAID = "openrouter:deepseek/deepseek-chat"
FREE = "openrouter:some/model:free"


def ok(provider="DeepSeek", cost=None, tin=1000, tout=100):
    usage = {"prompt_tokens": tin, "completion_tokens": tout, "total_tokens": tin + tout}
    if cost is not None:
        usage["cost"] = cost
    return 200, {"id": "gen-1", "object": "chat.completion", "created": 1, "model": "deepseek/deepseek-chat",
                 "provider": provider, "usage": usage,
                 "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "hi"}}]}


class Fake:
    """A fake gateway: answers from a queue, records every request (headers and body)."""

    def __init__(self):
        self.queue, self.requests = [], []
        fake = self

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                fake.requests.append({"path": self.path, "auth": self.headers.get("Authorization"), "body": body})
                status, out = fake.queue.pop(0) if fake.queue else ok()
                data = json.dumps(out).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):
                pass
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/api/v1"


@pytest.fixture
def fake(monkeypatch):
    f = Fake()
    monkeypatch.setenv("OPENROUTER_API_KEY", KEY)
    yield f
    f.server.shutdown()


def config(fake, model=PAID, role="gw", tools=None, free_roles=("gw",)):
    c = load_config()
    c["providers"]["openrouter"]["base_url"] = fake.url
    c["gateway_models"] = {PAID: {"upstream": ["deepseek"]}, FREE: {"upstream": ["chutes"], "free": True}}
    c["prices"][PAID] = {"input": 0.30, "output": 1.20}       # $0.0003 + $0.00012 for 1000 in, 100 out
    c["prices"][FREE] = {"input": 0, "output": 0}
    c["gateway"]["free_roles"] = list(free_roles)
    c["roles"][role] = {"model": model, "max_output_tokens": 200, "timeout_s": 10}
    if tools is not None:
        c["tools"][role] = tools
    c["budget"]["max_usd"] = 1.0
    c["llm"]["attempts"] = 3
    return c


def caller(cfg, tmp_path, role="gw"):
    log = EventLog(tmp_path / "events.jsonl")
    return LLMCaller(cfg, role, log, sleep=lambda s: None), log


def res():
    return Reservation(tokens=100_000, usd=1.0)


def events(log, name="llm_call"):
    return [e for e in log.read() if e["event"] == name]


# ---- the pin -----------------------------------------------------------------------------------------------------

def test_every_request_is_pinned_with_no_fallback(fake, tmp_path):
    c, log = caller(config(fake), tmp_path)
    c.call([HumanMessage("hello")], res())
    [r] = fake.requests
    assert r["path"] == "/api/v1/chat/completions" and r["body"]["model"] == "deepseek/deepseek-chat"
    assert r["body"]["provider"] == {"order": ["deepseek"], "only": ["deepseek"], "allow_fallbacks": False,
                                     "require_parameters": True, "data_collection": "deny"}
    assert "models" not in r["body"] and "route" not in r["body"] and "sort" not in r["body"]
    assert r["auth"] == f"Bearer {KEY}" and KEY not in (tmp_path / "events.jsonl").read_text()


def test_a_model_not_listed_is_refused_before_anything_is_sent(fake, tmp_path):
    cfg = config(fake, model="openrouter:other/model")
    cfg["prices"]["openrouter:other/model"] = {"input": 1, "output": 1}
    with pytest.raises(ConfigError, match="not in gateway_models"):
        caller(cfg, tmp_path)
    with pytest.raises(ConfigError, match="not in gateway_models"):
        build_chat_model(cfg, "gw")
    assert fake.requests == []


@pytest.mark.parametrize("key", ["provider", "models", "route", "sort"])
def test_role_params_cannot_change_the_pin(fake, tmp_path, key):
    cfg = config(fake)
    cfg["roles"]["gw"]["params"] = {"extra_body": {key: ["x"]}}
    with pytest.raises(ConfigError, match=f"extra_body.{key} is set by the gateway pin"):
        build_chat_model(cfg, "gw")


@pytest.mark.parametrize("bad", [{"upstream": []}, {"upstream": "deepseek"}, {"upstream": [""]},
                                 {"upstream": ["deepseek"], "free": "yes"}])
def test_a_malformed_gateway_entry_is_refused(fake, tmp_path, bad):
    cfg = config(fake)
    cfg["gateway_models"][PAID] = bad
    with pytest.raises(ConfigError):
        caller(cfg, tmp_path)


def test_an_unsupported_vendor_is_refused(fake, tmp_path):
    cfg = config(fake)
    cfg["providers"]["openrouter"]["vendor"] = "omniroute"
    with pytest.raises(ConfigError, match="not supported"):
        caller(cfg, tmp_path)


def test_a_reply_served_outside_the_pin_is_paid_then_fails(fake, tmp_path):
    fake.queue = [ok(provider="Chutes", cost=0.0004)]
    c, log = caller(config(fake), tmp_path)
    r = res()
    with pytest.raises(LLMCallFailed, match="outside its pin"):
        c.call([HumanMessage("hello")], r)
    [e] = events(log)
    assert e["upstream_served"] == "Chutes" and r.used_nano == e["usd_nano"] == 420_000
    assert events(log, "pin_violated")[0]["served"] == "Chutes" and len(fake.requests) == 1   # never retried
    assert not events(log, "price_drift")                     # 0.0004 vs our 0.00042: within 10%


def test_a_reply_served_outside_the_pin_still_reports_its_price_drift(fake, tmp_path):
    fake.queue = [ok(provider="Chutes", cost=0.002)]
    c, log = caller(config(fake), tmp_path)
    with pytest.raises(LLMCallFailed):
        c.call([HumanMessage("hello")], res())
    assert events(log, "price_drift") and events(log, "pin_violated")


def test_a_reply_that_does_not_name_its_provider_is_marked_unverified(fake, tmp_path):
    fake.queue = [ok(provider=None)]
    c, log = caller(config(fake), tmp_path)
    c.call([HumanMessage("hello")], res())
    assert events(log)[0]["upstream_served"] is None and events(log, "pin_unverified")


@pytest.mark.parametrize("upstream, served, good", [
    (["deepseek"], "DeepSeek", True), (["deepinfra/fp8"], "DeepInfra", True), (["google-vertex"], "Google", True),
    (["deepseek"], "Chutes", False), (["deepinfra/fp8"], "Together", False), (["deepseek"], "!!", False),
    (["deepseek"], None, True)])
def test_the_serving_provider_is_matched_against_the_pin(upstream, served, good):
    assert gateway.served_ok(upstream, served) is good


# ---- money -------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("reported, charged, how", [
    (0.0006, 600_000, "gateway_reported"),          # the gateway billed more than our count: its cost
    (0.0003, 420_000, "actual"),                    # it billed less: ours (conservative)
    (None, 420_000, "actual"),                      # it did not say: ours
])
def test_the_charge_is_the_larger_of_our_count_and_the_gateway_cost(fake, tmp_path, reported, charged, how):
    fake.queue = [ok(cost=reported)]
    c, log = caller(config(fake), tmp_path)
    r = res()
    c.call([HumanMessage("hello")], r)
    [e] = events(log)
    assert e["usd_nano"] == charged == r.used_nano and e["charged"] == how
    assert e["usd_computed_nano"] == 420_000
    assert e["usd_reported_nano"] == (None if reported is None else round(reported * 1e9))
    assert reconcile_ledger(log.read())[1]["usd_nano"] == charged


@pytest.mark.parametrize("reported, drift", [(0.0006, True), (0.0003, True), (0.00044, False), (None, False)])
def test_a_cost_far_from_ours_is_reported_as_price_drift(fake, tmp_path, reported, drift):
    fake.queue = [ok(cost=reported)]
    c, log = caller(config(fake), tmp_path)
    c.call([HumanMessage("hello")], res())
    assert bool(events(log, "price_drift")) == drift


@pytest.mark.parametrize("cost", [-1, "0.1", True])
def test_a_malformed_reported_cost_is_ignored(fake, tmp_path, cost):
    fake.queue = [ok(cost=cost)]
    c, log = caller(config(fake), tmp_path)
    c.call([HumanMessage("hello")], res())
    [e] = events(log)
    assert e["usd_reported_nano"] is None and e["usd_nano"] == 420_000


@pytest.mark.parametrize("cost", [float("nan"), float("inf")])
def test_a_cost_that_is_not_finite_is_ignored(cost):
    msg = type("M", (), {"response_metadata": {"gateway_cost": cost, "gateway_provider": " "}})()
    assert gateway.reported(msg) == (None, None)


def test_an_unpriced_gateway_model_is_refused_with_a_finite_cap(fake, tmp_path):
    cfg = config(fake)
    del cfg["prices"][PAID]
    with pytest.raises(ConfigError, match="no price"):
        caller(cfg, tmp_path)
    assert fake.requests == []


def test_an_empty_balance_is_not_retried(fake, tmp_path):
    fake.queue = [(402, {"error": {"code": 402, "message": "Insufficient credits"}})]
    c, log = caller(config(fake), tmp_path)
    r = res()
    with pytest.raises(LLMCallFailed):
        c.call([HumanMessage("hello")], r)
    assert len(fake.requests) == 1 and events(log)[0]["status"] == "error" and r.used_nano > 0


def test_a_rate_limit_is_retried_on_the_same_model_only_and_never_by_the_sdk(fake, tmp_path):
    fake.queue = [(429, {"error": {"code": 429, "message": "Rate limit exceeded"}})] * 4
    c, log = caller(config(fake), tmp_path)
    with pytest.raises(LLMCallFailed, match="still failing after 4 attempts"):   # SPEC_RATE_LIMIT_RETRY R2
        c.call([HumanMessage("hello")], res())
    assert len(fake.requests) == 4 == len(events(log))          # one request per ledger attempt: no SDK retries
    assert {r["body"]["model"] for r in fake.requests} == {"deepseek/deepseek-chat"}


# ---- free models -------------------------------------------------------------------------------------------------

def test_a_free_model_is_used_only_by_a_listed_role(fake, tmp_path):
    with pytest.raises(ConfigError, match="gateway.free_roles"):
        caller(config(fake, model=FREE, free_roles=()), tmp_path)
    with pytest.raises(ConfigError, match="gateway.free_roles"):
        build_chat_model(config(fake, model=FREE, free_roles=()), "gw")
    assert fake.requests == []


@pytest.mark.parametrize("tool", ["list_files", "search_files", "read_file", "write_file", "edit_file",
                                  "run_validation", "read_docs"])
def test_a_free_model_never_reads_a_repository(fake, tmp_path, tool):
    with pytest.raises(ConfigError, match="reads repositories"):
        caller(config(fake, model=FREE, tools=[tool]), tmp_path)
    assert fake.requests == []


def test_a_free_model_is_recorded_free_and_may_collect_data(fake, tmp_path):
    fake.queue = [ok(provider="Chutes", cost=0)]
    c, log = caller(config(fake, model=FREE, tools=[]), tmp_path)
    c.call([HumanMessage("hello")], res())
    [e] = events(log)
    assert e["free"] is True and e["usd_nano"] == 0 and e["usd_computed_nano"] == 0
    assert fake.requests[0]["body"]["provider"]["data_collection"] == "allow"


def test_a_free_model_the_gateway_bills_is_charged(fake, tmp_path):
    fake.queue = [ok(provider="Chutes", cost=0.002)]
    c, log = caller(config(fake, model=FREE, tools=[]), tmp_path)
    r = res()
    c.call([HumanMessage("hello")], r)
    assert r.used_nano == 2_000_000 and events(log, "price_drift")


def test_a_paid_model_needs_no_free_role(fake, tmp_path):
    c, _ = caller(config(fake, free_roles=(), tools=["read_file"]), tmp_path)
    c.call([HumanMessage("hello")], res())
    assert fake.requests[0]["body"]["provider"]["data_collection"] == "deny"


def test_the_caller_checks_the_role_even_with_an_injected_model(fake, tmp_path):
    from models.fake import StrictScriptedChatModel
    cfg = config(fake, model=FREE, free_roles=())
    with pytest.raises(ConfigError, match="gateway.free_roles"):
        LLMCaller(cfg, "gw", EventLog(tmp_path / "e.jsonl"), model=StrictScriptedChatModel(script=[]))


def test_a_free_model_is_refused_for_the_code_task_role(fake, tmp_path):
    cfg = config(fake, model=FREE, tools=[])
    cfg["code_task"]["role"] = "gw"
    with pytest.raises(ConfigError, match="reads repositories"):
        caller(cfg, tmp_path)


def test_a_free_model_is_never_bound_to_a_tool_outside_the_free_list(fake, tmp_path):
    from codetask.tools import EditFile, ReadFile
    from research.stages import SubmitFindings, WebSearch
    c, log = caller(config(fake, model=FREE, tools=[]), tmp_path)
    for tool in (ReadFile, EditFile):
        with pytest.raises(ConfigError, match="may not be given"):
            c.call([HumanMessage("hello")], res(), tools=[WebSearch, tool])
    assert fake.requests == [] and events(log) == []
    fake.queue = [ok(provider="Chutes", cost=0)]
    c.call([HumanMessage("hello")], res(), tools=[WebSearch, SubmitFindings])
    assert len(fake.requests) == 1


def test_a_paid_model_may_be_bound_to_any_tool(fake, tmp_path):
    from codetask.tools import ReadFile
    c, _ = caller(config(fake, tools=["read_file"], free_roles=()), tmp_path)
    c.call([HumanMessage("hello")], res(), tools=[ReadFile])
    assert len(fake.requests) == 1


@pytest.mark.parametrize("model, price", [("openrouter:x/y:free", {"input": 1, "output": 1}),
                                          ("openrouter:x/y", {"input": 0, "output": 0})])
def test_a_model_that_looks_free_must_be_marked_free(fake, tmp_path, model, price):
    cfg = config(fake, model=model)
    cfg["gateway_models"][model] = {"upstream": ["chutes"]}
    cfg["prices"][model] = price
    with pytest.raises(ConfigError, match="looks free"):
        caller(cfg, tmp_path)


@pytest.mark.parametrize("drift", [None, "0.1", True, 1.5, -0.1])
def test_a_bad_drift_threshold_is_a_config_error_for_gateway_roles_only(fake, tmp_path, drift):
    cfg = config(fake)
    cfg["gateway"]["cost_drift_warn"] = drift
    with pytest.raises(ConfigError, match="cost_drift_warn"):
        caller(cfg, tmp_path)
    cfg["roles"]["other"] = {"model": "fake:scripted"}
    from models.fake import StrictScriptedChatModel
    LLMCaller(cfg, "other", EventLog(tmp_path / "o.jsonl"), model=StrictScriptedChatModel(script=[]))
