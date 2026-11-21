"""T3a presentation change (SPEC_KARTU_SETUJU): the plan card and the install card are drawn in sections that are questions, and nothing the server sends is dropped
from the screen. Source tests always run; the rendering tests run the real drawing code in V8 (mini-racer) on the JSON of the 12 T3a cards and are skipped without it."""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from router import chat as rc  # noqa: E402

JS = (rc.STATIC_DIR / "app.js").read_text()
BLOCK = JS[JS.index("  // ---- T3: the plan card"):JS.index("  // ---- T2: read-only cards")]
CSS = (rc.STATIC_DIR / "app.css").read_text()

# the fields the screen showed before this change (read from the old code): every one must still be on the screen
PLAN_FIELDS = ["id", "state", "repo", "turn", "stale", "superseded", "why", "request", "request_by", "request_truncated", "summary", "summary_why", "issue_count", "cost",
               "ratio_text", "spent", "proposed", "proposed_each", "reference", "median", "defects", "fixed_line", "domain_read_label", "items", "title", "warning", "no_examples",
               "examples", "withheld", "domain_read", "fresh", "verdict", "at", "sources", "note", "says", "showable", "call", "assumptions", "inputs", "output", "raises",
               "proof", "wording"]
INSTALL_FIELDS = ["id", "state", "repo", "patch_sha12", "purpose", "by", "title", "text", "cost", "cap", "cap_median", "fixed_line", "open", "checks", "key", "ok", "label", "why",
                  "item", "files", "marks", "path", "files_cut", "scope_note", "patch_read", "patch_read_label", "patch_reader_tested", "domain_reader_tested", "approval", "note"]


@pytest.mark.parametrize("field", sorted(set(PLAN_FIELDS + INSTALL_FIELDS)))
def test_every_field_the_old_cards_showed_is_still_read_by_the_drawing_code(field):
    assert re.search(r"[.\[\"']" + field + r"\b", BLOCK), field


# one line of the drawing code per displayed thing: a deleted or disabled line fails here even when its field name is read elsewhere
SNIPPETS = ['r.verdict === "ok" ? "say" : "say warn"', 'x.verdict === "ok" || nit ? "say" : "say warn"', 's5.appendChild(el("p", "say", d.fixed_line))', 's7.appendChild(el("p", "say", d.fixed_line))', 'if (d.why) { card.appendChild(el("p", "note", d.why)); }', 'if (d.stale) {', 'if (d.superseded) {', 'if (d.request_truncated)', "s2.appendChild(el(\"p\", \"note\", d.summary_why))",
            'if (d.defects) {', 'kv(d, "Andaikan", a.name + " = " + a.shown)', 'kv(d, "masukan " + i.name, i.shown)', 'kv(d, "fungsi", e.call)', "e.proof.wording",
            'if (it.warning) { c.appendChild(el("p", "note", it.warning)); }', 'modelLine(c, "tanpa contoh: " + it.no_examples)', 'if (it.why) {', '"contoh ditahan harness"',
            'if (r.second) { line(r.second, 2); }', 'who_(r.reader2)', "(r.sources || []).join", "r.at + \": \"", "if (d.approval) {", 'f.marks.join("; ")', 'if (d.files_cut)', 'if (d.scope_note)',
            'd.patch_sha12 ? [{ text: "patch " + d.patch_sha12', 'd.turn ? [{ text: "giliran " + d.turn }]', "c.why ? \" - \" + c.why : \"\"", 'modelLine(s1, d.purpose.text)',
            'd.patch_reader_tested ?', 'c.ok === false ? "cond bad"', 'p.appendChild(who("mesin", "mesin"))', '"say big"', 'd.domain_reader_tested ?', "if (d.item) { s2.appendChild(planItem(d.item, false)); }", "d.cost.reference.cap_median"]


@pytest.mark.parametrize("snippet", SNIPPETS)
def test_each_displayed_thing_has_its_own_line_in_the_drawing_code(snippet):
    assert snippet in BLOCK, snippet


def test_no_status_is_counted_in_the_headline_and_the_back_handler_settles_the_card():
    count = BLOCK[BLOCK.index("function countLine"):BLOCK.index("function planItem")]
    assert "status" not in count and "proof" not in count
    nav = BLOCK[BLOCK.index("function cardButtons"):BLOCK.index("function showPlan")]
    assert "cardSeq++; openCard = null; renderCards(); loadCards();" in nav


def test_the_purpose_is_labelled_model_only_when_the_server_says_the_model_wrote_it():
    assert '/model/.test(String(d.purpose.by)) ? "model" : "tak"' in BLOCK


def test_a_reader_that_is_not_a_kind_and_id_is_not_named_undefined():
    assert "typeof r === \"object\"" in BLOCK and "r.reader.kind" not in BLOCK


def test_the_second_readers_are_shown_too():
    for field in ("second", "reader", "reader2"):
        assert "." + field in BLOCK


def test_no_colour_or_class_comes_from_a_number_or_from_the_cost_ratio():
    assert not re.search(r"\.ratio\b(?!_text)", BLOCK) and not re.search(r"parseFloat|Number\(|\bratio_text\s*[<>]", BLOCK)                     # only the machine's words (ratio_text), never the number
    assert "gradient" not in CSS and "scale" not in CSS.split("T3 cards")[1]


def test_the_cards_still_have_no_button_that_decides_anything():
    # SPEC_CHAT_T4A: the plan card has one live button ("Setujui rencana", prepared with the job id only) and one disabled placeholder; nothing else decides
    assert re.findall(r'el\("button", null, "([^"]+)"', BLOCK) == ["Semua kartu", "Jalankan antrean (belum aktif)"] and re.findall(r'\{ text: "([^"]+)", fn:', BLOCK) == ["Kartu teknis"]
    assert re.findall(r'el\("button", "go", "([^"]+)"', BLOCK) == ["Setujui rencana"]
    assert not re.search(r'method:\s*"POST"|\.post\(', BLOCK) and BLOCK.count("prepare(") == 1 and 'prepare({ action: "prd_approve", job: id })' in BLOCK


def test_the_request_is_labelled_atha_only_when_the_server_says_it_came_through_the_chat():
    assert re.search(r'request_by === "chat" \? "atha" : "tak"', BLOCK)
