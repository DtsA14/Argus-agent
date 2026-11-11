"""Mutants for SPEC_DRAFTER_FORM_FIXES (the harness corrects the draft's form slips before the check): each guarantee
broken alone; killed = a test failed. Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
D = "codetask/drafter.py"
A = "acceptance/draft.py"
V = "acceptance/validation.py"
T = ["tests/test_drafter_form_fixes.py", "tests/test_drafter.py", "tests/test_draft.py", "tests/test_draft_call_path.py",
     "tests/test_vitest_full_regression.py"]
M = [
    ("no normalization", D, "        args, changes = normalize_args(args, base_files)\n", "        changes = []\n"),
    ("ids kept", D, "            if isinstance(v, dict) and isinstance(v.get(\"id\"), str) and not ct.ID.match(v[\"id\"]):",
     "            if False:"),
    ("id not lower-cased", D, '    new = re.sub(r"[^a-z0-9_]", "_", vid.lower())', '    new = re.sub(r"[^a-z0-9_]", "_", vid)'),
    ("no v_ prefix", D, '    new = (new if re.match(r"[a-z]", new) else "v_" + new)[:32]', '    new = new[:32]'),
    ("taken id reused", D, "    return new if ct.ID.match(new) and new not in used else None",
     "    return new if ct.ID.match(new) else None"),
    ("new tests not protected", D, "            if not ct.matches(p, prot):\n                prot.append(p)",
     "            if False:\n                prot.append(p)"),
    ("new test added twice", D, "            if not ct.matches(p, prot):\n", "            if True:\n"),
    ("globs never dropped", D, "        if dropped and base_files and kept and all(", "        if False and all("),
    ("old tests not checked", D, " and all(ct.matches(f, kept) for f in _old_tests(base_files)):", ":"),
    ("refused globs dropped", D, "    return (not ct.check_glob(g) or any(", "    return (any("),
    ("directory globs dropped", D, "\n            or any(f.startswith(g.rstrip(\"/\") + \"/\") for f in files))", ")"),
    ("pytest tests not old", D, 'PYTEST_FILE = re.compile(r"(^|/)(test_[^/]*\\.py|[^/]*_test\\.py|conftest\\.py)$")',
     'PYTEST_FILE = re.compile(r"(?!)")'),
    ("args changed in place", D, "    out, changes = copy.deepcopy(args), []", "    out, changes = args, []"),
    ("reply silent", D, '        said = [NORMALIZED + "; ".join(changes) + "."] if changes else []', "        said = []"),
    ("no event", D, '            log.emit("draft_normalized", submit=n, changes=changes[:20])', "            pass"),
    ("held silent", D, '            return {"content": "\\n".join([ACCEPTED, *said]), "finished": True, "draft": held["draft"],',
     '            return {"content": ACCEPTED, "finished": True, "draft": held["draft"],'),
    ("old name hint gone", A, '                                + ((e.get("named_like") or {}).get(n, "") if got is None else ""))',
     "                                )"),
    ("new name hint gone", A, '                why = ("was not collected" + (e.get("named_like") or {}).get(n, "") if got is None',
     '                why = ("was not collected" if got is None'),
    ("evidence without hints", V, "    if hints:\n        evidence[\"named_like\"] = hints", "    if False:\n        evidence[\"named_like\"] = hints"),
    ("version kept", D, '"SubmitDraft": f"5:{tool_version(scfg, [env])}"', '"SubmitDraft": f"4:{tool_version(scfg, [env])}"'),
]

if __name__ == "__main__":
    killed = 0
    for name, f, old, new in M:
        p = WT / f
        orig = p.read_text()
        assert orig.count(old) == 1, (name, orig.count(old))
        p.write_text(orig.replace(old, new, 1))
        try:
            r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *T], cwd=WT,
                               capture_output=True, text=True, timeout=900)
        finally:
            p.write_text(orig)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        k = r.returncode == 1 and "failed" in last          # a test failed (not a collection or internal error)
        killed += k
        print(f"{'KILLED ' if k else 'SURVIVED'} {name}: {last}", flush=True)
    print(f"RESULT: {killed}/{len(M)} killed")
