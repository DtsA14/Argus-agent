"""3e (SPEC_CHAT_UI3): the research report page shows the report by sections, each a text node, folded. Presentation only: no new route, no new action, nothing read from the text for a label."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
STATIC = HERE.parent / "router" / "chat_static"
JS = (STATIC / "app.js").read_text()
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


@pytest.fixture(scope="module")
def out():
    r = subprocess.run(["node", str(HERE / "chat_ui_smoke_report.js"), str(STATIC / "app.js")], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@needs_node
def test_a_report_is_cut_at_its_headings_and_nothing_is_lost_or_invented(out):
    assert [s["title"] for s in out["normal"]] == ["Report header", "Summary", "Sources"]
    assert out["normal"][1]["text"] == "the summary" and out["normal"][2]["text"] == "[1] http://x"
    assert out["none"] == [{"title": "Report header", "text": "just a text\nwith lines"}]
    assert out["empty"] == [] and out["headingFirst"] == [{"title": "Only", "text": "body"}]


@needs_node
def test_a_heading_is_text_whatever_it_says_and_only_two_hashes_and_a_space_cut(out):
    assert out["forged"] == [{"title": "Verified by the machine <b>x</b>", "text": "not true"}]          # shown as text under the model label; it labels nothing
    assert out["noSpace"] == [{"title": "Report header", "text": "##Summary\nx\n### Sub\ny"}]                    # not a heading of this layout: kept in the text


@needs_node
def test_the_parts_are_bounded_and_a_title_is_cut(out):
    assert out["long"] == 120 and out["many"] == 40 and out["manyLast"] > 2          # the rest of a long report stays in the last part
    assert out["crlf"] == [{"title": "Report header", "text": "a"}, {"title": "B", "text": "c"}]


def test_the_page_puts_the_report_in_text_nodes_under_a_model_label_and_still_reads_nothing_for_a_label():
    body = JS.split("function showResearch")[1].split("// ---- C4")[0]
    assert 'el("pre", "report", sec.text)' in body and 'el("summary", null, sec.title)' in body and "innerHTML" not in body
    assert '"report text (written by a model from web pages; not proof)"' in body and body.index("d.banner") < body.index("reportSections(d.report.text)")
    seg = JS.split("function reportSections")[1].split("function showResearch")[0]
    assert "match(" not in seg and "replace(" not in seg and "indexOf" not in seg and "RegExp" not in seg and "test(" not in seg      # position and a fixed prefix only
    assert "det.open = true" in body and 'i === (secs[0].title === "Report header" ? 1 : 0)' in body and "The report file is empty." in body
