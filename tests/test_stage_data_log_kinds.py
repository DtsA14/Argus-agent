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
    for private in ("ok", "raised", "head_before", "read_sha", "examples_failed", "e2", "main", "a" * 40, "b" * 12):
        assert private not in text.replace('"what"', ""), private


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
    found = set()
    for sub in ("router", "scripts", "codetask", "research", "harness", "acceptance", "tools"):
        for p in (ROOT / sub).rglob("*.py"):
            found |= set(re.findall(r'\.note\([A-Za-z_.]+,\s*"([a-z_]+)"', p.read_text(encoding="utf-8")))
    assert found, "the scan found no log kinds: the pattern is wrong"
    assert found <= sd.LOG_WHAT, sorted(found - sd.LOG_WHAT)
