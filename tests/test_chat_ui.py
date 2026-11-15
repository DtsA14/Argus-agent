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
    assert re.search(r'<form id="issue-form" hidden>', HTML)
    assert 'data-mode="research" disabled' in HTML                                    # research is C3


def test_an_enter_in_the_message_box_does_not_prepare_by_a_hidden_default():
    assert "<textarea" in HTML and '<input id="message"' not in HTML                   # Enter is a newline, not a submit


def test_a_reply_or_discard_is_prepared_from_a_button_not_from_the_card():
    for a in ("issue_reply", "issue_start", "issue_abandon", "issue_new"):
        assert f'action: "{a}"' in JS
    assert JS.count("action:") == 5                                 # the reply is prepared from a button and from the composer


def test_the_one_viewer_link_is_still_the_only_link_and_the_handoff_goes_through_its_guard():
    assert "viewerLink(d.handoff ? VIEWER + d.handoff : null)" in JS
    assert JS.count("href") == 1

