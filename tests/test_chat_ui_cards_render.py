"""T3a presentation change, rendering half: the real drawing code of app.js run in V8 (mini-racer) on the JSON of the 12 T3a cards. Its own module so that a machine without
mini-racer skips only these tests and still runs the source tests of test_chat_ui_cards.py."""
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
pytest.importorskip("py_mini_racer")
from test_t3a_fixtures import by_set, card_json, world  # noqa: E402,F401

import card_render  # noqa: E402
from router import chat as rc  # noqa: E402

JS = (rc.STATIC_DIR / "app.js").read_text()


def api(c, s, root):
    if c["card_kind"] == "plan":
        return f"/api/approve/prd/{c['id']}", "showPlan", card_json(s, c, root)
    q = json.loads((root / "queues" / c["id"] / "queue.json").read_text())
    return f"/api/approve/code/{q['items'][0]['job']}", "showInstall", card_json(s, c, root)


def shown_strings(card):
    """The text values the server sent for the fields that were on screen before: each must be in the page."""
    out = []

    def walk(o, key=None):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("second", "reader", "reader2", "proof", "domain_read", "purpose", "cost", "item", "items", "examples", "inputs", "output", "assumptions", "files", "patch_read", "checks", "approval", "reference"):
                    walk(v, k)
                elif k in ("request", "summary", "fixed_line", "title", "text", "wording", "says", "call", "note", "path", "label", "shown", "ratio_text", "scope_note", "patch_read_label", "by",
                           "why", "warning", "no_examples", "summary_why", "at", "files_cut", "patch_sha12"):
                    if isinstance(v, str) and v:
                        out.append(v)
        elif isinstance(o, list):
            for x in o:
                walk(x, key)
    walk(card)
    return out


def text_of(html):
    return re.sub(r"<[^>]+>", "\u0001", html).replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")


def test_every_text_the_server_sent_is_on_the_page_for_all_twelve_cards(world):
    s, root, cards, _ = world
    for c in cards:
        page = text_of(draw(c, s, root))
        missing = [t for t in shown_strings(api(c, s, root)[2]) if t not in page]
        assert not missing, (c["set"], missing[:3])


def skeleton(html):
    return re.sub(r">[^<]+<", "><", html)


def draw(c, s, root):
    path, fn, payload = api(c, s, root)
    return card_render.render(JS, path, payload, fn)


def test_cards_of_the_same_kind_are_drawn_with_the_same_structure_whatever_their_class(world):
    s, root, cards, _ = world
    k = by_set(cards)
    plans = {n: skeleton(draw(k[n], s, root)) for n in ("p1", "p2", "p3", "p4", "p5", "p6", "p7")}
    assert len(set(plans.values())) == 1, {n: len(v) for n, v in plans.items()}
    inst = {n: skeleton(draw(k[n], s, root)) for n in ("i3", "i4", "i5")}
    assert len(set(inst.values())) == 1


def test_a_warning_class_appears_only_where_the_server_marks_something(world):
    s, root, cards, _ = world
    k = by_set(cards)
    for n in ("p1", "p3", "p5"):
        assert not re.search(r'class="[^"]*(warn|bad|flagged)', draw(k[n], s, root).replace('class="state warn"', ""))
    flagged = draw(k["i1"], s, root)
    assert "file flagged" in flagged and "src/other.py" in text_of(flagged)
    assert "cond bad" in draw(k["i2"], s, root)
    ok_card = draw(k["i3"], s, root)
    assert "cond bad" not in ok_card and "file flagged" not in ok_card                  # a condition that does not apply is not drawn as a failed one
    assert '<span class="who mesin">machine</span>' in flagged
