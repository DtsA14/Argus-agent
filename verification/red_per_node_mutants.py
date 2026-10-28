"""Mutants for SPEC_RED_TESTS_PER_NODE (incl. the review of #225): each applied alone in a worktree, the named tests run
with -x; killed = a test failed (an error or a skip is not a kill). Usage: mutants_red.py <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
SB = "tests/test_draft.py::test_the_red_check_records_the_message_and_the_repository_files_of_the_chain"
U = "tests/test_red_per_node.py"
PRINTS = U + "::test_the_red_check_prints_no_traceback_or_warning_summary"
V, D = "acceptance/validation.py", "codetask/drafter.py"
CHAIN = "exc = exc.__cause__ or (None if exc.__suppress_context__ else exc.__context__)"
M = [
    ("plugin: __cause__ not followed", V, CHAIN, "exc = None if exc.__suppress_context__ else exc.__context__", [SB]),
    ("plugin: context followed through from None", V, CHAIN, "exc = exc.__cause__ or exc.__context__", [SB]),
    ("plugin: chain not followed", V, CHAIN, "exc = None", [SB]),
    ("plugin: chain 5 deep", V, '"chain": 20', '"chain": 5', [SB]),
    ("plugin: names from the cut message", V, "    m = text(exc)\n    if isinstance(exc, pytest.fail",
     "    m = message(exc)\n    if isinstance(exc, pytest.fail", [SB]),
    ("plugin: names from the whole text (pytest's explanation too)", V, "\\b\", own(exc)))", "\\b\", text(exc)))", [SB]),
    ("plugin: DID NOT RAISE counted", V, 'and m.startswith("DID NOT RAISE")', "and False", [SB]),
    ("plugin: assert explanation counted", V, 'if line.startswith("assert ")), len(lines))', "if False), len(lines))", [SB]),
    ("plugin: shallowest kept", V, 'return paths[-limits["paths"]:]', 'return paths[:limits["paths"]]', [SB]),
    ("plugin: no dedup", V, "                if r not in kept:\n", "                if True:\n", [SB]),
    ("plugin: message not cut", V, 'return m if len(m) <= limits["message"] else m[:limits["message"] - 3] + "..."',
     "return m", [SB]),
    ("plugin: no message_names", V, '"message_names": names(e.value),', "", [SB]),
    ("plugin: frames without a file count", V, "os.path.realpath(p) if os.path.isfile(p) else None",
     "os.path.realpath(p)", [SB]),
    ("plugin: teardown error replaces a failed call", V,
     'if rep.failed and (call.when == "setup" or out.get(item.nodeid, {}).get("outcome") != "failed"):',
     "if rep.failed:", [SB]),
    ("plugin: tracebacks printed", V, '"--tb=no",', "", [PRINTS]),
    ("plugin: short summary printed", V, '"-rN", ', "", [PRINTS]),
    ("gate: a record it cannot read passes", D, "                out.append(UNREAD.format(vid=vid, node=n))\n", "", [U]),
    ("gate: AssertionError counts as another exception", D,
     'names = sorted({x for x in named if isinstance(x, str) and x != "AssertionError"})',
     "names = sorted({x for x in named if isinstance(x, str)})", [U, "tests/test_draft_call_path.py"]),
    ("gate: every file must be repository code", D, "if any(_repo_code(p, protected) for p in paths):",
     "if all(_repo_code(p, protected) for p in paths):", [U]),
    ("gate: test files count as repository code", D, "and not _test_path(path, protected))", ")", [U]),
    ("gate: the tail decides again", D,
     '            if not isinstance(r, dict) or not r.get("assertion"):\n                continue\n',
     '            if not isinstance(r, dict) or not r.get("assertion") or not b.get("output_tail"):\n'
     "                continue\n", [U]),
    ("review: only the first red test", D, "    for n in nodes:\n        r, name = red.get(n)",
     "    for n in nodes[:1]:\n        r, name = red.get(n)", [U]),
    ("review: first line not cut", D, 'first = first if len(first) <= RED_LINE else first[:RED_LINE - 3] + "..."', "",
     [U]),
    ("review: whole message, not its first line", D, '.split("\\n", 1)[0].split())', ".split())", [U]),
    ("review: red block without a red check", D, '                if b.get("red_check"):\n',
     "                if True:\n", [U]),
    ("feedback: no red lines", D,
     '        out += [f"    {line}" for line in red_lines(b, sorted(b.get("red_check") or {}))]\n', "", [U]),
    ("red_by_assertion: setup error not named", "acceptance/draft.py",
     'if isinstance(rec, dict) and rec.get("outcome") == "error":', "if False:",
     ["tests/test_draft.py::test_the_red_check_refuses_what_it_cannot_read_or_what_is_not_the_tests_own_assertion"]),
]

if __name__ == "__main__":
    killed = 0
    for name, f, old, new, tests in M:
        p = WT / f
        orig = p.read_text()
        assert orig.count(old) == 1, (name, orig.count(old))
        p.write_text(orig.replace(old, new, 1))
        r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *tests], cwd=WT,
                           capture_output=True, text=True)
        p.write_text(orig)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        k = "failed" in last                 # an error or a skip is not a kill
        killed += k
        fails = [line for line in r.stdout.splitlines() if line.startswith("FAILED")][:1]
        print(f"{'KILLED ' if k else 'SURVIVED'} {name}: {fails or last}", flush=True)
    print(f"RESULT: {killed}/{len(M)} killed")
