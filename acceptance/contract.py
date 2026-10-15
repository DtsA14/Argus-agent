"""The acceptance contract of a general task. Written and approved by a human, validated here, then frozen: the
canonical JSON and its sha256 are stored in the run directory, and the agent has no tool that can change them.

Shape (docs/reviews/ACCEPTANCE_GENERAL.md section 5):
  contract: str                 name
  version: int >= 1
  inputs: {workspace, issue}    workspace: repository directory, relative to the project root, under fixtures/repos/
  scope: {writable, protected}  globs relative to the workspace; protected wins, and no input file may match both
  artifacts: [{path, type, schema}]   slice 1: exactly SUMMARY.json, json, claims_v1 or claims_v2
  validation: [{id, executable, args, timeout_s, min_tests, max_skipped, must_pass?}]
  judge: []                     slice 1 has no subjective criteria
  limits: {max_usd, max_iterations}
"""
import hashlib
import json
import math
import re

from .validation import validate_command

ARTIFACT_TYPES = {"json": {"claims_v1", "claims_v2"}}
SUMMARY = "SUMMARY.json"
KEYS = {"contract", "version", "inputs", "scope", "artifacts", "validation", "judge", "limits"}
VALIDATION_KEYS = {"id", "executable", "args", "timeout_s", "min_tests", "max_skipped", "must_pass"}
MAX_TIMEOUT_S = 600
ID = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
TEST_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)+$")


class ContractError(Exception):
    def __init__(self, errors):
        super().__init__("; ".join(errors))
        self.errors = errors


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def check_glob(g):
    """A scope glob: relative, '/'-separated, no '..', no empty or absolute parts."""
    if not isinstance(g, str) or not g or "\x00" in g or "\\" in g or g.startswith("/"):
        return False
    return all(p not in ("", ".", "..") for p in g.split("/"))


def glob_regex(g):
    """'**' matches across directories, '*' and '?' within one path component. Nothing else is special."""
    out, i = [], 0
    while i < len(g):
        if g.startswith("**", i):
            out.append(".*")
            i += 2
        elif g[i] == "*":
            out.append("[^/]*")
            i += 1
        elif g[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(g[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def claims_schema(c):
    return c["artifacts"][0]["schema"]


def matches(path, globs):
    return any(glob_regex(g).match(path) for g in globs)


def validate(c):
    """Every problem with the contract, or [] if it is valid. Never fixes or loosens anything."""
    if not isinstance(c, dict):
        return ["contract must be an object"]
    errors = [f"unknown key {k!r}" for k in sorted(set(c) - KEYS)]
    errors += [f"missing key {k!r}" for k in sorted(KEYS - set(c))]
    if errors:
        return errors

    if not isinstance(c["contract"], str) or not ID.match(c["contract"]):
        errors.append("contract must be a lower-case name")
    if not _int(c["version"]) or c["version"] < 1:
        errors.append("version must be an integer >= 1")

    inp = c["inputs"]
    if not isinstance(inp, dict) or set(inp) != {"workspace", "issue"}:
        errors.append("inputs must have exactly 'workspace' and 'issue'")
    else:
        ws = inp["workspace"]
        if not check_glob(ws) or any(ch in ws for ch in "*?") or not ws.startswith("fixtures/repos/"):
            errors.append("inputs.workspace must be a plain relative path under fixtures/repos/")
        if not isinstance(inp["issue"], str) or not inp["issue"].strip() or len(inp["issue"]) > 2000:
            errors.append("inputs.issue must be a non-empty string of at most 2000 characters")

    sc = c["scope"]
    if not isinstance(sc, dict) or set(sc) != {"writable", "protected"}:
        errors.append("scope must have exactly 'writable' and 'protected'")
    else:
        for k in ("writable", "protected"):
            if not isinstance(sc[k], list) or not sc[k] or not all(check_glob(g) for g in sc[k]):
                errors.append(f"scope.{k} must be a non-empty list of relative globs without '..'")
        if not errors and set(sc["writable"]) & set(sc["protected"]):
            errors.append("a glob is both writable and protected")

    arts = c["artifacts"]
    if not (isinstance(arts, list) and len(arts) == 1 and isinstance(arts[0], dict)
            and set(arts[0]) == {"path", "type", "schema"} and arts[0]["path"] == SUMMARY and arts[0]["type"] == "json"
            and arts[0]["schema"] in ARTIFACT_TYPES["json"]):
        errors.append(f"artifacts must be exactly [{{path: {SUMMARY}, type: json, schema: claims_v1 | claims_v2}}]")

    vals = c["validation"]
    if not isinstance(vals, list) or not vals:
        errors.append("validation must be a non-empty list")
    else:
        seen = set()
        for i, v in enumerate(vals):
            where = f"validation[{i}]"
            if not isinstance(v, dict):
                errors.append(f"{where} must be an object")
                continue
            errors += [f"{where}: unknown key {k!r}" for k in sorted(set(v) - VALIDATION_KEYS)]
            errors += [f"{where}: missing key {k!r}" for k in sorted(VALIDATION_KEYS - {"must_pass"} - set(v))]
            if not ID.match(str(v.get("id", ""))):
                errors.append(f"{where}: id must be a lower-case name")
            elif v["id"] in seen:
                errors.append(f"{where}: duplicate id {v['id']!r}")
            seen.add(v.get("id"))
            errors += [f"{where}: {e}" for e in validate_command(v.get("executable"), v.get("args"))]
            t = v.get("timeout_s")
            if not _num(t) or not 0 < t <= MAX_TIMEOUT_S:
                errors.append(f"{where}: timeout_s must be a number in (0, {MAX_TIMEOUT_S}]")
            if not _int(v.get("min_tests")) or v.get("min_tests", 0) < 1:
                errors.append(f"{where}: min_tests must be an integer >= 1 (0 tests run is never a pass)")
            if not _int(v.get("max_skipped")) or v.get("max_skipped", -1) < 0:
                errors.append(f"{where}: max_skipped must be an integer >= 0")
            mp = v.get("must_pass", [])
            if not isinstance(mp, list) or not all(isinstance(x, str) and TEST_ID.match(x) for x in mp):
                errors.append(f"{where}: must_pass must be a list of dotted test ids")

    if c["judge"] != []:
        errors.append("judge must be [] in slice 1 (no subjective criteria)")

    lim = c["limits"]
    if not isinstance(lim, dict) or set(lim) != {"max_usd", "max_iterations"}:
        errors.append("limits must have exactly 'max_usd' and 'max_iterations'")
    else:
        if not _num(lim["max_usd"]) or not 0 < lim["max_usd"] <= 5:
            errors.append("limits.max_usd must be a finite number in (0, 5]")
        if not _int(lim["max_iterations"]) or not 1 <= lim["max_iterations"] <= 10:
            errors.append("limits.max_iterations must be an integer in [1, 10]")
    return errors


def check_scope_against(c, files):
    """Problems between the scope and the input repository's files: an input file may not be both writable and
    protected, and every protected glob must protect something (a typo would silently protect nothing)."""
    errors = []
    sc = c["scope"]
    for f in sorted(files):
        if matches(f, sc["writable"]) and matches(f, sc["protected"]):
            errors.append(f"input file {f!r} is both writable and protected")
    for g in sc["protected"]:
        if not any(glob_regex(g).match(f) for f in files):
            errors.append(f"protected glob {g!r} matches no input file")
    return errors


def canonical(c):
    return json.dumps(c, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def freeze(c):
    """(canonical JSON, sha256). Raises ContractError if the contract is not valid."""
    errors = validate(c)
    if errors:
        raise ContractError(errors)
    text = canonical(c)
    return text, hashlib.sha256(text.encode("utf-8")).hexdigest()
