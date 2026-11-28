"""SPEC_CHAT_JOB_APPROVE rev 1: `job_approve`, the draft approval of a standalone code job from the chat. Real files, a real server, the spawner is a recorder."""
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_chat_actions as t  # noqa: E402
import test_chat_cards as tc  # noqa: E402
import test_chat_t4b as t4  # noqa: E402
from router import chat_actions as ca  # noqa: E402
from router import job as rj  # noqa: E402

svc = t4.svc
J1, TEXT, QID = t4.J1, t4.TEXT, t4.QID
SNAPSHOT = {}


def card_of(out):
    return json.dumps(out["card"], sort_keys=True)


def test_the_draft_approve_card_of_a_queue_item_is_unchanged_by_the_refactor(svc):
    t4.queue(svc, jobs=(J1, None))
    t4.awaiting(svc, J1, TEXT)
    status, out = t4.prep(svc, "draft_approve")
    assert status == 200
    assert hashlib.sha256(card_of(out).encode()).hexdigest() == "4c29490230d94a1a1c94a12e249c011f16f4499cdd92b9d3a48b9a2eb4fa1ad7"
