"""P3 (SPEC_CHAT_MANAGER_P3): the foreman on the page. The page's own functions run in node on a tiny DOM (skipped without `node`); the static facts are read from the files."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
STATIC = HERE.parent / "router" / "chat_static"
JS = (STATIC / "app.js").read_text()
HTML = (STATIC / "index.html").read_text()
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


@pytest.fixture(scope="module")
def out():
    r = subprocess.run(["node", str(HERE / "chat_ui_smoke_manager.js"), str(STATIC / "app.js")], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_the_plus_menu_offers_the_foreman_and_the_script_knows_the_mode():
    assert re.search(r'data-mode="manager"[^>]*>Foreman<', HTML) and not re.search(r'data-mode="manager"[^>]*disabled', HTML)
    assert 'm === "manager"' in JS and 'else if (m === "manager") { openIssue = null; formState(); loadManager(); }' in JS
    chrome = JS.split("function setChrome()")[1].split("function closeMenu")[0]
    assert 'mode === "manager"' in chrome and 'mode === "manager"' in JS.split("function updateSummary")[1].split("function setChrome")[0] + chrome
    assert "message.maxLength = f ? 2000 : 6000;" in JS


def test_the_turn_is_posted_with_the_session_and_the_message_and_nothing_else():
    assert re.findall(r'post\("/api/manager/turn", (\{[^}]*\})\)', JS) == ['{ session: job, message: text }']
    assert JS.count('post("/api/manager/turn"') == 1


def test_nothing_of_a_proposal_goes_to_confirm_and_the_proposal_text_is_only_ever_a_text_node():
    box = JS.split("function proposalBox")[1].split("function renderManager")[0]
    assert "/api/confirm" not in box and "token" not in box and "innerHTML" not in JS
    assert box.count("prepare(body)") == 1 and box.count('prepare({ action: "issue_new"') == 1 and box.count("prepare(") == 2
    assert re.findall(r'\{ action: "(\w+)"', box) == ["issue_new", "prd_new", "research_new"]
    assert "body.source_job = mgr.job" in box and "body.source_turn = String(e.n)" in box


def test_the_source_is_added_to_a_form_only_from_a_proposal_and_every_move_clears_it():
    assert JS.count("fromProposal = null;") >= 2 and "fromProposal = { job: job, turn: e.n }" in JS
    prep = JS.split("function prepare(body)")[1].split("var ctx")[0]
    assert 'body.action === "research_new" || body.action === "prd_new" || body.action === "issue_new"' in prep and "body.source_job === undefined" in prep
    assert "issue_reply" not in prep and "issue_*" not in prep and 'indexOf("issue' not in prep
    setmode = JS.split("function setMode(m)")[1].split("issueForm.hidden")[0]
    assert "fromProposal = null;" in setmode and "mgrStop();" in setmode


def test_the_card_of_a_session_shows_what_one_confirmation_covers_and_where_a_text_came_from():
    for k in ("ttl_hours", "max_turns", "turn_note", "confirms", "source_note"):
        assert f'["{k}"' in JS
    assert "the foreman's proposal" in JS and "edited by you" in JS


@needs_node
def test_the_foreman_view_is_text_with_its_speaker_and_the_budget_and_time_left(out):
    h = out["open"]
    assert "left $0.1996 of $0.2000" in h and "time left 11 h 59 min" in h
    assert "<p.msg human mine>ide <b>x</b></p>" in h                    # a tag in the text is text, not markup (the fake DOM prints text as it is)
    assert "foreman (a model, not Argus)" not in h and h.count("<p.say foreman>") == 5 and "reason (written by the model)" in h
    assert "The foreman is waiting for your answer." in h and "The foreman sees no route for this in Argus." in h
    assert "This turn failed: unusable" in h and "Nothing is started." in h
    assert "The foreman is answering." in out["busy"] and "left unknown" in out["blocked"]
    assert "Prepare a session" in out["none"] and "Prepare a session" not in out["starting"] and "The session is starting." in out["starting"]


@needs_node
def test_a_proposal_button_prepares_the_form_with_its_source_and_starts_nothing(out):
    assert out["buttons"] == ["Prepare", "Edit first", "Prepare", "Edit first"]
    assert [json.loads(x) for x in out["prepared"]] == [
        {"action": "prd_new", "repo": "ledger-cli", "message": "Tambah <b>ringkasan</b>", "source_job": "j20261126_023857_708b", "source_turn": "1"},
        {"action": "research_new", "message": "Bandingkan dua pustaka", "source_job": "j20261126_023857_708b", "source_turn": "4"}]
    assert out["norepo"] == ["Prepare[off]", "Edit first"]


@needs_node
def test_edit_first_opens_the_form_filled_and_remembers_the_source(out):
    modes, text, repo, src = json.loads(out["edit"])
    assert modes == ["prd"] and text == "Tambah <b>ringkasan</b>" and repo == "ledger-cli" and src == {"job": "j20261126_023857_708b", "turn": 1}


@needs_node
def test_a_turn_is_sent_only_into_an_open_idle_session_with_a_message(out):
    for k in ("sendNoSession", "sendBusy", "sendEnded", "sendEmpty"):
        assert json.loads(out[k])[0] == []
    assert "no open foreman session" in out["sendNoSession"] and "still answering" in out["sendBusy"]
    posted, notes, box, left, polling = json.loads(out["sendOk"])
    assert posted == ['/api/manager/turn {"session":"j20261126_023857_708b","message":"halo mandor"}'] and notes == [] and box == "" and left == 59 and polling is True
    posted, notes, kept, stuck = json.loads(out["sendRefused"])
    assert notes == ["Could not send: the session is busy"] and kept == "halo lagi" and stuck is True          # a refused turn keeps what was typed, and the card then offers a new session
    assert out["timeLeft"] == "11 h 59 min|0 h 1 min|unknown|unknown"


@needs_node
def test_a_session_that_cannot_take_a_turn_offers_a_new_one(out):
    o = out["over"]
    assert o["healthy"] is False and o["fine"] is False and o["busy"] is False
    assert o["expired"] is True and o["poor"] is True and o["turns"] is True and o["stuck"] is True


@needs_node
def test_two_quick_sends_post_once(out):
    assert json.loads(out["double"]) == [1, "The foreman is still answering."]


@needs_node
def test_a_turn_answered_after_the_person_left_the_mode_draws_and_polls_nothing(out):
    box, timer, timers, sending = json.loads(out["leave"])
    assert box == "form lain" and timer is None and timers == 0 and sending is False


@needs_node
def test_the_polls_and_the_session_search_are_bounded(out):
    assert out["pollDone"] == "0|"                               # the answer is in: no read, no timer
    assert out["pollBound"] == "2|"                              # three reads allowed: two taken, then it stops
    assert out["search"] == "13|0"                               # one read and twelve retries, then none


def test_the_source_is_cleared_after_a_confirm_and_the_new_session_card_has_its_own_texts():
    cb = JS.split("var c = renderCard(prep, function (r) {")[1].split("mgr.expect = 12")[0]
    assert "fromProposal = null;" in cb
    assert 'card.action === "manager_new" ? "The session is being made' in JS and 'card.action === "manager_new" ? "Foreman view"' in JS
    assert 'p.route !== "research" && p.route !== "prd"' in JS


@needs_node
def test_next_steps_are_the_harness_sentences_as_text_and_their_buttons_only_move_the_person(out):
    h = out["next"]
    assert "Next steps (from the harness, not the foreman)" in h and "Research · REPORT_READY · $0.1050:" in h and "PRD · AWAITING_HUMAN · $0.0000:" in h
    assert "Research · RESEARCHING:" in h and "<b>x</b>" in h                # no figure when there is none; a tag in the text is text
    assert out["nextButtons"][:2] == ["Open the report", "Open the Queue tab"] and out["nextNone"] is False
    modes, shown, prepared, posted = json.loads(out["nextClicks"])
    assert modes == ["research", "cards"] and shown == ["j20261126_052522_fcc7"]
    assert prepared == len(out["prepared"]) == 2 and posted == 0              # only the two proposal clicks of the earlier scenario prepared anything; a next-step button adds none


def test_the_next_steps_box_posts_and_prepares_nothing():
    box = JS.split("function nextStepsBox")[1].split("function renderManager")[0]
    assert "post(" not in box and "prepare(" not in box and "/api/" not in box and "innerHTML" not in box
    assert 'setMode("research"); showResearch(n.job);' in box and 'setMode("cards");' in box


def test_a_next_steps_value_that_is_not_a_list_draws_no_box():
    assert "Array.isArray(d.next_steps) && d.next_steps.length" in JS


@needs_node
def test_an_issue_proposal_has_prepare_with_its_source_and_edit_first_that_keeps_it(out):                 # F44: SPEC_FOREMAN_ISSUE_PREPARE
    assert out["issueButtons"] == ["Prepare", "Edit first"] and out["issuePrepared"] == 0
    assert "The foreman proposes: an issue" in out["issueHtml"] and "Repo: ledger-cli" in out["issueHtml"] and "Nothing is started." in out["issueHtml"]
    assert [json.loads(x) for x in out["issueBodies"]] == [{"action": "issue_new", "repo": "ledger-cli", "message": "Tambah opsi --month <b>x</b>",
                                                             "source_job": "j20261126_023857_708b", "source_turn": "1"}]
    modes, text, repo, src, notes, prepared = json.loads(out["issueEdit"])
    assert modes == ["issue"] and text == "Tambah opsi --month <b>x</b>" and repo == "ledger-cli" and src == {"job": "j20261126_023857_708b", "turn": 1} and notes == [] and prepared == 0
    modes, text, repo, notes, src = json.loads(out["issueUnlisted"])
    assert modes == ["issue"] and repo == "" and notes == ["The proposed repository bulking-app is not in the list: choose one."] and src == {"job": "j20261126_023857_708b", "turn": 1}
    assert out["issueNoRepo"] == ["Prepare[off]", "Edit first"] and "Repo: none named: use Edit first" in out["issueNoRepoHtml"]


def test_the_issue_proposal_code_is_text_only_saves_the_session_before_the_mode_move_and_never_sends_a_reply_with_a_source():
    box = JS.split("function proposalBox")[1].split("function nextStepsBox")[0]
    issue = box.split('if (p.route === "issue") {')[1].split("return b;")[0]
    assert "innerHTML" not in issue and issue.count('el("button"') == 2 and 'igo.disabled = !p.repo' in issue
    assert issue.index("var job = mgr.job;") < issue.index('setMode("issue");') < issue.index("fromProposal = { job: job, turn: e.n };")
    assert 'repoSel.options' in issue and "repoSel.value" in issue
    assert 'prepare({ action: "issue_new", repo: p.repo, message: p.text, source_job: mgr.job, source_turn: String(e.n) })' in issue
    show = JS.split("function showIssue")[1].split("get(")[0]
    assert "if (!keep) { fromProposal = null; }" in show
    assert "openIssue = null; fromProposal = null; formState(); renderIssues();" in JS


def test_a_confirmed_issue_card_from_the_foreman_goes_to_the_writing_and_keeps_the_started_card():       # F46
    cb = JS.split('var c = renderCard(prep, function (r) {')[1].split("pending = c;")[0]
    man = cb.split('if (mode === "manager") {')[1].split("return;")[0]
    assert 'body.action === "issue_new" && r.job' in man and 'showIssue(r.job, true)' in man and 'setMode("issue")' in man
    assert man.index("var keepCard = pending; pending = null;") < man.index('setMode("issue")') < man.index("pending = keepCard;") < man.index("showIssue(r.job, true)")
    assert 'body.action === "manager_new"' in man and "research_new" not in man and "prd_new" not in man          # research and PRD stay where they are
