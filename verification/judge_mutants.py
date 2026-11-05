"""Mutants for SPEC_JUDGE (argus judge, the advisory judge j1): each applied alone in a worktree, the named tests run
with -x; killed = a test of tests/test_code_judge.py FAILED and pytest reported no error (an import or fixture error,
or a skip, is not a kill). Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
J, C = "router/job.py", "codetask/judge.py"
T = ["-rfEs", "tests/test_code_judge.py"]
M = [
    # G1
    ("state check removed", J, [('job.data["state"] not in JUDGEABLE:', 'False:')]),
    ("package validity not checked", J, [('st.get("status") != "DONE" or not rv.get("valid"):',
                                          'st.get("status") != "DONE":')]),
    # G2
    ("job.json in the prompt", J, [("issue=job_issue(job), draft=draft, package=package,",
                                    "issue=job_issue(job) + job.file.read_text(), draft=draft, package=package,")]),
    ("PR.md read and shown", C, [('PACKAGE = ("changes.patch", "tests.md", "claims.md")',
                                  'PACKAGE = ("changes.patch", "tests.md", "claims.md", "PR.md")'),
                                 ('"Files a finding may name: " + ", ".join(sorted(paths))])',
                                  '"Files a finding may name: " + ", ".join(sorted(paths)), *package.values()])')]),
    # G3
    ("size checked after the request", C, [('        if len(prompt) > lim["max_input_chars"]:',
                                            '        if False:')]),
    # G4
    ("where not checked", C, [("if where is not None and path_of(where) not in paths:", "if False:")]),
    ("a block without findings passes", C, [("    if verdict == BLOCK and not raw:", "    if False:")]),
    ("text cut on every submit", C, [('problem = _bounded(f.get("problem"), f"finding {i} problem", PROBLEM_MAX, last, problems)',
                                      'problem = _bounded(f.get("problem"), f"finding {i} problem", PROBLEM_MAX, True, problems)'),
                                     ('summary = _bounded(args.get("summary"), "summary", SUMMARY_MAX, last, problems)',
                                      'summary = _bounded(args.get("summary"), "summary", SUMMARY_MAX, True, problems)')]),
    # G5
    ("judge moves the job", J, [('    (job.dir / "JUDGE.md").write_text(',
                                 '    job.data["state"] = REJECTED\n    job.save()\n    (job.dir / "JUDGE.md").write_text(')]),
    # G6
    ("a judged package is bought again", J, [('st.get("package") == shas and st.get("status") == jd.JUDGED:', 'False:')]),
    # G7
    ("a cut-off stage is not continued", J, [('resume = st is not None and st.get("package") == shas and st.get("status") is None',
                                              'resume = False')]),
    ("resume does not continue the judge", J, [('        if sids and job.data["stages"][sids[-1]].get("status") is None and state in JUDGEABLE:',
                                                '        if False:')]),
    # G8
    ("cap check removed", J, [("        if cap < need:                            # J6", "        if False:                            # J6")]),
    ("cap ignores what is left", J, [('judge_max_usd", 0.10)), left_usd(job)), 6)', 'judge_max_usd", 0.10)), 1e9), 6)')]),
    # G9
    ("package sha not compared", J, [('stale = package_shas(st_a["review"]["dir"]) != st.get("package")', 'stale = False'),
                                     ('resume = st is not None and st.get("package") == shas and st.get("status") is None',
                                      'resume = st is not None and st.get("status") is None'),
                                     ('if st is not None and st.get("package") == shas and st.get("status") == jd.JUDGED:',
                                      'if st is not None and st.get("status") == jd.JUDGED:')]),
    # G10
    ("pin dropped", "config.yaml", [('  "openrouter:z-ai/glm-5.3":                           {upstream: [baidu/fp8]}\n',
                                     '  "openrouter:z-ai/glm-5.3":                           {upstream: [baidu/fp8, wafer/us]}\n')]),
]

if __name__ == "__main__":
    killed = 0
    for name, f, edits in M:
        p = WT / f
        orig = p.read_text()
        text = orig
        for a, b in edits:
            assert text.count(a) == 1, (name, a[:50], text.count(a))
            text = text.replace(a, b, 1)
        p.write_text(text)
        try:
            r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *T], cwd=WT,
                               capture_output=True, text=True, timeout=1800)
        finally:
            p.write_text(orig)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        fails = [line for line in r.stdout.splitlines() if line.startswith("FAILED tests/test_code_judge.py")][:1]
        k = bool(fails) and "error" not in last
        killed += k
        verdict = "KILLED " if k else "SKIPPED" if "skipped" in last else "ERROR  " if "error" in last else "SURVIVED"
        print(f"{verdict} {name}: {fails or last}", flush=True)
    print(f"RESULT: {killed}/{len(M)} killed")
