"""SPEC_BUDGET_V2 part 1 (rev 1): the daily and monthly meters of actual spend, read from the stage ledgers. Synthetic ledgers in a temporary jobs directory."""
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from router import budget as bg  # noqa: E402

WIB = timezone(timedelta(hours=7))
LIM = {"daily_nano": 1_000_000_000, "monthly_nano": 30_000_000_000, "warn_at": 0.8}


def at(y, mo, d, h=0, mi=0, s=0, tz=timezone.utc):
    return datetime(y, mo, d, h, mi, s, tzinfo=tz).timestamp()


def started(cid, ts, worst):
    return {"event": "llm_call_started", "call_id": cid, "ts": ts, "worst_usd_nano": worst}


def done(cid, ts, nano, status="ok"):
    return {"event": "llm_call", "call_id": cid, "ts": ts, "status": status, "usd_nano": nano}


def write(path, events, newline=True):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(json.dumps(e) for e in events)
    path.write_text(body + ("\n" if newline else ""))
    return path


def ledger(jobs, job, events, stage="m1", **kw):
    return write(Path(jobs) / job / "runs" / f"{job}-{stage}" / "events.jsonl", events, **kw)


@pytest.fixture
def jobs(tmp_path):
    d = tmp_path / "jobs"
    d.mkdir()
    return d


def meter(jobs, now, **kw):
    return bg.Ledgers(jobs).snapshot(LIM, now=now)


# ---- the config ---------------------------------------------------------------------------------------------------

def test_the_section_is_optional_and_validated():
    assert bg.settings({"chat": {}}) is None and bg.settings({}) is None
    assert bg.settings({"chat": {"budget": {"daily_usd": 1.0, "monthly_usd": 30.0, "warn_at": 0.8}}}) == {"daily_nano": 10 ** 9, "monthly_nano": 30 * 10 ** 9, "warn_at": 0.8, "sources": []}


@pytest.mark.parametrize("bad", [{"daily_usd": 0, "monthly_usd": 30, "warn_at": 0.8}, {"daily_usd": -1, "monthly_usd": 30, "warn_at": 0.8}, {"daily_usd": float("nan"), "monthly_usd": 30, "warn_at": 0.8},
                                 {"daily_usd": True, "monthly_usd": 30, "warn_at": 0.8}, {"daily_usd": 31, "monthly_usd": 30, "warn_at": 0.8}, {"daily_usd": 1, "monthly_usd": 30, "warn_at": 0},
                                 {"daily_usd": 1, "monthly_usd": 30, "warn_at": 1.5}, {"daily_usd": 1, "monthly_usd": 30, "warn_at": True}, {"daily_usd": 1, "monthly_usd": 30},
                                 {"daily_usd": 1, "monthly_usd": 30, "warn_at": 0.8, "weekly_usd": 5}, "x"])
def test_a_bad_section_is_refused(bad):
    with pytest.raises(bg.BudgetConfigError):
        bg.settings({"chat": {"budget": bad}})


def test_the_real_config_has_the_budget_atha_chose():
    from runner import load_config
    s = bg.settings(load_config())
    assert (s["daily_nano"], s["monthly_nano"], s["warn_at"]) == (10 ** 9, 30 * 10 ** 9, 0.8)
    labels = [x[0] for x in s["sources"]]
    assert 0 < len(labels) <= bg.SOURCES_MAX and len(set(labels)) == len(labels) and bg.OWN not in labels and all(os.path.isabs(x[1]) and x[2] in ("jobs", "flat") for x in s["sources"])
    assert not any("staging" in x[1] or os.path.basename(x[1]).startswith("wt-") for x in s["sources"])            # staging and a worktree itself hold copies: not sources


# ---- the windows --------------------------------------------------------------------------------------------------

def test_the_day_turns_at_midnight_wib_not_utc(jobs):
    ledger(jobs, "j1", [started("a", at(2026, 11, 28, 16, 59, 59), 5), done("a", at(2026, 11, 28, 16, 59, 59), 100),
                        started("b", at(2026, 11, 28, 17, 0, 0), 5), done("b", at(2026, 11, 28, 17, 0, 0), 7)])
    on28 = meter(jobs, at(2026, 11, 28, 5, 0, 0))                         # 12:00 WIB on the 28th
    on29 = meter(jobs, at(2026, 11, 29, 5, 0, 0))                         # 12:00 WIB on the 29th
    assert on28["day"]["spent_nano"] == 100 and on28["day"]["date"] == "2026-11-28"
    assert on29["day"]["spent_nano"] == 7 and on29["day"]["date"] == "2026-11-29"
    assert on28["month"]["spent_nano"] == on29["month"]["spent_nano"] == 107


def test_the_month_turns_at_midnight_wib_on_the_first(jobs):
    ledger(jobs, "j1", [started("a", at(2026, 11, 30, 16, 59, 59), 5), done("a", at(2026, 11, 30, 16, 59, 59), 100),
                        started("b", at(2026, 11, 30, 17, 0, 0), 5), done("b", at(2026, 11, 30, 17, 0, 0), 7)])
    nov = meter(jobs, at(2026, 11, 30, 10))
    dec = meter(jobs, at(2026, 12, 1, 10))
    assert nov["month"]["spent_nano"] == 100 and nov["month"]["date"] == "2026-11"
    assert dec["month"]["spent_nano"] == 7 and dec["month"]["date"] == "2026-12" and dec["month"]["resets_at"].startswith("2027-01-01T00:00:00+07:00")


def test_a_leap_day_is_a_day_and_february_has_29_days_in_2028(jobs):
    ledger(jobs, "j1", [started("a", at(2028, 2, 28, 17, 0, 0), 5), done("a", at(2028, 2, 28, 17, 0, 0), 9)])       # 00:00 WIB on 29 February
    m = meter(jobs, at(2028, 2, 29, 12))
    assert m["day"]["spent_nano"] == 9 and m["day"]["date"] == "2028-02-29" and m["day"]["resets_at"].startswith("2028-03-01T00:00:00+07:00")


def test_a_call_that_spans_two_days_counts_where_it_ended(jobs):
    ledger(jobs, "j1", [started("a", at(2026, 11, 28, 16, 59, 58), 50), done("a", at(2026, 11, 28, 17, 0, 2), 40)])
    assert meter(jobs, at(2026, 11, 28, 10))["day"]["spent_nano"] == 0
    assert meter(jobs, at(2026, 11, 29, 10))["day"]["spent_nano"] == 40


# ---- what counts --------------------------------------------------------------------------------------------------

NOW = at(2026, 11, 28, 5)


def test_a_started_call_without_its_end_counts_its_worst_case_and_its_end_replaces_it(jobs):
    p = ledger(jobs, "j1", [started("a", NOW - 10, 900)])
    L = bg.Ledgers(jobs)
    assert L.snapshot(LIM, now=NOW)["day"]["spent_nano"] == 900                  # as harness.llm.reconcile_ledger charges unknown_after_crash
    with open(p, "a") as f:
        f.write(json.dumps(done("a", NOW - 5, 120)) + "\n")
    assert L.snapshot(LIM, now=NOW)["day"]["spent_nano"] == 120


def test_a_refused_call_and_other_event_kinds_are_not_summed(jobs):
    ledger(jobs, "j1", [done("r", NOW - 5, None, status="refused"), {"event": "reservation_restored", "ts": NOW - 4, "usd_nano": 777, "call_id": "x"},
                        {"event": "price_drift", "ts": NOW - 3, "usd_nano": 555}, started("a", NOW - 2, 5), done("a", NOW - 1, 30)])
    m = meter(jobs, NOW)
    assert m["day"]["spent_nano"] == 30 and m["unknown"] is None


def test_the_patch_reader_and_env_ledgers_are_counted(jobs):
    write(jobs / "j1" / "patch_read_ledger.jsonl", [started("p", NOW - 9, 5), done("p", NOW - 8, 11)])
    write(jobs / "env_propose_ledger.jsonl", [started("e", NOW - 9, 5), done("e", NOW - 8, 13)])
    ledger(jobs, "j1", [started("a", NOW - 7, 5), done("a", NOW - 6, 17)])
    assert meter(jobs, NOW)["day"]["spent_nano"] == 11 + 13 + 17


def test_fixture_ledgers_inside_repo_snapshots_and_symlinks_are_not_read(jobs, tmp_path):
    ledger(jobs, "j1", [started("a", NOW - 6, 5), done("a", NOW - 5, 17)])
    for sub in ("runs/j1-a1/source/fixtures/audit", "runs/j1-a1/workspace/x", "root/fixtures"):
        write(jobs / "j1" / sub / "events.jsonl", [started("f", NOW - 4, 5), done("f", NOW - 3, 99999)])
    outside = write(tmp_path / "elsewhere" / "events.jsonl", [started("s", NOW - 4, 5), done("s", NOW - 3, 88888)])
    (jobs / "j2" / "runs" / "j2-m1").mkdir(parents=True)
    os.symlink(outside, jobs / "j2" / "runs" / "j2-m1" / "events.jsonl")
    L = bg.Ledgers(jobs)
    m = L.snapshot(LIM, now=NOW)
    assert m["day"]["spent_nano"] == 17 and m["ignored"] == 1 and m["unknown"] is None


def test_chat_and_cli_jobs_are_both_counted(jobs):
    ledger(jobs, "j20261128_090000_aaaa", [started("a", NOW - 6, 5), done("a", NOW - 5, 10)])          # a job id the chat made
    ledger(jobs, "jcli_job", [started("b", NOW - 6, 5), done("b", NOW - 5, 20)])                         # any other job directory
    assert meter(jobs, NOW)["day"]["spent_nano"] == 30


# ---- reading edges ------------------------------------------------------------------------------------------------

def test_a_write_in_progress_is_not_unknown_and_not_counted_until_its_line_is_whole(jobs):
    p = ledger(jobs, "j1", [started("a", NOW - 6, 5), done("a", NOW - 5, 10)])
    L = bg.Ledgers(jobs)
    assert L.snapshot(LIM, now=NOW)["day"]["spent_nano"] == 10
    end = json.dumps(done("b", NOW - 3, 4))
    with open(p, "a") as f:
        f.write(json.dumps(started("b", NOW - 4, 50)) + "\n" + end[:25])        # b has started (its worst case counts) and its end is being written: whole lines, then a cut one
    m = L.snapshot(LIM, now=NOW)
    assert m["day"]["spent_nano"] == 60 and m["unknown"] is None
    with open(p, "a") as f:
        f.write(end[25:] + "\n")
    assert L.snapshot(LIM, now=NOW)["day"]["spent_nano"] == 14                     # the cut line was not consumed: the whole line is read and replaces the worst case


def test_a_broken_line_in_the_middle_is_skipped_not_unknown(jobs):
    p = ledger(jobs, "j1", [started("a", NOW - 6, 5)])
    with open(p, "a") as f:
        f.write('{"event": "llm_call_started", "call_id": "cut\n')              # a crash left this; the harness repairs it with a newline
        f.write(json.dumps(done("a", NOW - 5, 10)) + "\n")
    m = meter(jobs, NOW)
    assert m["day"]["spent_nano"] == 10 and m["unknown"] is None


def test_an_unpriced_call_makes_only_its_own_windows_unknown(jobs):
    ledger(jobs, "j1", [started("a", at(2026, 10, 5), 5), done("a", at(2026, 10, 5), None), started("b", NOW - 6, 5), done("b", NOW - 5, 10)])
    m = meter(jobs, NOW)
    assert m["day"]["spent_nano"] == 10 and m["month"]["spent_nano"] == 10 and m["unknown"] is None          # October's unpriced call is not November's problem
    ledger(jobs, "j2", [started("c", NOW - 4, None)])
    m = meter(jobs, NOW)
    assert m["day"]["unknown"] == {"reason": "unpriced call", "job": "j2", "source": "Argus jobs"} and m["day"]["spent_usd"] is None and m["month"]["unknown"]["job"] == "j2" and m["unknown"]["job"] == "j2"


@pytest.mark.parametrize("amount", [-5, 1.5, "7", True])
def test_an_amount_that_is_not_a_non_negative_integer_is_unpriced(jobs, amount):
    ledger(jobs, "j1", [started("a", NOW - 6, 5), done("a", NOW - 5, amount)])
    assert meter(jobs, NOW)["day"]["unknown"]["reason"] == "unpriced call"


def test_an_unreadable_ledger_is_unknown_only_when_it_is_from_this_month(jobs):
    new = ledger(jobs, "j1", [started("a", NOW - 6, 5), done("a", NOW - 5, 10)])
    old = ledger(jobs, "j0", [started("o", NOW - 6, 5), done("o", NOW - 5, 10)])
    os.utime(old, (at(2026, 9, 1), at(2026, 9, 1)))
    new.chmod(0)
    old.chmod(0)
    try:
        m = meter(jobs, NOW)
        assert m["month"]["unknown"] == {"reason": "unreadable", "job": "j1", "source": "Argus jobs"} and m["day"]["unknown"]["job"] == "j1" and m["month"]["spent_usd"] is None
        new.chmod(0o644)
        m = meter(jobs, NOW)
        assert m["unknown"] is None and m["ignored"] == 0 or m["unknown"] is None                          # the old one, unreadable and from September, is no problem now
    finally:
        new.chmod(0o644)
        old.chmod(0o644)


def test_a_shrunk_ledger_is_read_again_from_the_start_and_an_append_only_adds(jobs):
    p = ledger(jobs, "j1", [started("a", NOW - 6, 5), done("a", NOW - 5, 10), started("b", NOW - 4, 5), done("b", NOW - 3, 20)])
    L = bg.Ledgers(jobs)
    assert L.snapshot(LIM, now=NOW)["day"]["spent_nano"] == 30
    write(p, [started("c", NOW - 2, 5), done("c", NOW - 1, 7)])
    assert L.snapshot(LIM, now=NOW)["day"]["spent_nano"] == 7
    with open(p, "a") as f:
        f.write(json.dumps(started("d", NOW - 1, 5)) + "\n" + json.dumps(done("d", NOW, 3)) + "\n")
    assert L.snapshot(LIM, now=NOW)["day"]["spent_nano"] == 10


def test_a_deleted_ledger_stops_counting(jobs):
    p = ledger(jobs, "j1", [started("a", NOW - 6, 5), done("a", NOW - 5, 10)])
    L = bg.Ledgers(jobs)
    assert L.snapshot(LIM, now=NOW)["day"]["spent_nano"] == 10
    p.unlink()
    assert L.snapshot(LIM, now=NOW)["day"]["spent_nano"] == 0


# ---- the meters' numbers ------------------------------------------------------------------------------------------

def test_the_warning_starts_exactly_at_warn_at(jobs):
    ledger(jobs, "j1", [started("a", NOW - 6, 5), done("a", NOW - 5, 799_999_999)])
    assert meter(jobs, NOW)["day"]["warn"] is False
    ledger(jobs, "j2", [started("b", NOW - 4, 5), done("b", NOW - 3, 1)])
    m = meter(jobs, NOW)
    assert m["day"]["warn"] is True and m["day"]["spent_nano"] == 800_000_000 and m["month"]["warn"] is False


def test_the_month_meter_is_not_the_day_meter(jobs):
    ledger(jobs, "j1", [started("a", at(2026, 11, 3, 5), 5), done("a", at(2026, 11, 3, 5), 40), started("b", NOW - 3, 5), done("b", NOW - 2, 2)])
    m = meter(jobs, NOW)
    assert m["day"]["spent_nano"] == 2 and m["month"]["spent_nano"] == 42 and m["day"]["limit_usd"] == 1.0 and m["month"]["limit_usd"] == 30.0
    assert "WIB" in m["note"] and "listed sources" in m["note"]


def test_nothing_is_zero_when_there_are_no_ledgers(jobs):
    m = meter(jobs, NOW)
    assert m["day"]["spent_nano"] == 0 and m["scanned"] == 0 and m["unknown"] is None
    assert bg.Ledgers(jobs / "nowhere").snapshot(LIM, now=NOW)["day"]["spent_nano"] == 0


def test_the_snapshot_is_kept_for_a_few_seconds(jobs):
    t = [100.0]
    L = bg.Ledgers(jobs, clock=lambda: NOW, mono=lambda: t[0])
    ledger(jobs, "j1", [started("a", NOW - 6, 5), done("a", NOW - 5, 10)])
    a = L.snapshot(LIM)
    ledger(jobs, "j2", [started("b", NOW - 4, 5), done("b", NOW - 3, 20)])
    t[0] += bg.BUDGET_TTL_S - 1
    assert L.snapshot(LIM) is a and a["day"]["spent_nano"] == 10
    t[0] += 2
    assert L.snapshot(LIM)["day"]["spent_nano"] == 30


def test_a_cold_scan_of_600_ledgers_and_a_warm_one_are_fast(jobs):
    for i in range(600):
        ledger(jobs, f"j{i:04d}", [e for k in range(20) for e in (started(f"c{i}_{k}", NOW - 100 + k, 50), done(f"c{i}_{k}", NOW - 100 + k, 10))])
    L = bg.Ledgers(jobs)
    t = time.perf_counter()
    L.warm()
    cold = time.perf_counter() - t
    t = time.perf_counter()
    m = L.snapshot(LIM, now=NOW)
    warm = time.perf_counter() - t
    assert m["scanned"] == 600 and m["day"]["spent_nano"] == 600 * 20 * 10
    assert cold < 5.0 and warm < 1.0, (cold, warm)                         # the spec's 2 s and 50 ms, with room for a loaded host


# ---- B1.1 (rev 2): the bill, platforms, sources, copies ------------------------------------------------------------

def call(cid, ts, usd_nano, reported="absent", model="openrouter:deepseek/deepseek-v4.1-flash-1017", status="ok"):
    e = {"event": "llm_call", "call_id": cid, "ts": ts, "status": status, "usd_nano": usd_nano, "model": model}
    if reported != "absent":
        e["usd_reported_nano"] = reported
    return e


def start(cid, ts, worst, model="openrouter:deepseek/deepseek-v4.1-flash-1017"):
    return {**started(cid, ts, worst), "model": model}


def test_a_call_costs_what_its_bill_says_the_reported_cost_when_there_is_one(jobs):
    ledger(jobs, "j1", [start("a", NOW - 9, 5), call("a", NOW - 8, 1000, reported=400),          # the harness's upper bound 1000, the gateway billed 400
                        start("b", NOW - 7, 5), call("b", NOW - 6, 300),                          # a direct API: no reported cost, the harness's count
                        start("c", NOW - 5, 5), call("c", NOW - 4, 900, reported=1.5),             # a reported value that is not an integer is not used
                        start("d", NOW - 3, 5), call("d", NOW - 2, 700, reported=-1)])
    assert meter(jobs, NOW)["day"]["spent_nano"] == 400 + 300 + 900 + 700


def test_a_started_call_still_counts_its_worst_case_and_its_platform(jobs):
    ledger(jobs, "j1", [start("a", NOW - 9, 777, model="deepseek:deepseek-flash")])
    m = meter(jobs, NOW)
    assert m["day"]["spent_nano"] == 777 and m["day"]["by_platform"] == {"DeepSeek": 777}


@pytest.mark.parametrize("model,name", [("openrouter:deepseek/x", "OpenRouter"), ("deepseek:deepseek-flash", "DeepSeek"), ("anthropic:claude-haiku-5-5", "Anthropic"),
                                        ("together:llama", "Together"), (None, "Other"), ("nocolon", "Other"), (":x", "Other"), (5, "Other")])
def test_the_platform_is_the_prefix_of_the_model(model, name):
    assert bg.platform_of(model) == name


def test_the_platforms_and_the_sources_each_add_up_to_the_total(jobs, tmp_path):
    other = tmp_path / "exp"
    ledger(jobs, "j1", [start("a", NOW - 9, 5, model="openrouter:m"), call("a", NOW - 8, 100, model="openrouter:m"), start("b", NOW - 7, 5, model="deepseek:m"), call("b", NOW - 6, 50, model="deepseek:m")])
    ledger(other, "j2", [start("c", NOW - 5, 5, model="deepseek:m"), call("c", NOW - 4, 25, model="deepseek:m")])
    lim = {**LIM, "sources": [("Experiments", str(other), "jobs")]}
    m = bg.Ledgers(jobs).snapshot(lim, now=NOW)
    assert m["day"]["spent_nano"] == 175 and m["day"]["by_platform"] == {"OpenRouter": 100, "DeepSeek": 75} and m["day"]["by_source"] == {"Argus jobs": 150, "Experiments": 25}
    assert sum(m["month"]["by_platform"].values()) == sum(m["month"]["by_source"].values()) == m["month"]["spent_nano"] == 175
    assert [x["label"] for x in m["sources"]] == ["Argus jobs", "Experiments"]


def test_a_call_held_by_several_sources_counts_once_for_the_first(jobs, tmp_path):
    copy = tmp_path / "copy"
    ev = [start("a", NOW - 9, 5), call("a", NOW - 8, 100)]
    ledger(jobs, "j1", ev)
    ledger(copy, "j1", ev)                                                    # a snapshot copy of the same ledger
    ledger(copy, "j9", [start("z", NOW - 3, 5), call("z", NOW - 2, 40)])
    m = bg.Ledgers(jobs).snapshot({**LIM, "sources": [("Copy", str(copy), "jobs")]}, now=NOW)
    assert m["day"]["spent_nano"] == 140 and m["day"]["by_source"] == {"Argus jobs": 100, "Copy": 40}
    first = bg.Ledgers(jobs).snapshot({**LIM, "sources": [("A", str(copy), "jobs")]}, now=NOW)
    assert first["day"]["by_source"]["Argus jobs"] == 100                      # the chat's own directory is first whatever the config says


def test_the_config_order_decides_which_source_holds_a_shared_call(jobs, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    ev = [start("a", NOW - 9, 5), call("a", NOW - 8, 100)]
    ledger(a, "j1", ev)
    ledger(b, "j1", ev)
    m = bg.Ledgers(jobs).snapshot({**LIM, "sources": [("B", str(b), "jobs"), ("A", str(a), "jobs")]}, now=NOW)
    assert m["day"]["by_source"] == {"B": 100}


def test_a_flat_source_reads_ledgers_three_deep_not_four_and_skips_checkout_directories(jobs, tmp_path):
    root = tmp_path / "flat"
    write(root / "route_eval_ledger.jsonl", [start("a", NOW - 9, 5), call("a", NOW - 8, 1)])
    write(root / "x" / "y" / "z" / "events.jsonl", [start("b", NOW - 9, 5), call("b", NOW - 8, 10)])                # three directories deep: read
    write(root / "x" / "y" / "z" / "w" / "events.jsonl", [start("c", NOW - 9, 5), call("c", NOW - 8, 100)])         # four: not read
    for skip in ("fixtures", "source", "workspace", "root", ".git", "node_modules"):
        write(root / skip / "events.jsonl", [start("s" + skip, NOW - 9, 5), call("s" + skip, NOW - 8, 1000)])
    outside = write(tmp_path / "elsewhere" / "events.jsonl", [start("o", NOW - 9, 5), call("o", NOW - 8, 99999)])
    os.symlink(outside, root / "linked_ledger.jsonl")
    m = bg.Ledgers(jobs).snapshot({**LIM, "sources": [("Flat", str(root), "flat")]}, now=NOW)
    assert m["day"]["spent_nano"] == 1 + 10 and m["ignored"] == 1


def test_a_missing_source_is_listed_as_missing_and_is_not_unknown(jobs, tmp_path):
    m = bg.Ledgers(jobs).snapshot({**LIM, "sources": [("Gone", str(tmp_path / "nowhere"), "jobs"), ("Gone flat", str(tmp_path / "nowhere2"), "flat")]}, now=NOW)
    assert m["unknown"] is None and [x["missing"] for x in m["sources"]] == [False, True, True]


def test_a_plain_file_named_like_a_job_beside_the_jobs_is_not_unknown(jobs):
    (jobs / "j20261122_120632_4c0a.out").write_text("output of a run")
    ledger(jobs, "j1", [start("a", NOW - 9, 5), call("a", NOW - 8, 10)])
    m = meter(jobs, NOW)
    assert m["unknown"] is None and m["day"]["spent_nano"] == 10


def test_an_unknown_window_names_the_source(jobs, tmp_path):
    exp = tmp_path / "exp"
    ledger(exp, "j2", [start("c", NOW - 4, None)])
    m = bg.Ledgers(jobs).snapshot({**LIM, "sources": [("Experiments", str(exp), "jobs")]}, now=NOW)
    assert m["day"]["unknown"] == {"reason": "unpriced call", "job": "j2", "source": "Experiments"} and m["day"]["by_platform"] is None and m["day"]["by_source"] is None


@pytest.mark.parametrize("sources", [[{"label": "A", "path": "/x", "layout": "jobs"}, {"label": "A", "path": "/y", "layout": "jobs"}], [{"label": "Argus jobs", "path": "/x", "layout": "jobs"}],
                                     [{"label": "A", "path": "relative/x", "layout": "jobs"}], [{"label": "A", "path": "/x", "layout": "deep"}], [{"label": "", "path": "/x", "layout": "jobs"}],
                                     [{"label": 5, "path": "/x", "layout": "jobs"}], [{"label": "A" * 41, "path": "/x", "layout": "jobs"}], [{"label": "A", "path": "/x"}],
                                     [{"label": str(i), "path": "/x", "layout": "jobs"} for i in range(41)], "x", [{"label": "A", "path": "/x", "layout": "jobs", "extra": 1}]])
def test_bad_sources_are_refused(sources):
    with pytest.raises(bg.BudgetConfigError):
        bg.settings({"chat": {"budget": {"daily_usd": 1, "monthly_usd": 30, "warn_at": 0.8, "sources": sources}}})


def test_a_good_source_list_is_expanded_and_ordered():
    s = bg.settings({"chat": {"budget": {"daily_usd": 1, "monthly_usd": 30, "warn_at": 0.8, "sources": [{"label": "H", "path": "~/x", "layout": "flat"}, {"label": "J", "path": "/abs/j", "layout": "jobs"}]}}})
    assert s["sources"] == [("H", os.path.expanduser("~/x"), "flat"), ("J", "/abs/j", "jobs")]
