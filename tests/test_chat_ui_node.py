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
    assert "Sha draf: </b>aaaaaaaaaaaa" in out["card:draft_approve"] and "tests/test_a.py::test_x" in out["card:draft_approve"] and "(tulisan model)" in out["card:draft_approve"]
    rich, note = out["card:draft_approve:3"], out["card:draft_approve:4"]
    assert "Draf ini mengubah tes yang sudah ada: tests/test_old.py dan 2 lagi" in rich and "<details.more>" in rich
    assert "Teks penulis (model), bukan bukti" in rich and "it may break b" in rich and "no baseline recorded" in rich
    assert "<b>do</b> the thing" in rich and "<b>do</b>" not in rich.replace("&lt;", "").replace("<b>do</b> the thing", "")   # a tag in the text stays text: it is a text node, never markup
    assert "Ringkasan rencana tidak tersedia" in note and "<details" not in note and "mengubah tes" not in note
    chat, term = out["card:prd_approve:5"], out["card:prd_approve:6"]
    assert "permintaan pertama, dimulai lewat chat (tercatat via ui)" in chat and "… (dipotong)" in chat and "2 balasan dari terminal tidak ditampilkan" in chat
    assert "repo rujukan (dibaca penulis, hanya baca)" in chat and "ledger-cli@abcdef123456, athena@123456abcdef" in chat
    assert "<details.more>" in chat and "Ringkasan penulis (tulisan model, bukan bukti)" in chat and "</span>ringkasan <b>penulis</b></p></details>" in chat   # the tag is the text of a text node inside the fold
    assert "permintaan pertama, dari terminal (manusia atau sesi Claude, tidak tercatat)" in term and "dipotong" not in term and "balasan dari terminal" not in term
    assert "Rujukan repo lain tidak terbaca" in term and "<details" not in term
    assert "Drafter limit" in out["card:queue_step"] and "isi issue" in out["card:queue_step"] + out["card:draft_approve"]


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
    assert "The daily cap and the money already booked are not shown" in c and "ledger-cli: PRD kategori" in c and "athena: buffer" not in c   # a job that cost nothing is not listed


def test_the_decisions_page_lists_what_waits_with_fixed_labels_counts_a_draft_job_once_and_says_when_it_may_be_incomplete():
    out = json.loads(node(HERE / "chat_ui_smoke_nav.js", APP))
    assert out["need"] == "false|5|5 jobs · 5 waiting|5 items waiting for you"            # 4 waiting rows + the one open job that is not the draft's own job (jc counts once)
    d = out["decisions"]
    assert d.index("Waiting for you") < d.index("Open jobs") and "Plan ready for your decision" in d and "Draft of issue 2 is ready for you" in d
    assert "Start issue 3 (drafter)" in d and "Queue waits for your go (money)" in d and "a <b>plan</b>" in d and "old job" in d and "draft job" not in d
    n = out["decisionsNotes"]
    assert "The daily cap could not be computed: steps that spend money are not listed." in n and "Not everything was checked: this list may be incomplete." in n
    assert "Nothing is waiting for you." in out["nothing"] and "Waiting for you" not in out["nothing"] and "Open jobs" not in out["nothing"]
    w = out["panelwaiting"]
    assert "draft job" in w and "other" not in w                                          # the panel's Waiting filter follows the waiting rows' jobs too
