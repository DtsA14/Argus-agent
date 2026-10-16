"""SUMMARY.json: the agent's structured completion claims, each checked against the harness's own evidence. Free text
is allowed in "summary" but is never evidence and is never parsed for claims.

Two schema versions; the contract names the one it uses (artifacts[0].schema), so an old run is never reinterpreted:
  claims_v1  1 to 50 claims
  claims_v2  0 to 50 claims (eval live #1: requiring a claim pushed an agent that could not finish into a false
             claim, then into a change made only to have something to claim). An empty list claims nothing; it does
             not make a failed task pass, since acceptance still checks every criterion from evidence.

  {"claims": [{"claim": "tests_pass",   "evidence": "validation:<id>"},
              {"claim": "issue_fixed",  "evidence": "validation:<id>"},
              {"claim": "file_changed", "path": "<workspace-relative path>"}],
   "summary": "<at most 2000 characters>"}

A claim kind that is not listed, an extra key, or a claim the evidence does not support fails layer D: a summary
does not pass because it sounds convincing.
"""
import json
import os
import stat

from .contract import SUMMARY

MAX_BYTES = 64 * 1024
SCHEMAS = {"claims_v1": 1, "claims_v2": 0}     # schema -> minimum number of claims
KINDS = {"tests_pass": "evidence", "issue_fixed": "evidence", "file_changed": "path"}


def read_summary(workspace, schema="claims_v1"):
    """(document, problems). The artifact must be a regular file, small, UTF-8 JSON with the shape of `schema`."""
    p = os.path.join(workspace, SUMMARY)
    try:
        st = os.lstat(p)
    except FileNotFoundError:
        return None, [f"{SUMMARY} is missing"]
    if not stat.S_ISREG(st.st_mode):
        return None, [f"{SUMMARY} is not a regular file"]
    if st.st_size > MAX_BYTES:
        return None, [f"{SUMMARY} is larger than {MAX_BYTES} bytes"]
    try:
        with open(p, "rb") as f:
            doc = json.loads(f.read().decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        return None, [f"{SUMMARY} is not valid UTF-8 JSON: {e}"]
    return doc, schema_problems(doc, schema)


def schema_problems(doc, schema="claims_v1"):
    if schema not in SCHEMAS:
        return [f"unknown claims schema {schema!r}"]
    least = SCHEMAS[schema]
    if not isinstance(doc, dict) or set(doc) != {"claims", "summary"}:
        return ["SUMMARY must be an object with exactly 'claims' and 'summary'"]
    errors = []
    if not isinstance(doc["summary"], str) or len(doc["summary"]) > 2000:
        errors.append("summary must be a string of at most 2000 characters")
    claims = doc["claims"]
    if not isinstance(claims, list) or not least <= len(claims) <= 50:
        return errors + [f"claims must be a list of {least} to 50 claims"]
    for i, c in enumerate(claims):
        if not isinstance(c, dict) or not isinstance(c.get("claim"), str) or c["claim"] not in KINDS:
            errors.append(f"claims[{i}]: unknown claim kind {c.get('claim') if isinstance(c, dict) else c!r}")
            continue
        field = KINDS[c["claim"]]
        if set(c) != {"claim", field} or not isinstance(c[field], str) or not c[field]:
            errors.append(f"claims[{i}]: a {c['claim']!r} claim has exactly 'claim' and a non-empty '{field}'")
    return errors


def check_claims(doc, validations, changes):
    """One verdict per claim. validations: {"validation:<id>": verdict}; changes: the workspace diff.
    issue_fixed needs a passing validation that has required tests (the contract's must_pass)."""
    changed = set(changes["added"]) | set(changes["modified"])
    out = []
    for i, c in enumerate(doc["claims"]):
        cid = f"claim[{i}]:{c['claim']}"
        if c["claim"] == "file_changed":
            ok = c["path"] in changed and c["path"] != SUMMARY
            why = "" if ok else f"{c['path']!r} was not changed in the workspace"
        else:
            v = validations.get(c["evidence"])
            if v is None:
                ok, why = False, f"evidence {c['evidence']!r} is not a validation in the contract"
            elif v["status"] != "pass":
                ok, why = False, f"evidence {c['evidence']!r} did not pass ({v['status']}: {v['reason']})"
            elif c["claim"] == "issue_fixed" and not v["evidence"].get("must_pass"):
                ok, why = False, f"evidence {c['evidence']!r} names no required test, so it cannot show a fix"
            else:
                ok, why = True, ""
        out.append({"id": cid, "layer": "D", "status": "pass" if ok else "fail", "reason": why,
                    "evidence": {"claim": c}})
    return out
