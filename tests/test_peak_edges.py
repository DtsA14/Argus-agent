"""SPEC_PEAK_EDGES: the worst case before sending is always at the peak price (P1), the ledger cost takes the higher
multiplier of a call's start and end (P2), and the router's confirm screen warns at peak (P3)."""
import copy
from datetime import datetime, timedelta, timezone

import pytest
from langchain_core.messages import HumanMessage

from harness.events import EventLog
from harness.llm import LLMCaller, Reservation
from models.fake import ScriptedChatModel, reply
from models.pricing import cost_usd, peak_line
from runner import load_config

DS = "deepseek:deepseek-flash"
MSGS = [HumanMessage("hello")]
THU = datetime(2026, 10, 15, tzinfo=timezone.utc)                  # a Thursday; DeepSeek peak 01-04 and 06-10 UTC
SAT = datetime(2026, 10, 17, tzinfo=timezone.utc)


def at(day, h, m=0, s=0):
    return day + timedelta(hours=h, minutes=m, seconds=s)


class Clock:
    """The caller's clock: each read takes the next time, the last one stays."""

    def __init__(self, *times):
        self.times, self.reads = list(times), 0

    def __call__(self):
        self.reads += 1
        return self.times.pop(0) if len(self.times) > 1 else self.times[0]


def make(tmp_path, clock, *, model=DS, est_in=1000, script=None):
    cfg = copy.deepcopy(load_config())
    cfg["llm"]["base_delay"] = 0
    cfg["roles"]["worker"]["model"] = model
    fake = ScriptedChatModel(script=list(script or [reply(input_tokens=900, output_tokens=500)]))
    log = EventLog(tmp_path / "e.jsonl")
    c = LLMCaller(cfg, "worker", log, model=fake, counter=lambda m, t: est_in, sleep=lambda s: None, now=clock)
    return c, fake, log, cfg


def ledger(log, event):
    return [e for e in log.read() if e["event"] == event]


def plain(cfg, model, mult, **tok):
    return cost_usd(cfg["prices"][model], window=None, **tok) * mult


# ---- P1: the worst case is the peak price at any hour -------------------------------------------------------------

@pytest.mark.parametrize("now", [at(THU, 2), at(THU, 0, 59, 30), at(THU, 12), at(SAT, 2)],
                         ids=["peak", "a minute before peak", "weekday off-peak", "saturday"])
def test_the_worst_case_and_max_tokens_are_at_the_peak_price_at_any_hour(tmp_path, now):
    c, fake, log, _ = make(tmp_path, Clock(now))
    assert not c.cache                                 # DeepSeek caches by itself, no write cost
    c.call(MSGS, Reservation(tokens=10**9, usd=0.002))
    (started,) = ledger(log, "llm_call_started")
    # 1,000 input at $0.15/M x2 = $0.0003; the rest at $0.60/M x2: 1,416 output tokens (off-peak rates would give 3,083)
    assert fake.calls[0]["kwargs"]["max_tokens"] == 1416 < c.max_output
    assert started["worst_usd"] == pytest.approx(0.0003 + 1416 * 1.2e-6, rel=1e-6)


def test_a_model_without_a_peak_window_keeps_its_plain_worst_case(tmp_path):
    model = "anthropic:claude-haiku-5-5"
    c, fake, log, cfg = make(tmp_path, Clock(at(THU, 2)), model=model)
    price = cfg["prices"][model]
    usd = 0.01
    c.call(MSGS, Reservation(tokens=10**9, usd=usd))
    (started,) = ledger(log, "llm_call_started")
    worst = c._usd(1000, fake.calls[0]["kwargs"]["max_tokens"], write_5m=1000 if c.cache else 0, mult=1)
    assert started["worst_usd"] == pytest.approx(worst, rel=1e-6)
    assert worst <= usd and price.get("peak_multiplier", 1) == 1


# ---- P2: the ledger cost takes the higher multiplier of start and end ----------------------------------------------

@pytest.mark.parametrize("start, end, mult", [
    (at(THU, 0, 59, 30), at(THU, 1, 0, 10), 2),        # sent off-peak, answered at peak
    (at(THU, 3, 59, 50), at(THU, 4, 0, 20), 2),        # sent at peak, answered off-peak
    (at(THU, 12), at(THU, 12, 1), 1),                  # all off-peak: the price does not go up
    (at(SAT, 2), at(SAT, 2, 1), 1),                    # weekend
], ids=["into peak", "out of peak", "off-peak", "saturday"])
def test_the_cost_takes_the_higher_multiplier_of_start_and_end(tmp_path, start, end, mult):
    clock = Clock(start, end)
    c, _, log, cfg = make(tmp_path, clock)
    res = Reservation(tokens=10**9, usd=1.0)
    c.call(MSGS, res)
    (started,) = ledger(log, "llm_call_started")
    (done,) = ledger(log, "llm_call")
    assert done["usd"] == pytest.approx(plain(cfg, DS, mult, input_tokens=900, output_tokens=500), rel=1e-6)
    assert done["peak"] is (mult > 1)
    assert done["usd_nano"] <= started["worst_usd_nano"] and not res.violated
    assert clock.reads == 2                            # one read before sending, one after the reply


def test_a_crossing_call_that_spends_its_whole_reservation_stays_within_it(tmp_path):
    """Sent at 00:59:30 with all output the reservation allows; answered at peak: the bill fits."""
    c, fake, log, cfg = make(tmp_path, Clock(at(THU, 0, 59, 30), at(THU, 1, 0, 10)), est_in=1000)
    res = Reservation(tokens=10**9, usd=0.002)
    cap = c._output_cap(1000, res)
    fake.script[:] = [reply(input_tokens=1000, output_tokens=cap)]
    c.call(MSGS, res)
    assert not res.violated and res.used_usd <= res.usd
    assert not ledger(log, "budget_violation")


# ---- P3: the router's confirm screen warns at peak ---------------------------------------------------------------

WINDOW = load_config()["peak_windows"]["deepseek"]
PRICE = load_config()["prices"][DS]


@pytest.mark.parametrize("now, line", [
    (at(THU, 2), "peak: deepseek is at 2x now (until 04:00 UTC = 11:00 WIB); off-peak costs about half"),
    (at(THU, 9, 59), "peak: deepseek is at 2x now (until 10:00 UTC = 17:00 WIB); off-peak costs about half"),
    (at(THU, 0, 45), "peak: deepseek goes to 2x at 01:00 UTC = 08:00 WIB; off-peak costs about half"),
    (at(THU, 5, 30), "peak: deepseek goes to 2x at 06:00 UTC = 13:00 WIB; off-peak costs about half"),
    (at(THU, 0, 20), None), (at(THU, 12), None), (at(SAT, 2), None), (at(THU, 4), None),
])
def test_the_peak_line(now, line):
    assert peak_line("deepseek", PRICE, WINDOW, now) == line


def test_no_peak_line_without_a_window_or_a_higher_price():
    assert peak_line("anthropic", {"input": 1, "output": 1}, None, at(THU, 2)) is None
    assert peak_line("deepseek", {"input": 1, "output": 1}, WINDOW, at(THU, 2)) is None


def test_the_confirm_screen_and_limits_shown_carry_the_peak_line(tmp_path):
    from router import job as rj
    from tests.test_router import Env
    c = load_config()                                  # DeepSeek roles, models still the scripted fakes
    e = Env(tmp_path, config=c)
    e.deps.clock, e.deps.get_key = (lambda: "2026-10-15T02:00:00Z"), (lambda: "sk-" + "a" * 32)
    e.code()
    assert "until 04:00 UTC = 11:00 WIB" in e.confirms[0]
    shown = [x["screen"] for x in rj.open_job("jtest", e.jobs).data["log"] if x["what"] == "limits_shown"]
    assert shown and "peak: deepseek is at 2x now" in shown[0]


def test_no_peak_line_on_the_confirm_screen_off_peak(tmp_path):
    from tests.test_router import Env
    e = Env(tmp_path, config=load_config())
    e.deps.get_key = lambda: "sk-" + "a" * 32
    e.code()                                           # Friday 00:00 UTC
    assert "peak:" not in e.confirms[0]
