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
GOLDEN_CARD = {"action": "draft_approve", "agent_cap_usd": 0.5, "agent_max_usd_config": 0.5, "attempt_usd": 0.018, "changed_tests": [], "changed_tests_n": 0,
               "draft_run": "d1-run", "flags": ["budget profile: default"], "item": 1, "job": J1,
               "item_text": "One\n\nA discount larger than the sum gives 0.\n\nNothing else changes: x\n\nTests: y\n\nEnvironment: pyenv",
               "money": "the agent runs inside the job cap the queue already holds; no new money. Tests and the contract are the drafter's (a model's), shown as it wrote them. The command re-checks the draft in the sandbox (`dr.check`) and the repository's HEAD; this card does not",
               "profile": "default", "queue": QID, "repo": "athena", "retry": False, "summary_note": "summary unavailable", "title": "Approve the draft (the agent starts)",
               "validations": [{"id": "v1", "must_pass": ["tests/test_a.py::test_x"]}], "writable": ["src/a.py", "tests/test_a.py"]}


def card_of(out):
    return json.dumps(out["card"], sort_keys=True)


def test_the_draft_approve_card_of_a_queue_item_is_unchanged_by_the_refactor(svc):
    t4.queue(svc, jobs=(J1, None))
    t4.awaiting(svc, J1, TEXT)
    status, out = t4.prep(svc, "draft_approve")
    assert status == 200
    c = {k: v for k, v in out["card"].items() if k not in ("list_sha", "approved_sha", "draft_sha")}
    assert c == GOLDEN_CARD and out["card"]["draft_sha"] == rj.draft_sha_of(t4.draft())
