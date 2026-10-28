"""Mutants for SPEC_RED_TESTS_PER_NODE: each applied alone in a worktree, the named tests run with -x; killed = any fail."""
import subprocess, sys
from pathlib import Path
WT, PY = Path(sys.argv[1]), sys.argv[2]
SB = "tests/test_draft.py::test_the_red_check_records_the_message_and_the_repository_files_of_the_chain"
U = "tests/test_red_per_node.py"
M = [
 ("plugin: __cause__ not followed", "acceptance/validation.py",
  "exc = exc.__cause__ or (None if exc.__suppress_context__ else exc.__context__)",
  "exc = None if exc.__suppress_context__ else exc.__context__", [SB]),
 ("plugin: context followed through from None", "acceptance/validation.py",
  "exc = exc.__cause__ or (None if exc.__suppress_context__ else exc.__context__)",
  "exc = exc.__cause__ or exc.__context__", [SB]),
 ("plugin: chain not followed", "acceptance/validation.py",
  "exc = exc.__cause__ or (None if exc.__suppress_context__ else exc.__context__)", "exc = None", [SB]),
 ("plugin: names from the cut message", "acceptance/validation.py",
  'set(re.findall(r"\\b([A-Z]\\w*(?:Error|Exception))\\b", text(exc)))',
  'set(re.findall(r"\\b([A-Z]\\w*(?:Error|Exception))\\b", message(exc)))', [SB]),
 ("plugin: shallowest 20 kept", "acceptance/validation.py", "return paths[-%(paths)d:]", "return paths[:%(paths)d]", [SB]),
 ("plugin: no dedup", "acceptance/validation.py", "if inside(f.filename) and rel(f.filename) not in paths:",
  "if inside(f.filename):", [SB]),
 ("plugin: message not cut", "acceptance/validation.py", 'return m if len(m) <= %(message)d else m[:%(message)d - 3] + "..."',
  "return m", [SB]),
 ("plugin: no message_names", "acceptance/validation.py", '"message_names": names(e.value),', "", [SB]),
 ("plugin: tracebacks printed", "acceptance/validation.py", '"--tb=no",', "", [U + "::test_the_red_check_prints_no_traceback_or_warning_summary"]),
 ("plugin: short summary printed", "acceptance/validation.py", '"-rN", ', "", [U + "::test_the_red_check_prints_no_traceback_or_warning_summary"]),
 ("gate: a record it cannot read passes", "codetask/drafter.py", "                out.append(UNREAD.format(vid=vid, node=n))\n", "", [U]),
 ("gate: AssertionError counts as another exception", "codetask/drafter.py",
  'names = sorted({x for x in named if isinstance(x, str) and x != "AssertionError"})',
  'names = sorted({x for x in named if isinstance(x, str)})', [U, "tests/test_draft_call_path.py"]),
 ("gate: every file must be repository code", "codetask/drafter.py", "if any(_repo_code(p, protected) for p in paths):",
  "if all(_repo_code(p, protected) for p in paths):", [U]),
 ("gate: test files count as repository code", "codetask/drafter.py",
  "and not _test_path(path, protected))", ")", [U]),
 ("gate: the tail decides again (old rule: no record, no problem)", "codetask/drafter.py",
  "            if not isinstance(r, dict) or not r.get(\"assertion\"):\n                continue\n",
  "            if not isinstance(r, dict) or not r.get(\"assertion\") or not b.get(\"output_tail\"):\n                continue\n", [U]),
 ("review: only the first red test", "codetask/drafter.py", "    for n in nodes:\n        r, name = red.get(n)",
  "    for n in nodes[:1]:\n        r, name = red.get(n)", [U]),
 ("review: first line not cut", "codetask/drafter.py",
  'first = first if len(first) <= RED_LINE else first[:RED_LINE - 3] + "..."', "", [U]),
 ("review: whole message, not its first line", "codetask/drafter.py",
  '.split("\\n", 1)[0].split())', '.split())', [U]),
 ("feedback: no red lines", "codetask/drafter.py",
  '        out += [f"    {line}" for line in red_lines(b, sorted(b.get("red_check") or {}))]\n', "", [U]),
 ("red_by_assertion: setup error not named", "acceptance/draft.py",
  'if isinstance(rec, dict) and rec.get("outcome") == "error":', "if False:",
  ["tests/test_draft.py::test_the_red_check_refuses_what_it_cannot_read_or_what_is_not_the_tests_own_assertion"]),
]
killed = 0
for name, f, old, new, tests in M:
    p = WT / f
    orig = p.read_text()
    assert orig.count(old) == 1, (name, orig.count(old))
    p.write_text(orig.replace(old, new, 1))
    r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *tests], cwd=WT, capture_output=True, text=True)
    p.write_text(orig)
    last = (r.stdout.strip().splitlines() or [""])[-1]
    k = "failed" in last                 # an error or a skip is not a kill
    killed += k
    fails = [l for l in r.stdout.splitlines() if l.startswith("FAILED")][:1]
    print(f"{'KILLED ' if k else 'SURVIVED'} {name}: {fails or r.stdout.splitlines()[-1]}", flush=True)
print(f"RESULT: {killed}/{len(M)} killed")
