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
    assert tabs == [("chat", "Chat"), ("cards", "Queue"), ("decide", "Decisions"), ("cost", "Cost")]
    assert re.findall(r'data-mode="(\w+)"', HTML) == ["manager", "issue", "prd", "research"]               # the "+" menu of the one box: the foreman first, then New issue; PRD and Research sit behind "More types" (hidden at first); no chips, no Status (tapping the Chat tab again is the overview)
    assert 'id="tabs"' in HTML and 'aria-label="Main navigation"' in HTML


def test_the_page_makes_one_link_out_and_it_is_the_viewer_on_its_own_port_with_no_text_from_a_job():
    anchors = re.findall(r"<a\b[^>]*>", HTML)
    assert len(anchors) == 2 and all('href="http://localhost:8710/"' in a and 'rel="noopener noreferrer"' in a for a in anchors)      # the panel's footer and the ... menu: the same viewer, nothing else
    assert all("8711" not in a and "8712" not in a for a in anchors)


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


# ---- the repository of a code job (it has only a path) and the cost marks, from the Opus review --------------------------------

class Names:
    def __init__(self, *names):
        self.names = names

    def _repo_names(self):
        return list(self.names)


def listed(svc, names):
    chat = rc.Chat(svc.jobs, actions=Names(*names))
    return chat.threads()["threads"][0]


@pytest.mark.parametrize("path, names, want", [("/home/ubuntu/ledger-cli", ("ledger-cli",), "ledger-cli"), ("~/athena/", ("athena",), "athena"),
                                               ("/home/ubuntu/ledger-cli", ("athena",), None), ("/home/ubuntu/ledger-cli", (), None),
                                               ("/home/ubuntu/other", ("ledger-cli",), None), ("/x/..", ("..",), None), (3, ("ledger-cli",), None),
                                               ("/home/ubuntu/ledger-cli\n", ("ledger-cli",), None), ("/" + "a" * 5000, ("a",), None)])
def test_a_code_job_has_the_repo_of_the_last_part_of_its_path_only_when_it_is_a_registered_name(svc, path, names, want):
    set_inputs(svc, repo=path)
    got = listed(svc, names)
    assert got["repo"] == want and path not in json.dumps(got) if isinstance(path, str) and want is None else got["repo"] == want


def test_the_repo_name_of_the_job_wins_and_the_path_never_travels(svc):
    set_inputs(svc, repo="/home/ubuntu/ledger-cli", repo_name="athena")
    got = listed(svc, ("ledger-cli", "athena"))
    assert got["repo"] == "athena" and "/home/ubuntu" not in json.dumps(got)


def test_a_chat_without_actions_lists_the_name_but_never_guesses_from_a_path(svc):
    set_inputs(svc, repo="/home/ubuntu/ledger-cli")
    assert rc.Chat(svc.jobs).threads()["threads"][0]["repo"] is None
    set_inputs(svc, repo_name="ledger-cli")
    assert rc.Chat(svc.jobs).threads()["threads"][0]["repo"] == "ledger-cli"


def test_a_failing_names_source_means_no_guess_and_no_error(svc):
    class Broken:
        def _repo_names(self):
            raise RuntimeError("config")
    set_inputs(svc, repo="/home/ubuntu/ledger-cli")
    assert rc.Chat(svc.jobs, actions=Broken()).threads()["threads"][0]["repo"] is None


def test_a_stage_without_a_cost_is_counted_as_unknown_not_as_nothing(svc):
    p = svc.jobs / tc.JOB / "job.json"
    data = json.loads(p.read_text())
    data["stages"] = {"d1": {"kind": "draft", "status": "DRAFTED", "usd": 0.25}, "d2": {"kind": "draft", "status": "DRAFTED"},
                      "d3": {"kind": "draft", "status": "DRAFTED", "usd": None}}
    p.write_text(json.dumps(data))
    got = svc.get_json("/api/threads")[1]["threads"][0]
    assert got["stages_usd"] == 0.25 and got["stages_unknown"] == 2


# ---- the page: the poll must not draw over a reason being typed ---------------------------------------------------------------

JS = (rc.STATIC_DIR / "app.js").read_text()


def test_the_poll_in_load_only_refreshes_and_never_redraws_the_decisions_page():
    load = JS.split("  function load() {")[1].split("  // ---- C2b")[0]
    assert "loadDecisions(false)" in load and "renderDecisions" not in load and "loadDecisions()" not in load
    ld = JS.split("  function loadDecisions(rerender) {")[1].split("  function showDecision")[0]
    assert 'if (rerender !== false && mode === "decide" && openDecision === null) { renderDecisions(); }' in ld
    assert 'if (rerender !== false) { summary.textContent' in ld                          # a background refresh that fails says nothing on the page
    assert 'if (!(mode === "decide" && openDecision === null)) { loadDecisions(false); }' in load


def test_the_box_is_in_the_chat_tab_only_and_the_plus_menu_closes_with_every_move():
    assert 'document.getElementById("dock").hidden = !inChat;' in JS and "closeMenu();" in JS.split("function setChrome")[1].split("function closeMenu")[0]
    assert "issueForm.hidden = !inChat;" in JS and "chipsOpen" not in JS and "#chips" not in JS
    assert re.search(r'<button id="plus"[^>]*aria-haspopup="menu"[^>]*aria-expanded="false"', HTML) and 'id="plus-menu" role="menu"' in HTML
    assert HTML.index('id="plus"') < HTML.index('<form id="issue-form"') and HTML.count("<button") - HTML.count('data-tab=') >= 8
    css = (rc.STATIC_DIR / "app.css").read_text()
    assert "--on-accent:#120d2b" in css and "--on-accent:#f6f8fa" in css and "#120d2b;" not in css.split("/* UI-3a")[1] and "env(" not in css
    assert "Object.create(null)" in JS.split("function renderList")[1].split("function renderOverview")[0]


def test_the_header_has_an_ellipsis_menu_with_refresh_and_the_viewer_and_no_plus():
    head = HTML.split('<header class="bar">')[1].split("</header>")[0]
    assert 'id="more"' in head and "⋯" in head and 'id="new-request"' not in HTML and ">+<" not in head
    assert 'id="more-menu" role="menu"' in head and 'id="refresh"' in head
    assert 'document.getElementById("refresh").addEventListener("click", function () { closeMenu(); load(); });' in JS
    assert 'document.getElementById("more-menu").hidden = true;' in JS.split("function closeMenu")[1].split("function openNew")[0]


def test_the_chat_tab_opens_on_the_foreman_and_prd_and_research_start_folded():
    assert 'var lastChat = "manager";' in JS
    assert 'else { setMode("manager"); }' in JS and 'if (deep) { setMode("decide")' in JS      # a deep link to a job still opens that job
    assert re.search(r'id="plus-more"[^>]*aria-expanded="false"', HTML)
    for m in ("prd", "research"):
        assert re.search(r'data-mode="%s" class="more-type" hidden' % m, HTML)
    for m in ("manager", "issue"):
        assert re.search(r'data-mode="%s"(?! class="more-type")(?![^>]*hidden)' % m, HTML)
