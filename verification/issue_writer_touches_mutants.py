"""Mutants for SPEC_ISSUE_WRITER amendment 4 (the harness searches the old tests for what the issue touches): each guarantee broken alone; killed = a
test failed. Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
W = "codetask/issue_writer.py"
T = ["tests/test_issue_writer.py"]
M = [
    ("touches not required", W, "    if not isinstance(touches, list) or not 1 <= len(touches) <= TOUCHES_MAX:",
     "    if not isinstance(touches, list) or len(touches) > TOUCHES_MAX:"),
    ("no limit on the number", W, "    if not isinstance(touches, list) or not 1 <= len(touches) <= TOUCHES_MAX:",
     "    if not isinstance(touches, list) or not touches:"),
    ("touches checked on a reply only", W, "    if not only:\n        why, touches, test_hits", "    if True:\n        why, touches, test_hits"),
    ("touch length unchecked", W, '        w = text_problem(t, f"touch {i}", TOUCH_MAX, newlines=False)',
     '        w = text_problem(t, f"touch {i}", 10**6, newlines=True)'),
    ("short touch allowed", W, "        if not w and len(t.strip()) < TOUCH_MIN:", "        if False:"),
    ("touch not stripped", W, "            terms.append(t.strip())", "            terms.append(t)"),
    ("missing touch allowed", W, "    if missing and not incomplete:", "    if False:"),
    ("missing refused when incomplete", W, "    if missing and not incomplete:", "    if missing:"),
    ("code not needed", W, '    if (hits or incomplete) and args.get("clash_check") != code:', "    if False:"),
    ("any code passes", W, '    if (hits or incomplete) and args.get("clash_check") != code:',
     '    if (hits or incomplete) and not args.get("clash_check"):'),
    ("incomplete needs no code", W, '    if (hits or incomplete) and args.get("clash_check") != code:',
     '    if hits and args.get("clash_check") != code:'),
    ("code over files only", W, '"\\n".join(f"{f}:{n}:{t}" for f, n, t in hits)', '"\\n".join(f for f, n, t in hits)'),
    ("code too short", W, ".hexdigest()[:12]", ".hexdigest()[:8]"),
    ("non-test lines listed", W, "                    if test:\n", "                    if True:\n"),
    ("test dirs not known", W, "    return any(p.lower() in TEST_DIRS for p in parts[:-1]) or", "    return"),
    ("test dirs include the file name", W, "any(p.lower() in TEST_DIRS for p in parts[:-1])",
     "any(p.lower() in TEST_DIRS for p in parts)"),
    ("test dirs case-sensitive", W, "any(p.lower() in TEST_DIRS", "any(p in TEST_DIRS"),
    ("no spec or e2e dirs", W, '"__tests__", "spec", "specs", "e2e"}', '"__tests__"}'),
    ("CamelCase tests not known", W, "|.*Tests?\\.[^.]+|", "|"),
    ("_spec not known", W, "|.*_(test|spec)\\.[^.]+|", "|.*_test\\.[^.]+|"),
    ("lstat error crashes", W, "            try:\n                st = os.lstat(os.path.join(dirpath, name))\n            except OSError:\n                incomplete = True\n                continue\n",
     "            st = os.lstat(os.path.join(dirpath, name))\n"),
    ("test name matched as prefix", W, "bool(TEST_NAME.fullmatch(parts[-1]))", "bool(TEST_NAME.match(parts[-1]))"),
    ("conftest not a test", W, "|conftest\\.py", ""),
    (".git searched", W, 'if d != ".git" and not', "if not"),
    # both guards at once: os.walk(followlinks=False) and the islink filter each alone keep symlinked dirs out
    ("symlinked dirs followed", W, ["os.walk(jail.root, followlinks=False)", 'if d != ".git" and not os.path.islink(os.path.join(dirpath, d)))'],
     ["os.walk(jail.root, followlinks=True)", 'if d != ".git")']),
    ("symlinked files read", W, "            if not stat.S_ISREG(st.st_mode):\n                continue                                           # symlink",
     "            if False:\n                continue                                           # symlink"),
    # both bounds at once: read_text refuses a file over max_bytes too (caught: incomplete)
    ("large file read", W, ["            if st.st_size > SEARCH_MAX_FILE or files", "jail.read_text(rel, max_bytes=SEARCH_MAX_FILE)"],
     ["            if files", "jail.read_text(rel, max_bytes=10**9)"]),
    ("incomplete not said", W, "    if incomplete:\n        out.append", "    if False:\n        out.append"),
    ("no cap per file", W, "or per.get(f, 0) >= HITS_PER_FILE", ""),
    ("no cap in all", W, "if shown >= HITS_SHOWN or", "if"),
    ("more not counted", W, "        if more:\n", "        if False:\n"),
    ("code not in the rejection", W, 'f"clash), then submit again with clash_check \\"{code}\\":"]', 'f"clash), then submit again:"]'),
    ("touches not kept", W, '"notes": notes, "touches": touches,', '"notes": notes, "touches": [],'),
    ("hits not counted", W, '        return [hits_report(hits, code, incomplete)], terms, len(hits)\n    return [], terms, len(hits)',
     '        return [hits_report(hits, code, incomplete)], terms, len(hits)\n    return [], terms, 0'),
    ("version kept", W, '"SubmitIssue": "5"}', '"SubmitIssue": "4"}'),
    ("prompt silent", W, '    "- Name in `touches` the existing', '    "- Name the existing'),
    ("three submits", "config.yaml", "max_steps: 20, max_submits: 4}", "max_steps: 20, max_submits: 3}"),
]

if __name__ == "__main__":
    killed = 0
    for name, f, old, new in M:
        p = WT / f
        orig = mutated = p.read_text()
        for o, n in zip(*((old, new) if isinstance(old, list) else ([old], [new]))):
            assert mutated.count(o) == 1, (name, o, mutated.count(o))
            mutated = mutated.replace(o, n, 1)
        p.write_text(mutated)
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
