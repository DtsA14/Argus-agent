"""C2b (docs/reviews/SPEC_CHAT_APP.md): the issue mode of the page. The script is read as text (no browser here); what is pinned is
what makes the page safe to hold the buttons: the card is the server's and shown as text, Confirm sends the token and nothing else,
is off at first, is never a form's default and is armed only after the server's delay."""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import router.chat as rc  # noqa: E402

JS = (rc.STATIC_DIR / "app.js").read_text()
HTML = (rc.STATIC_DIR / "index.html").read_text()


def js_index(text):
    return JS.index(text)


def test_confirm_sends_the_token_and_nothing_else():
    assert re.findall(r'post\("/api/confirm", (\{[^}]*\})\)', JS) == ["{ token: prep.token }"]
    assert JS.count('post("/api/confirm"') == 1 and JS.count('post("/api/prepare"') == 1


def test_only_two_paths_are_posted_and_every_post_omits_credentials():
    assert sorted(set(re.findall(r'post\("(/[^"]*)"', JS))) == ["/api/confirm", "/api/prepare"]
    assert JS.count('method: "POST"') == 1 and JS.count('credentials: "omit"') == 2      # get() and post()
    assert 'headers: { "Content-Type": "application/json"' in JS


def test_the_confirm_button_is_off_until_the_servers_delay_and_not_a_submit():
    assert 'ok.type = "button";' in JS and "ok.disabled = true;" in JS
    assert js_index("ok.disabled = true;") < js_index("prep.min_delay_s")
    assert "ok.disabled = false" in JS and JS.count("ok.disabled = false") == 1
    assert "Math.ceil((prep.min_delay_s || 1) * 1000)" in JS
    assert "if (ok.disabled) { return; }" in JS                                          # a click on a disabled button does nothing


def test_the_confirm_button_is_never_focused_or_a_default():
    assert ".focus(" not in JS and "autofocus" not in JS and "autofocus" not in HTML
    assert 'el("button", "go", "Konfirmasi")' in JS and JS.count("\"Konfirmasi\")") == 1
    # the card is built outside the form: the form holds the composer only, and its one button is Siapkan (prepare: spends nothing)
    form = re.search(r'<form id="issue-form".*?</form>', HTML, re.S).group(0)
    assert "Konfirmasi" not in form and form.count("<button") == 1 and 'id="prepare"' in form


def test_the_card_is_the_servers_card_shown_field_by_field_as_text():
    assert "fact(c, kv[1]" in JS and "LABELS.forEach" in JS
    assert "document.createTextNode(String(value))" in JS
    assert "Object.keys(card)" not in JS and "for (var" not in JS.split("function renderCard")[1].split("function prepare")[0]


def test_the_page_does_not_build_the_action_from_the_card():
    # prepare takes the action from the button that was pressed; confirm takes the token only: nothing of the card goes back
    body = JS.split("function renderCard")[1].split("function prepare")[0]
    assert "prep.card" in body and "post(" in body
    assert not re.search(r"post\(\"/api/confirm\",[^)]*card", body)


def test_the_issue_chip_is_on_and_the_composer_starts_hidden():
    assert re.search(r'data-mode="issue"[^>]*>Issue<', HTML) and not re.search(r'data-mode="issue"[^>]*disabled', HTML)
    assert re.search(r'<form id="issue-form" hidden[ >]', HTML)
    assert re.search(r'data-mode="research"[^>]*>Riset<', HTML) and not re.search(r'data-mode="research"[^>]*disabled', HTML)   # C3


def test_an_enter_in_the_message_box_does_not_prepare_by_a_hidden_default():
    assert "<textarea" in HTML and '<input id="message"' not in HTML                   # Enter is a newline, not a submit


def test_a_reply_or_discard_is_prepared_from_a_button_not_from_the_card():
    for a in ("issue_reply", "issue_start", "issue_abandon", "issue_new"):
        assert f'action: "{a}"' in JS
    assert JS.count("action:") == 6                                 # the reply is prepared from a button and from the composer; research_new from the composer


def test_the_one_viewer_link_is_still_the_only_link_and_the_handoff_goes_through_its_guard():
    assert "viewerLink(d.handoff ? VIEWER + d.handoff : null)" in JS
    assert JS.count("href") == 1



# ---- Opus review of C2b (2026-11-15): NO-GO on the nested form, and the rest ------------------------------------------------

def test_no_form_is_opened_inside_another_form():
    from html.parser import HTMLParser

    class P(HTMLParser):
        depth = 0
        bad = []

        def handle_starttag(self, tag, attrs):
            if tag == "form":
                if self.depth:
                    self.bad.append(dict(attrs).get("id"))
                self.depth += 1

        def handle_endtag(self, tag):
            if tag == "form":
                self.depth -= 1
    p = P()
    p.feed(HTML)
    assert p.bad == [] and p.depth == 0
    assert HTML.count("<form ") == 2


def test_every_element_the_script_looks_up_by_id_exists_in_the_page():
    ids = set(re.findall(r'id="([^"]+)"', HTML))
    wanted = set(re.findall(r'getElementById\("([^"]+)"\)', JS))
    assert wanted <= ids, wanted - ids


def test_only_one_card_can_be_live_and_a_new_one_settles_the_old():
    body = JS.split("function dropPending")[1].split("function issueCard")[0]
    assert "    if (pending) { pending.settle(); if (pending.parentNode)" in body and body.count("slot.appendChild(c)") == 2
    assert body.index("dropPending();\n      var c = renderCard") > 0
    assert "stream.insertBefore" not in JS                                              # no card is pushed in under the finger


def test_batal_is_off_once_confirm_was_sent_and_a_card_with_a_confirm_on_its_way_is_kept():
    ok = JS.split('ok.addEventListener("click"')[1].split("post(")[0]
    assert "no.disabled = true;" in ok and "c.sent = true;" in ok
    assert "if (pending && pending.sent) { return; }" in JS
    assert "if (busy || (pending && pending.sent)) { return; }" in JS


def test_a_failed_fetch_is_not_shown_as_a_refusal():
    assert "err.answered = true" in JS and "        if (e.answered) {" in JS and "Status tidak diketahui" in JS
    after = JS.split("Status tidak diketahui")[1].split("});")[0]
    assert "loadIssues()" in after


def test_the_form_says_whether_it_makes_a_new_issue_or_a_reply():
    assert "Siapkan balasan" in JS and "Siapkan issue baru" in JS and "repoSel.hidden = r || openIssue !== null" in JS
    assert re.search(r'encodeURIComponent\(id\)\)\.then\(function \(d\) \{\n\s+openIssue = id;', JS)      # set when the thread was read, not before


def test_a_prepare_answered_after_the_user_moved_on_is_dropped():
    assert "if (mode !== ctx.mode || openIssue !== ctx.open) { return; }" in JS


# ---- second Opus review of C2b: the buttons act on their own card, and a card is tied to the issue on screen --------------------

def test_batal_and_tutup_remove_their_own_card_not_the_current_one():
    assert JS.count("{ removeCard(c); }") == 2
    body = JS.split("function removeCard")[1].split("function dropPending")[0]
    assert "if (pending === c) { pending = null; }" in body and "c.settle();" in body


def test_a_prepare_that_resolves_while_a_confirm_is_on_its_way_shows_nothing():
    assert JS.count("if (pending && pending.sent) { return; }") == 3          # dropPending, the .then and the .catch of prepare


def test_a_finished_confirm_draws_the_thread_only_in_issue_mode():
    assert 'if (r.job && mode === "issue") { showIssue(r.job, true); }' in JS


def test_a_card_is_dropped_when_another_issue_or_the_list_is_opened():
    assert "if (!keep && id !== openIssue) { dropPending(); }" in JS
    assert 'back.addEventListener("click", function () { dropPending(); openIssue = null;' in JS
    assert 'showIssue(openIssue, true)' in JS


def test_the_slot_has_a_vh_fallback_before_dvh():
    css = (rc.STATIC_DIR / "app.css").read_text()
    assert "max-height:50vh;max-height:50dvh" in css


# ---- C3: research mode of the page ----------------------------------------------------------------------------------------

def research_part():
    return JS.split("function researchCard")[1].split("function setMode")[0]


def test_the_report_goes_on_the_page_as_text_under_the_servers_banner_and_the_label_comes_from_the_server():
    body = research_part()
    assert 'el("pre", "report", d.report.text)' in body
    assert body.index("d.banner") < body.index("d.report.text")
    assert 'd.checked ? "Sudah dicek oleh e1' in body and "Belum dicek oleh e1." in body
    assert "report.text.indexOf" not in JS and "match(" not in body and "replace(" not in body       # the text is never read for a label


def test_research_mode_prepares_the_question_and_nothing_else():
    assert 'prepare({ action: "research_new", message: message.value })' in JS
    assert re.findall(r'\{ action: "research_new"[^}]*\}', JS) == ['{ action: "research_new", message: message.value }']
    assert "profile:" not in JS and "job: openResearch" not in JS


def test_a_research_job_has_no_action_buttons_only_a_viewer_link():
    body = research_part()
    assert "act(" not in body      # card click and back: nothing posts
    assert "post(" not in body and "prepare(" not in body
    assert 'viewerLink(d.state === "starting" || d.state === "refused" ? null : VIEWER + d.id)' in body


def test_starting_refused_and_stalled_jobs_are_said_so():
    body = research_part()
    for text in ("Riset sedang dimulai", "Ditolak sebelum dimulai", "Terhenti: jalankan argus resume"):
        assert text in body


def test_the_confirm_card_shows_the_go_live_screen_fields():
    for key in ("profile", "stage_models", "stage_caps", "web", "data_sent", "free_models"):
        assert f'["{key}"' in JS


def test_the_form_is_the_research_form_in_research_mode_and_the_repo_is_hidden():
    assert 'var r = mode === "research";' in JS and "Siapkan riset" in JS
    assert 'issueForm.hidden = m === "status";' in JS and 'query.hidden = m !== "status";' in JS


def test_a_finished_research_confirm_opens_the_job_in_research_mode_only():
    assert 'if (mode === "research") { loadResearch(); if (r.job) { showResearch(r.job); } return; }' in JS
    assert "if (mode !== \"research\") { return; }" in research_part()                 # a late answer after the user left the mode draws nothing


def test_the_poll_does_not_redraw_research_while_a_confirm_is_on_its_way():
    assert 'if (mode === "research" && !(pending && pending.sent))' in JS


def test_the_report_box_wraps_and_is_bounded():
    css = (rc.STATIC_DIR / "app.css").read_text()
    assert ".report{white-space:pre-wrap" in css and "max-height:60vh" in css
