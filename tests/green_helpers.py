"""SPEC_VF_O1_CANARY_NONCE: helpers for tests that feed canned pytest output to judge_result (a pytest validation is trusted only with the
harness's record behind the run's nonce)."""
import collections
import hashlib
import json

from acceptance import validation as va

NONCE = "ARGUS-GREEN-" + "0" * 32 + ":"
CANARY_OK = {"test_pass": "ok", "test_fail": "FAIL:AssertionError", "test_error": "FAIL:RuntimeError"}


def sha_of(tests):
    pairs = sorted([n, s] for n, s in tests.items())
    return hashlib.sha256(json.dumps(pairs, ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()


def record(text, rc=0, nonce=NONCE, **over):
    """A record that agrees with `text` (as the harness's script writes it), with fields overridden by `over`."""
    tests = va.parse_pytest(text)["tests"]
    rec = {"rc": rc, "counts": dict(collections.Counter(tests.values())), "sha": sha_of(tests), "canary": dict(CANARY_OK),
           "canary_rc": 1, "canary_error": None}
    rec.update(over)
    return nonce + json.dumps(rec, sort_keys=True)


def with_record(text, rc=0, nonce=NONCE, **over):
    return text + ("" if text.endswith("\n") or not text else "\n") + "\n" + record(text, rc, nonce, **over) + "\n"


def recorded(r, **over):
    """A run result whose stdout is followed by an agreeing record (rc: its exit code)."""
    return {**r, "stdout": with_record(r.get("stdout") or "", r.get("exit_code") or 0, **over)}


def judge(spec, r, **over):
    """judge_result on a run with an agreeing record (set record=False for none)."""
    return va.judge_result(spec, recorded(r, **over), nonce=NONCE)
