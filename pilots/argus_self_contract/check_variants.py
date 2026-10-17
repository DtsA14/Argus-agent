"""Check the pilot tests against variants of acceptance/contract.py: the current code, a reference fix and wrong fixes.
  python check_variants.py <workspace>   (a copy of the pilot snapshot: acceptance/, tools/, fixtures/contracts/, pilot_tests/)"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

WS = Path(sys.argv[1])
SRC = (WS / "acceptance" / "contract.py").read_text(encoding="utf-8")

HOOK_OLD = '''            if not isinstance(mp, list) or not all(isinstance(x, str) and TEST_ID.match(x) for x in mp):
                errors.append(f"{where}: must_pass must be a list of dotted test ids")
'''
HOOK_NEW = HOOK_OLD + '''            elif isinstance(v.get("args"), list) and not validate_command(v.get("executable"), v.get("args")):
                errors += [f"{where}: {e}" for e in unreachable(v["args"], mp)]
'''
REF = '''

def unreachable(args, must_pass):
    """Required tests that `python -m unittest discover` with these options can never run, as discovery does it:
    the module is the test file's path relative to the top-level directory (-t, default: the start directory -s),
    the file is under -s and its name matches -p (default test*.py), and with -k a test runs only if some pattern
    matches its full id (no '*': a substring). Static: a test that exists is not checked here."""
    import fnmatch
    import posixpath
    opts, ks = {}, []
    for opt, val in zip(args[3::2], args[4::2]):
        if opt == "-k":
            ks.append(val)
        else:
            opts[opt] = val
    start = posixpath.normpath(opts.get("-s", "."))
    top = posixpath.normpath(opts.get("-t", start))
    rel = posixpath.relpath(start, top)
    if rel == ".." or rel.startswith("../"):
        return [f"start directory {start!r} is not inside the top-level directory {top!r}"]
    prefix = [] if rel == "." else rel.split("/")
    pattern = opts.get("-p", "test*.py")
    problems, seen = [], set()
    for test in must_pass:
        if test in seen:
            problems.append(f"must_pass lists {test!r} twice")
            continue
        seen.add(test)
        parts = test.split(".")
        module = parts[:-2]
        if len(parts) < 3:
            problems.append(f"must_pass {test!r} is not a unittest id (module.Class.method)")
        elif module[:len(prefix)] != prefix or len(module) <= len(prefix):
            problems.append(f"must_pass {test!r} is not in a module under the start directory {start!r}")
        elif not fnmatch.fnmatch(module[-1] + ".py", pattern):
            problems.append(f"must_pass {test!r}: {module[-1]}.py does not match the pattern {pattern!r}")
        elif ks and not any(fnmatch.fnmatchcase(test, k if "*" in k else f"*{k}*") for k in ks):
            problems.append(f"must_pass {test!r} matches none of the -k patterns {ks}")
    return problems
'''
ANCHOR = "\n\ndef check_scope_against(c, files):"
reference = SRC.replace(HOOK_OLD, HOOK_NEW).replace(ANCHOR, REF + ANCHOR)

VARIANTS = {
    "current": SRC,
    "reference": reference,
    "pattern_only": reference.replace("        elif module[:len(prefix)] != prefix or len(module) <= len(prefix):\n"
                                      "            problems.append(f\"must_pass {test!r} is not in a module under the start "
                                      "directory {start!r}\")\n", ""),
    "ignores_k": reference.replace("        elif ks and not any(", "        elif False and not any("),
    "top_defaults_to_dot": reference.replace('top = posixpath.normpath(opts.get("-t", start))',
                                             'top = posixpath.normpath(opts.get("-t", "."))'),
    "no_subpackages": reference.replace("len(module) <= len(prefix)", "len(module) != len(prefix) + 1"),
    "no_duplicates_check": reference.replace("        if test in seen:\n", "        if False:\n"),
}
for name, code in VARIANTS.items():
    assert name == "current" or code != SRC, name
    assert name in ("current", "reference") or code != reference, name
    with tempfile.TemporaryDirectory() as t:
        ws = Path(t) / "ws"
        shutil.copytree(WS, ws)
        (ws / "acceptance" / "contract.py").write_text(code, encoding="utf-8")
        res = []
        for pat in ("test_must_pass_reachable.py", "test_contract_regression.py"):
            r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "pilot_tests", "-t", ".", "-p", pat],
                               cwd=ws, capture_output=True, text=True)
            res.append(f"{pat.split('_')[1]}: {r.stderr.strip().splitlines()[-1]}")
        print(f"{name:<20}", " | ".join(res))
if len(sys.argv) > 2:
    Path(sys.argv[2]).write_text(reference, encoding="utf-8")
