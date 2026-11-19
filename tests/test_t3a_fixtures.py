"""T3a (SPEC_KARTU_SETUJU section 8): the 12 cards of scripts/t3a_fixtures.py are files of real jobs in a separate directory and the real card routes show what the
key says: the machine's cost ratio, the scope mark, the failed audit; the replies are recorded as given and scored by the key, not by Claude."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import t3a_fixtures as t3a  # noqa: E402
from test_chat_actions import Service  # noqa: E402


@pytest.fixture
def world(tmp_path):
    root = tmp_path / "r"
    cards, h = t3a.build(root, seed=3)
    s = Service(root)
    s.actions.cards.queues_dir = root / "queues"
    yield s, root, cards, h
    s.stop()


def card_json(s, c, root):
    if c["card_kind"] == "plan":
        return s.request("GET", f"/api/approve/prd/{c['id']}")[1]
    q = json.loads((root / "queues" / c["id"] / "queue.json").read_text())
    return s.request("GET", f"/api/approve/code/{q['items'][0]['job']}")[1]


def by_set(cards):
    return {c["set"]: c for c in cards}


def test_twelve_cards_six_and_six_with_the_planted_kinds(world):
    _, _, cards, _ = world
    assert len(cards) == 12 and sorted(c["kind"] for c in cards) == ["defect"] * 6 + ["good"] * 6
    assert sorted(c["class"] for c in cards if c["kind"] == "defect") == ["audit", "biaya", "biaya", "cakupan", "tujuan", "tujuan"]
    assert [c["card"] for c in cards] == list(range(1, 13))


def test_the_plan_cards_show_the_machines_cost_ratio_and_the_request_beside_the_writers_text(world):
    s, root, cards, _ = world
    k = by_set(cards)
    ratio = {n: card_json(s, k[n], root)["cost"]["ratio"] for n in ("p1", "p3", "p4", "p5")}
    assert ratio["p3"] >= 3 and ratio["p4"] >= 3 and ratio["p1"] <= 1.5 and ratio["p5"] <= 1.5
    p1 = card_json(s, k["p1"], root)
    assert "diskon member" in p1["request"] and "poin loyalitas" in p1["summary"]
    assert all(card_json(s, k[n], root)["items"][0]["domain_read"]["kind"] == "ok" for n in ("p1", "p5"))


def test_the_install_cards_show_the_scope_mark_and_the_failed_audit_and_the_good_ones_are_open(world):
    s, root, cards, _ = world
    k = by_set(cards)
    i1, i2 = card_json(s, k["i1"], root), card_json(s, k["i2"], root)
    assert any("src/other.py" in m for m in i1["scope_marks"])
    assert {x["key"]: x["ok"] for x in i2["checks"]}["b"] is False
    for n in ("i3", "i4", "i5"):
        g = card_json(s, k[n], root)
        assert g["scope_marks"] == [] and g["open"] is True, (n, [x for x in g["checks"] if x["ok"] is False])


def test_the_cards_never_go_into_the_live_jobs_directory(tmp_path):
    with pytest.raises(SystemExit):
        t3a.build(tmp_path / "pilot3a_live" / "x")
    t3a.build(tmp_path / "ok", seed=1)
    with pytest.raises(SystemExit):
        t3a.build(tmp_path / "ok", seed=1)                  # a second build in the same place is refused


def right(root, cards, h, skip=()):
    for c in cards:
        if c["card"] in skip:
            continue
        if c["kind"] == "defect":
            t3a.reply(root, c["card"], "tolak", c["class"], "x")
        else:
            t3a.reply(root, c["card"], "terima", None, "x")


def test_all_right_passes_and_the_replies_are_kept_as_given(world):
    _, root, cards, h = world
    right(root, cards, h)
    passed, lines = t3a.score(root, h)
    assert passed and lines[-1] == "PASS"
    assert json.loads((t3a.keydir(root) / t3a.REPLIES).read_text().splitlines()[0])["text"] == "x"


def test_one_false_alarm_passes_two_do_not_and_rejecting_everything_fails(world):
    _, root, cards, h = world
    good = [c for c in cards if c["kind"] == "good"]
    right(root, cards, h, skip={good[0]["card"], good[1]["card"]})
    t3a.reply(root, good[0]["card"], "tolak", "biaya", "x")
    t3a.reply(root, good[1]["card"], "terima", None, "x")
    assert t3a.score(root, h)[0] is True
    # a second root: two good rejected
    root2 = root.parent / "r2"
    cards2, h2 = t3a.build(root2, seed=4)
    right(root2, cards2, h2, skip={c["card"] for c in cards2 if c["kind"] == "good"})
    for c in [c for c in cards2 if c["kind"] == "good"][:2]:
        t3a.reply(root2, c["card"], "tolak", "biaya", "x")
    for c in [c for c in cards2 if c["kind"] == "good"][2:]:
        t3a.reply(root2, c["card"], "terima", None, "x")
    assert t3a.score(root2, h2)[0] is False
    root3 = root.parent / "r3"
    cards3, h3 = t3a.build(root3, seed=5)
    for c in cards3:
        t3a.reply(root3, c["card"], "tolak", "biaya", "x")
    assert t3a.score(root3, h3)[0] is False


def test_an_accepted_defect_a_wrong_class_an_unanswered_card_and_a_wrong_hash_fail(world):
    _, root, cards, h = world
    d = [c for c in cards if c["kind"] == "defect"]
    right(root, cards, h, skip={d[0]["card"], d[1]["card"], d[2]["card"]})
    t3a.reply(root, d[0]["card"], "terima", None, "x")
    t3a.reply(root, d[1]["card"], "tolak", "audit" if d[1]["class"] != "audit" else "biaya", "x")
    passed, lines = t3a.score(root, h)
    assert not passed and any("not answered" in l for l in lines) and sum("MISS" in l for l in lines) == 2
    assert t3a.score(root, "0" * 64)[0] is False


def test_a_card_is_answered_once_and_the_reply_is_checked(world):
    _, root, cards, _ = world
    t3a.reply(root, 1, "terima", None, "x")
    for args in ((1, "tolak", "biaya", "x"), (2, "tolak", None, "x"), (2, "tolak", "lain", "x"), (2, "terima", "biaya", "x"), (99, "terima", None, "x")):
        with pytest.raises(SystemExit):
            t3a.reply(root, *args)
