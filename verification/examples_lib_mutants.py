"""Mutants for SPEC_EXAMPLE_GATE PR 1 (codetask/examples.py: form, comparison, tautology check, runner script, two passes): each applied alone in a worktree; killed = a test FAILED and pytest reported no error.
Usage: <this> <worktree> <python> [name fragments to run only some]. Docker is not needed.
"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
ONLY = sys.argv[3:]
T = ["-rfEs", "tests/test_examples.py", "tests/test_xdist_groups.py"]
E = "codetask/examples.py"


M = [
    ("the number tolerance is gone", E, [("return math.isclose(expected, actual, rel_tol=REL_TOL, abs_tol=0.0)", "return expected == actual")]),
    ("the number tolerance is too loose", E, [("REL_TOL = 1e-9", "REL_TOL = 1e-2")]),
    ("a bool is a number", E, [("    if isinstance(expected, bool) or isinstance(actual, bool):\n        return type(expected) is type(actual) and expected == actual\n", "")]),
    ("objects may have different keys", E, [("return set(expected) == set(actual) and all(", "return all(")]),
    ("lists may differ in length", E, [("return len(expected) == len(actual) and all(same(a, b) for a, b in zip(expected, actual))", "return all(same(a, b) for a, b in zip(expected, actual))")]),
    ("more examples than the limit", E, [("MAX_EXAMPLES, MAX_BYTES = 6, 3000", "MAX_EXAMPLES, MAX_BYTES = 7, 3000")]),
    ("the size limit is gone", E, [("    if size > MAX_BYTES:", "    if False:")]),
    ("unknown keys are allowed", E, [("        if extra:\n            problems.append(f\"{where}: unknown key(s)", "        if False:\n            problems.append(f\"{where}: unknown key(s)")]),
    ("an id may repeat", E, [("        elif eid in seen:", "        elif False:")]),
    ("the id form is not checked", E, [("if not isinstance(eid, str) or not ID.fullmatch(eid):", "if False:")]),
    ("the tier is not checked", E, [("        if ex.get(\"tier\") not in TIERS:", "        if False:")]),
    ("expect and raises together are fine", E, [("        if (\"expect\" in ex) == (\"raises\" in ex):", "        if False:")]),
    ("raises may be any text", E, [("if not isinstance(r, str) or not RAISES.fullmatch(r) or len(r) > RAISES_MAX:", "if False:")]),
    ("a whatif needs no overrides", E, [("            if not isinstance(ov, dict) or not ov:", "            if False:")]),
    ("overrides on any tier", E, [("        elif \"overrides\" in ex:", "        elif False:")]),
    ("an override name may be anything", E, [("if not isinstance(k, str) or not OVERRIDE.fullmatch(k):", "if False:")]),
    ("a NaN is JSON", E, [("json.dumps(value, allow_nan=False)", "json.dumps(value)")]),
    ("a control character in a text is fine", E, [("        if unicodedata.category(c)[0] == \"C\" or unicodedata.category(c) in (\"Zl\", \"Zp\"):\n            return f\"{name} has", "        if False:\n            return f\"{name} has")]),
    ("the says limit is gone", E, [("(\"says\", SAYS_MAX, False)", "(\"says\", 10**6, False)")]),
    ("the tautology check ignores imports", E, [("    if not ours:", "    if False:")]),
    ("the tautology check ignores calls", E, [("    if not any(isinstance(n, ast.Call)", "    if False and not any(isinstance(n, ast.Call)")]),
    ("a module outside the tree counts", E, [("os.path.isdir(os.path.join(tree, m)) or os.path.isfile(os.path.join(tree, m + \".py\"))", "True")]),
    ("clean keeps control characters", E, [("    text = \"\".join(\" \" if unicodedata.category(c)[0] == \"C\" or unicodedata.category(c) in (\"Zl\", \"Zp\") else c\n                   for c in str(text))\n", "    text = str(text)\n")]),
    ("clean does not cut", E, [("    return text if len(text) <= limit else text[:limit - 3] + \"...\"", "    return text")]),
    ("a result line without the frame counts", E, [("        if not ln.startswith(frame):\n            continue\n", "")]),
    ("the last line of an id counts", E, [("            got.setdefault(rec[\"id\"], rec[\"result\"])", "            got[rec[\"id\"]] = rec[\"result\"]")]),
    ("a missing result passes", E, [("got.get(ex[\"id\"], {\"ok\": False, \"error\": \"NoResult\", \"message\": \"the pass printed no result\"})", "got.get(ex[\"id\"], {\"ok\": True, \"value\": ex.get(\"expect\")})")]),
    ("the second pass is not compared", E, [("        if json.dumps(a, sort_keys=True) != json.dumps(b, sort_keys=True):", "        if False:")]),
    ("overrides are applied in the pass without them", E, [("\"overrides\": ex.get(\"overrides\", {}) if with_overrides else {}}", "\"overrides\": ex.get(\"overrides\", {})}")]),
    ("an override of a missing name is ignored", E, [("            if not hasattr(target, attr):\n                raise AttributeError(\"override %s: %s has no %s\" % (name, module, attr))\n", "")]),
    ("the payload stays in argv", E, [("del sys.argv[1:]\n", "")]),
    ("noise is not redirected", E, [("    with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):", "    if True:")]),
    ("the child runs without isolation flags", E, [("[sys.executable, \"-I\", \"-c\", payload[\"child\"], arg]", "[sys.executable, \"-c\", payload[\"child\"], arg]")]),
    ("a timeout is a pass", E, [("result = {\"ok\": False, \"error\": \"Timeout\"", "result = {\"ok\": True, \"value\": None, \"error\": \"Timeout\"")]),
    ("a value that is not JSON is an error", E, [("    if raw.get(\"invalid\"):\n        return INVALID,", "    if False:\n        return INVALID,")]),
    ("raises passes on any exception", E, [("return (PASS if raw.get(\"error\") == example[\"raises\"] else FAIL), shown", "return PASS, shown")]),
    ("a value is a pass when an exception was expected", E, [("            return FAIL, f\"no exception was raised;", "            return PASS, f\"no exception was raised;")]),
    ("an unexpected exception is a fail", E, [("    return ERROR, shown", "    return FAIL, shown")]),
    ("the actual value is not shortened", E, [("    return actual if len(text) <= ACTUAL_MAX else clean(text)", "    return actual")]),
    ("a runner that raises is turned into a result", E, [("    r = runner(argv)\n", "    try:\n        r = runner(argv)\n    except Exception:\n        r = {}\n")]),
]

if __name__ == "__main__":
    killed = ran = 0
    for name, F, edits, *rest in M:
        if ONLY and not any(o in name for o in ONLY):
            continue
        p = WT / F
        orig = p.read_text()
        text = orig
        stale = [a[:70] for a, _ in edits if text.count(a) != 1]
        if stale:
            print(f"STALE   {name}: {stale}", flush=True)
            continue
        for a, b in edits:
            text = text.replace(a, b, 1)
        p.write_text(text)
        ran += 1
        try:
            r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *(rest[0] if rest else T)], cwd=WT, capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired:
            print(f"TIMEOUT {name}", flush=True)
            continue
        finally:
            p.write_text(orig)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        fails = [line for line in r.stdout.splitlines() if line.startswith("FAILED tests/test_")][:1]
        k = bool(fails) and "error" not in last
        killed += k
        print(f"{'KILLED ' if k else 'ERROR  ' if 'error' in last else 'SURVIVED'} {name}: {fails or last}", flush=True)
    print(f"RESULT: {killed}/{ran} killed")
