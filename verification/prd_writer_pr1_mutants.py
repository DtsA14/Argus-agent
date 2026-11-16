"""Mutants for SPEC_PRD_WRITER PR 1 (the `known`/`strict` of touches_problems, the writer's config section, the kind "prd" in router/job.py): each applied alone in a worktree; killed = a test FAILED and pytest reported no error.
Usage: <this> <worktree> <python> [name fragments to run only some]. Docker is not needed.
"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
ONLY = sys.argv[3:]
T = ["-rfEs", "tests/test_prd_writer_base.py", "tests/test_issue_writer.py"]
W, I, J, PJ = "codetask/issue_writer.py", "router/issue.py", "router/job.py", "router/prd_job.py"


def off(cond):
    """The condition's line with `if False:` in its place, keeping the indentation."""
    return (cond, cond[: len(cond) - len(cond.lstrip())] + "if False:")


M = [
    ("known ignored", W, [("if t not in found and t not in known]", "if t not in found]")]),
    ("known matched as a substring", W, [("if t not in found and t not in known]", "if t not in found and not any(k in t or t in k for k in known)]")]),
    ("known matched before strip", W, [("terms.append(t.strip())", "terms.append(t)")]),
    ("strict ignored", W, [("if missing and (strict or not unread):", "if missing and not unread:")]),
    ("strict by default", W, [("def touches_problems(args, source, known=frozenset(), strict=False):", "def touches_problems(args, source, known=frozenset(), strict=True):")]),
    ("known by default is not empty", W, [("def touches_problems(args, source, known=frozenset(), strict=False):", 'def touches_problems(args, source, known=frozenset({"x"}), strict=False):')]),
    ("settings ignores the section", W, [("    iw = cfg[section]", '    iw = cfg["issue_writer"]')]),
    ("run_writer takes its limits from the issue writer", W, [("    lim = settings(cfg, section)", "    lim = settings(cfg)")]),
    ("run_writer takes its role from the issue writer", W, [('    role = cfg[section]["role"]', '    role = cfg["issue_writer"]["role"]')]),
    ("the job settings ignore the section", I, [('    if section not in cfg:\n        raise rj.Refused(f"the config has no {section} section; nothing was started")\n    return cfg[section]', '    if "issue_writer" not in cfg:\n        raise rj.Refused("the config has no issue_writer section; nothing was started")\n    return cfg["issue_writer"]')]),
    ("the preflight reads the issue writer's section", I, [("    s = _settings(cfg, section)\n    role = s[\"role\"]", "    s = _settings(cfg)\n    role = s[\"role\"]")]),
    ("the preflight checks the limits of the issue writer", I, [("        iw.settings(scfg, section)", "        iw.settings(scfg)")]),
    ("move uses the code table for a prd job", J, [('        elif self.data.get("kind") == "prd":            # SPEC_PRD_WRITER: its own states (router/prd_job.py)\n            from router.prd_job import LEGAL as legal\n', '')]),
    ("move uses the issue table for a prd job", J, [("            from router.prd_job import LEGAL as legal", "            from router.issue import LEGAL as legal")]),
    ("a prd job may be handed off", PJ, [("(AWAITING_HUMAN, WRITING), (WRITE_FAILED, WRITING)}", "(AWAITING_HUMAN, WRITING), (WRITE_FAILED, WRITING), (AWAITING_HUMAN, ri.HANDED_OFF)}")]),
    ("an abandoned prd job may be written again", PJ, [("(AWAITING_HUMAN, WRITING), (WRITE_FAILED, WRITING)}", "(AWAITING_HUMAN, WRITING), (WRITE_FAILED, WRITING), (ABANDONED, WRITING)}")]),
    ("a blocked prd job cannot be abandoned", PJ, [("(s, ABANDONED) for s in (NEW, WRITING, AWAITING_HUMAN, WRITE_FAILED, BLOCKED)", "(s, ABANDONED) for s in (NEW, WRITING, AWAITING_HUMAN, WRITE_FAILED)")]),
    ("resume of a prd job runs the code job's resume", J, [("            return job, prd_job.resume(job, cfg, deps)", "            return job, job")]),
    ("status of a prd job says issue", J, [('(prd)", f"money', '(issue)", f"money')]),
    ("status of a prd job drops the money", J, [("""        head = [f"job {job.id}: {d['state']} (prd)", f"money: cap ${d['max_usd']:.2f}, spent ${spent_nano(job) / 1e9:.4f}",""", """        head = [f"job {job.id}: {d['state']} (prd)",""")]),
]

if __name__ == "__main__":
    killed = ran = 0
    for name, F, edits in M:
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
            r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *T], cwd=WT, capture_output=True, text=True, timeout=300)
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
