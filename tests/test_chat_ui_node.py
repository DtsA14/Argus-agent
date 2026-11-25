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
    assert "Batas drafter" in out["card:queue_step"] and "isi issue" in out["card:queue_step"] + out["card:draft_approve"]


def test_the_money_button_waits_for_the_ack_and_the_reason_and_sends_only_what_the_server_named():
    lines = dict(x.rsplit(": ", 1) for x in node(HERE / "chat_ui_smoke_go.js", APP).strip().splitlines())
    assert lines["start disabled"] == "true" and lines["ack only: disabled"] == "true" and lines["short reason: disabled"] == "true" and lines["ack+reason: enabled"] == "true"
    assert json.loads(lines["prepared"]) == {"action": "queue_go", "job": "j20261117_100000_aaaa", "ack": "1,3", "reason": "alasan yang cukup panjang"}
    assert lines["unticked: disabled and nothing sent"] == "true"
    assert lines["no needs: enabled, sends job only"] == json.dumps({"action": "queue_go", "job": "j20261117_100000_aaaa"}, separators=(",", ":"))
    assert json.loads(lines["ack only"]) == {"action": "queue_go", "job": "j20261117_100000_aaaa", "ack": "2"}
