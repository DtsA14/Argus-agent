"""The public snapshot allowlist of log entries (router/stage_data.py LOG_WHAT): a job whose log holds a kind it does not know is left out
of the snapshot as a whole. `repro`, `repro_patched` and `apply_started` were written by the router and missing from the list, so every
code job carrying them was excluded (45 of the 66 jobs in a CLI jobs directory, 2026-11-17). Only the kind and the allowlisted fields
(at, what, old, new, stage) are published; the payload of these entries (statuses, heads, shas) is not."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from router import stage_data as sd  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
AT = "2026-11-17T12:00:00Z"
RAW = {"job": "jx", "kind": "code", "state": "APPLIED", "created_at": AT, "max_usd": 1.0, "stages": {},
       "log": [{"at": AT, "what": "created", "by": "x"},
               {"at": AT, "what": "repro", "blocks": 2, "statuses": ["ok", "raised"]},
               {"at": AT, "what": "repro_patched", "sid": "a1", "statuses": ["ok"]},
               {"at": AT, "what": "apply_started", "head_before": "a" * 40, "branch": "main", "read_sha": "b" * 12,
                "examples_failed": ["e2"]},
               {"at": AT, "what": "state", "old": "REVIEW_READY", "new": "APPLIED", "commit": "c" * 40}]}


def test_a_job_with_repro_and_apply_entries_is_projected_and_only_the_kind_is_published():
    out = sd.project_job(json.loads(json.dumps(RAW)), "jx")
    assert [e["what"] for e in out["log"]] == ["created", "repro", "repro_patched", "apply_started", "state"]
    text = json.dumps(out)
    assert out["log"] == [{"at": AT, "what": "created"}, {"at": AT, "what": "repro"}, {"at": AT, "what": "repro_patched"},
                          {"at": AT, "what": "apply_started"}, {"at": AT, "what": "state", "old": "REVIEW_READY", "new": "APPLIED"}]
    for private in ("raised", "head_before", "read_sha", "examples_failed", "e2", "a1", "main", "a" * 40, "b" * 12, "blocks", "sid"):
        assert private not in text, private


def test_an_unknown_kind_still_excludes_the_job():
    raw = json.loads(json.dumps(RAW))
    raw["log"].append({"at": AT, "what": "something_new"})
    try:
        sd.project_job(raw, "jx")
    except sd.Excluded:
        return
    raise AssertionError("an unknown log kind must still exclude the job")


def test_every_kind_the_code_writes_into_a_job_log_is_in_the_allowlist():
    """A new `job.note(deps, "kind", ...)` without its entry in LOG_WHAT would hide every job that carries it: this fails at once."""
    found, scanned = set(), 0
    for sub in ("router", "scripts", "codetask", "research", "harness", "acceptance", "tools"):
        for p in (ROOT / sub).rglob("*.py"):
            scanned += 1
            for arg in re.findall(r"\.note\(\s*[A-Za-z_.]+,\s*([^,)\n]*)", p.read_text(encoding="utf-8")):
                found |= set(re.findall(r'"([a-z_]+)"', arg))              # also the two kinds of `"a" if ok else "b"`
    assert scanned > 50 and {"created", "repro", "apply_started", "not_confirmed"} <= found, sorted(found)
    assert found <= sd.LOG_WHAT, sorted(found - sd.LOG_WHAT)
