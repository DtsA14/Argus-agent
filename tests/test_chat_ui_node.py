"""The page's own code, run in node on a tiny DOM (no browser): the queue card's step button, the two confirmation cards of T4b and the money button of the plan card. Skipped without
`node`. The functions are cut out of app.js by name, so a syntax error or a changed call shows here, not in the phone."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
APP = HERE.parent / "router" / "chat_static" / "app.js"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def node(*args):
    r = subprocess.run(["node", *map(str, args)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_app_js_is_valid_javascript():
    node("--check", APP)


def test_the_step_button_and_the_two_confirmation_cards_draw_and_prepare_the_queue_id_only():
    out = json.loads(node(HERE / "chat_ui_smoke_steps.js", APP))
    assert json.loads(out["queue_step"]["prepared"]) == [{"action": "queue_step", "queue": "q20261117T100400Z-abcd"}]
    assert json.loads(out["draft_approve"]["prepared"]) == [{"action": "draft_approve", "queue": "q20261117T100400Z-abcd"}]
    assert out["null"]["prepared"] is None and "<button" not in out["null"]["html"]
    assert "Draft sha: </b>aaaaaaaaaaaa" in out["card:draft_approve"] and "tests/test_a.py::test_x" in out["card:draft_approve"] and "(written by a model)" in out["card:draft_approve"]
    rich, note = out["card:draft_approve:3"], out["card:draft_approve:4"]
    assert "This draft changes existing tests: tests/test_old.py and 2 more" in rich and "<details.more>" in rich
    assert "Text by the writer (a model), not proof" in rich and "it may break b" in rich and "no baseline recorded" in rich
    assert "<b>do</b> the thing" in rich and "<b>do</b>" not in rich.replace("&lt;", "").replace("<b>do</b> the thing", "")   # a tag in the text stays text: it is a text node, never markup
    assert "The plan summary is not available" in note and "<details" not in note and "changes existing tests" not in note
    chat, term = out["card:prd_approve:5"], out["card:prd_approve:6"]
    assert "first request, started from the chat (recorded via the UI)" in chat and "… (cut)" in chat and "2 replies from the terminal are not shown" in chat
    assert "reference repos (read by the writer, read only)" in chat and "ledger-cli@abcdef123456, athena@123456abcdef" in chat
    assert "<details.more>" in chat and "Writer's summary (written by a model, not proof)" in chat and "</span>ringkasan <b>penulis</b></p></details>" in chat   # the tag is the text of a text node inside the fold
    assert "first request, from the terminal (a person or a Claude session, not recorded)" in term and "(cut)" not in term and "replies from the terminal" not in term
    assert "The reference repos cannot be read" in term and "<details" not in term
    assert "Drafter limit" in out["card:queue_step"] and "issue text" in out["card:queue_step"] + out["card:draft_approve"]


def test_the_money_button_waits_for_the_ack_and_the_reason_and_sends_only_what_the_server_named():
    lines = dict(x.rsplit(": ", 1) for x in node(HERE / "chat_ui_smoke_go.js", APP).strip().splitlines())
    assert lines["start disabled"] == "true" and lines["ack only: disabled"] == "true" and lines["short reason: disabled"] == "true" and lines["ack+reason: enabled"] == "true"
    assert json.loads(lines["prepared"]) == {"action": "queue_go", "job": "j20261117_100000_aaaa", "ack": "1,3", "reason": "alasan yang cukup panjang"}
    assert lines["unticked: disabled and nothing sent"] == "true"
    assert lines["no needs: enabled, sends job only"] == json.dumps({"action": "queue_go", "job": "j20261117_100000_aaaa"}, separators=(",", ":"))
    assert json.loads(lines["ack only"]) == {"action": "queue_go", "job": "j20261117_100000_aaaa", "ack": "2"}


def test_the_panel_groups_by_repo_filters_and_the_cost_view_and_badge_say_what_they_know():
    out = json.loads(node(HERE / "chat_ui_smoke_nav.js", APP))
    a = out["all"]
    assert a.index("ledger-cli") < a.index("athena") < a.index("constructor") < a.index("No repo")                                      # the jobs without a repo come last
    assert "<span.gn>ledger-cli</span><span.gw>1 waiting</span>" in a and "<span.gn>athena</span><span.gc>1 job</span>" in a and "<span.gn>constructor</span>" in a        # a repo named like an object method is only a name
    assert "[true]" in a and "Antrean <b>x</b>" in a and "Dexie atau idb" not in a.split("No repo")[0]       # a tag in a title is the text of a text node
    assert "PRD kategori" in a and "<span.kt>research</span>" not in a.split("athena")[0]
    w = out["waiting"]
    assert "Antrean <b>x</b>" in w and "PRD kategori" not in w and "athena" not in w and "No repo" not in w
    r = out["research"]
    assert "Dexie atau idb" in r and "ledger-cli" not in r
    t = out["toggled"]
    assert "[false]" in t and "PRD kategori" not in t and "buffer" in t                                          # a closed group shows no job; an opened one does
    assert "No matching jobs." in out["none"]
    assert out["badge1"] == "false|1" and out["badge0"] == "true|0" and out["badge12"] == "false|9+"
    assert out["summary"] == "5 jobs · 12 waiting" and out["panelcost"] == "Recorded stage cost: $0.2400"
    c = out["cost"]
    assert "Recorded stage cost" in c and "Total (5 jobs in the list): $0.2400" in c and "Code: $0.0300" in c and "Research: $0.1400" in c and "PRD: $0.0700" in c
    assert "1 job has a stage with no cost figure: not counted, not zero." in c
    assert "Only stage figures recorded in the job list (the newest only)." in c and "ledger-cli: PRD kategori" in c and "athena: buffer" not in c   # a job that cost nothing is not listed


def test_the_decisions_page_lists_what_waits_with_fixed_labels_counts_a_draft_job_once_and_says_when_it_may_be_incomplete():
    out = json.loads(node(HERE / "chat_ui_smoke_nav.js", APP))
    assert out["need"] == "false|5|5 jobs · 5 waiting|5 items waiting for you"            # 4 waiting rows + the one open job that is not the draft's own job (jc counts once)
    d = out["decisions"]
    assert d.index("Waiting for you") < d.index("Open jobs") and "Plan ready for your decision" in d and "Draft of issue 2 is ready for you" in d
    assert "Start issue 3 (drafter)" in d and "Queue waits for your go (money)" in d and "a <b>plan</b>" in d and "old job" in d and "draft job" not in d
    n = out["decisionsNotes"]
    assert "The daily cap could not be computed: the queue's go and the steps of queues whose go was more than 24 hours ago are not listed." in n and "Not everything was checked: this list may be incomplete." in n
    assert "Nothing is waiting for you." in out["nothing"] and "Waiting for you" not in out["nothing"] and "Open jobs" not in out["nothing"]
    w = out["panelwaiting"]
    assert "draft job" in w and "other" not in w                                          # the panel's Waiting filter follows the waiting rows' jobs too


def test_the_queue_progress_bar_counts_only_applied_items_and_is_absent_without_a_state_or_a_count_or_when_closed():
    out = json.loads(node(HERE / "chat_ui_smoke_nav.js", APP))
    bars = [b.split("|")[0] for b in out["bars"]]
    assert bars == ["5/5", "", "", "3/1", "", ""]                                  # DONE 5/5, CLOSED none, no state none, WAITING 3/1, a PRD none, a queue of 0 items none
    n = out["nulls"]
    assert "Start the next issue (drafter)" in n and "Draft of the next issue is ready for you" in n and "null" not in n and "undefined" not in n
    assert "Could not refresh this list: the rows shown may be out of date." in n
    assert n.count("athena") == 1                                                    # a queue row whose title is its repository's name shows it once


def test_the_cost_view_has_two_different_numbers_booked_and_recorded_and_never_shows_unknown_as_zero():
    out = json.loads(node(HERE / "chat_ui_smoke_nav.js", APP))
    assert "Loading…" in out["costNull"] and "Booked against the daily cap" in out["costNull"]
    ok = out["costOk"]
    assert "Booked (last 24 hours): $1.08 of $7.00" in ok and "Left: $5.92" in ok and out["bar"] == "7/1.08"
    assert "The cap counts the full limit of every job, start, reply and queue started from this chat in the last 24 hours, not what they spent. A request whose own limit is more than Left is refused." in ok
    assert "Left: $0.00" in out["costOver"] and out["barOver"] == "7/7"                 # over the cap: the bar stops at full, nothing is negative
    for key in ("costUnknown", "costFailed"):
        assert "The daily cap could not be computed right now." in out[key] and "Booked (last 24 hours)" not in out[key] and "$0.00" not in out[key].split("Recorded in the last 24 hours")[0]
    assert "Booked (last 24 hours)" in out["costZero"] and "$0.00 of $0.00" in out["costZero"] and "<progress" not in out["costZero"]       # a cap of 0 has no bar
    day = out["cost"].split("Recorded in the last 24 hours")[1].split("Recorded stage cost")[0]
    assert "Total (3 jobs created): $0.1700" in day and "Code: $0.0300" in day and "Research: $0.1400" in day and "PRD" not in day.replace("Recorded", "")     # j2 is 25 hours old, j5 has no readable date
    assert "Money still being spent by a running stage is not in it yet." in day
    allj = out["cost"].split("Recorded stage cost")[1]
    assert "Total (5 jobs in the list): $0.2400" in allj and "PRD: $0.0700" in allj and "1 job has a stage with no cost figure: not counted, not zero." in allj


def test_the_cost_view_survives_odd_numbers_and_reads_the_24_hours_from_the_job_id():
    out = json.loads(node(HERE / "chat_ui_smoke_nav.js", APP))
    s = out["costStrings"]
    assert "The daily cap could not be computed right now." in s and "Booked (last 24 hours)" not in s and "The cap counts the full limit" in s     # a number that arrives as text is no number; the note stays
    assert "Booked (last 24 hours): $7.00 of $7.00" in out["costRound"] and "Left: $0.00" in out["costRound"]
    # 12:00 on 2026-11-25 is "now": 4 h old yes; 25 h no; exactly 24 h yes; 23 h 59 min 59 s yes; 2027 no; one second in the future no; not a job id no; upper case hex no
    assert out["recent"] == "10110000"
    assert "The list holds only the newest 100 jobs: this total may be incomplete." in out["cost100"] and "may be incomplete" not in out["cost"]


def test_the_draft_page_marks_every_diff_line_by_its_first_character_shows_notes_as_model_text_and_leaves_the_page_when_the_tab_changed():
    out = json.loads(node(HERE / "chat_ui_smoke_draft.js", APP))
    assert out["blockLines"] == "hdr,hdr,hunk,ctx,del,add,add,del,ctx,add"               # `+++i;` is an added line, `--x` a removed one: only the first two lines are headers
    assert "<div.dl.add>+<b>tag</b></div>" in out["blockText"]                              # a tag in the text is the text of a text node
    p = out["page"]
    assert "Draft details" in p and "Draft sha: </b>aaaaaaaaaaaa" in p and "may write" in p and "tests/test_a.py::test_x" in p
    assert "old text matches the recorded hash" in p and "no recorded hash to check the old text against" in p
    assert "the old text does NOT match the recorded hash: this diff may not be against the version the drafter saw" in p and "The diff is cut here: it is longer than the page shows." in p
    assert "No difference between the old text and the new text." in p
    assert "removed (written by a model)" in p and "no <i>longer</i> true" in p and "modified (written by a model)" in p
    assert "(path not shown)" in p and "the path is not shown" in p and "unavailable" in p
    assert "Only the first 6 of 7 files are shown." in p and "The writer's plan is not available for this draft." in p
    assert "step (written by a model)" in p and "risk (written by a model)" in p and "not proven by the machine (written by a model)" in p
    assert out["state"] == "1;j20261117_110000_aaa1;draft;/api/draft/j20261117_110000_aaa1"
    assert "None: the draft only adds new tests." in out["none"] and "Only the first" not in out["none"]
    assert "The draft details cannot be read." in out["failed"]
    assert out["leftTab"] == "<section></section>"                                            # an answer that arrives after the person left the Queue tab draws nothing
    assert out["stale"] == "<section></section>" and out["fresh"] is True                      # an older answer draws nothing; the newest does
    assert "The list of changed tests cannot be read." in out["unreadable"] and "None: the draft only adds new tests." not in out["unreadable"]


# ---- SPEC_CHAT_APPLY_REPLY PR3: the real installActions and replyBox on a tiny DOM -----------------------------------------------------------

def test_the_reply_box_and_the_install_buttons_open_only_when_the_rules_say_and_send_only_the_allowed_fields():
    out = json.loads(node(HERE / "chat_ui_smoke_apply.js", APP))
    assert out["reply_buttons"] == [["", "Prepare reply", True]] and out["reply_value_empty"] == "" and out["reply_click_while_empty"] == "[]"
    assert json.loads(out["reply_sent"]) == [{"action": "prd_reply", "job": "j1", "message": "use two decimals"}]
    assert "<textarea" in out["reply_write_failed"] and "Prepare reply" in out["reply_write_failed"]       # a failed write can be answered too
    assert all(h == "<div.nav></div>" for h in out["reply_other_states"])                       # no box on a plan that is approved, being written or accepted
    assert out["reader_buttons"] == [["go", "Run the two patch readers (money is spent)", False]]
    assert json.loads(out["reader_sent"]) == [{"action": "patch_read_run", "job": "j1"}]
    for k in ("install_fine", "install_concern"):
        x = out[k]
        assert x["before_diff"]["go_off"] is True and x["before_diff"]["tick_off"] is True      # nothing opens before the whole patch is on the page
        assert x["ticked_but_no_diff_click"] == "[]" and x["after_diff"]["html_has_diff"] is True and x["after_diff"]["tick_off"] is False
        assert x["unticked_go_off"] is True                                                    # unticking closes it again
    assert out["install_fine"]["before_diff"]["has_reason_field"] is False and out["install_fine"]["after_diff"]["go_off"] is False
    assert json.loads(out["install_fine"]["sent"]) == [{"action": "code_apply", "job": "j1", "sha": "a1b2c3d4e5f6"}]
    c = out["install_concern"]
    assert c["before_diff"]["has_reason_field"] is True and c["after_diff"]["go_off"] is True and c["no_reason_click"] == "[]" and c["reason_typed_go_off"] is False
    assert json.loads(c["sent"]) == [{"action": "code_apply", "job": "j1", "sha": "a1b2c3d4e5f6", "reason": "because it is only a nit"}]
    for k in ("install_cut", "install_changed"):                                                # a patch that is cut or not the one on the card never opens the button
        assert out[k]["go_off"] is True and out[k]["tick_off"] is True and out[k]["prepared"] == "[]"
    assert "the cap of this job is spent" in out["refused"] and "<button" not in out["refused"]
    assert "never marked applied" in out["started_warning"] and "2026-11-28T01:02:03Z" in out["started_warning"]
