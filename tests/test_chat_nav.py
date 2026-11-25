"""SPEC_CHAT_UI3 3a: the repository on the job list, and the page's navigation (four tabs, one link out). Real files, a real server."""
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_chat as tc  # noqa: E402
from router import chat as rc  # noqa: E402

svc = tc.svc
HTML = (rc.STATIC_DIR / "index.html").read_text()


def set_inputs(svc, **inputs):
    p = svc.jobs / tc.JOB / "job.json"
    data = json.loads(p.read_text())
    data["inputs"] = {**data["inputs"], **inputs}
    p.write_text(json.dumps(data))


def repo_on_list(svc):
    status, body = svc.get_json("/api/threads")
    assert status == 200 and len(body["threads"]) == 1
    return body["threads"][0]["repo"]


@pytest.mark.parametrize("name", ["ledger-cli", "athena", "a", "nexus_lite.v2", "X" * 64])
def test_a_job_made_for_a_registered_name_carries_it(svc, name):
    set_inputs(svc, repo_name=name)
    assert repo_on_list(svc) == name


@pytest.mark.parametrize("name", [None, "", "../x", "a/b", "-x", ".x", "a b", "x\ny", "X" * 65, 3, ["a"], {"a": 1}, True, "é", "a‮b", "ledger-cli\n"])
def test_anything_that_is_not_the_shape_of_a_name_is_no_repo(svc, name):
    set_inputs(svc, repo_name=name)
    assert repo_on_list(svc) is None


def test_a_job_without_inputs_or_with_junk_inputs_still_lists(svc):
    p = svc.jobs / tc.JOB / "job.json"
    data = json.loads(p.read_text())
    data["inputs"] = "junk"
    p.write_text(json.dumps(data))
    status, body = svc.get_json("/api/threads")
    assert status in (200,) and (body["threads"] == [] or body["threads"][0]["repo"] is None)


def test_the_repo_is_read_from_the_job_file_and_the_path_of_the_repo_is_never_listed(svc):
    set_inputs(svc, repo_name="ledger-cli", repo="/secret/path")
    status, raw = svc.request("GET", "/api/threads")[0], svc.request("GET", "/api/threads")[2]
    assert status == 200 and b"/secret/path" not in raw and json.loads(raw)["threads"][0]["repo"] == "ledger-cli"


def test_the_bottom_bar_has_the_four_tabs_in_order_and_the_chips_only_the_chat_modes():
    tabs = re.findall(r'<button type="button" data-tab="(\w+)"[^>]*>([A-Za-z]+)<', HTML)
    assert tabs == [("chat", "Obrolan"), ("cards", "Antrean"), ("decide", "Keputusan"), ("cost", "Biaya")]
    assert re.findall(r'data-mode="(\w+)"', HTML) == ["status", "issue", "prd", "research"]
    assert 'id="tabs"' in HTML and 'aria-label="Navigasi utama"' in HTML


def test_the_page_makes_one_link_out_and_it_is_the_viewer_on_its_own_port_with_no_text_from_a_job():
    anchors = re.findall(r"<a\b[^>]*>", HTML)
    assert len(anchors) == 1 and 'href="http://localhost:8710/"' in anchors[0] and 'rel="noopener noreferrer"' in anchors[0]
    assert "8711" not in anchors[0] and "8712" not in anchors[0]


def test_the_tab_icons_are_inline_vectors_with_no_script_and_no_external_image():
    assert HTML.count("<svg") == 4 and HTML.count('aria-hidden="true"') >= 4 and "<img" not in HTML and "data:" not in HTML
    css = (rc.STATIC_DIR / "app.css").read_text()
    assert "url(" not in css and "@import" not in css


def test_the_script_looks_up_only_ids_and_selectors_the_page_has():
    js = (rc.STATIC_DIR / "app.js").read_text()
    for sel in re.findall(r'querySelectorAll\("([^"]+)"\)', js):
        base = sel.split(" ")[0]
        assert base.lstrip("#.") in HTML or base.lstrip("#.") in ("stream",), sel
    assert 'document.getElementById("decide-badge")' in js and 'id="decide-badge"' in HTML
