"""Mutants for SPEC_PRD_QUEUE PR 1 (router/queue.py, the queue commands in scripts/argus.py): each applied alone in a worktree; killed = a test FAILED and pytest reported no error.
Usage: <this> <worktree> <python> [name fragments to run only some]. Docker is not needed."""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
ONLY = sys.argv[3:]
T = ["-rfEs", "tests/test_queue.py"]
Q = "router/queue.py"


def off(cond):
    """The condition's line with `if False:` in its place, keeping the indentation."""
    return (cond, cond[: len(cond) - len(cond.lstrip())] + "if False:")


M = [
    ("the list sha not recomputed at step", Q, [('if not q.get("approved") or q["approved"].get("sha") != list_sha(q):', 'if not q.get("approved"):')]),
    ("the jobs directory not in the list sha", Q, [('"environment": q["environment"], "jobs_dir": q["jobs_dir"],', '"environment": q["environment"],')]),
    ("another jobs directory accepted", Q, [off('        if Path(jobs_dir).resolve() != Path(q["jobs_dir"]):')]),
    ("a closed queue steps", Q, [('            raise Refused(f"queue {qid} is closed")\n        if not q.get("approved") or q', '            pass\n        if not q.get("approved") or q')]),
    ("no check that the recorded job is the item's", Q, [off("        if job is not None and not _bound(job, q, item, commit):")]),
    ("the job's issue not compared", Q, [('_sha(i["issue"]) == item["issue_sha256"] and ', "")]),
    ("the job's commit not compared", Q, [(' and i.get("commit") == commit', "")]),
    ("the job's repository not compared", Q, [(' and i.get("repo") == q["repo"])', ")")]),
    ("a stageless BLOCKED job is made again", Q, [off('            if job is not None and job.data["state"] == rj.BLOCKED:')]),
    ("a stageless NEW job is forgotten without abandoning it", Q, [off('            if job is not None and job.data["state"] == rj.NEW:')]),
    ("the forgetting is not saved", Q, [("        if forget:\n            _save(d, q)", "        if False:\n            _save(d, q)")]),
    ("the job id is recorded after the start", Q, [("        _save(d, q)\n        try:\n            rj.start_code", "        try:\n            rj.start_code")]),
    ("as_is not required", Q, [("if not nxt or as_is is not True:", "if not nxt:")]),
    ("the next item starts on the base commit", Q, [("            commit = nxt\n            continue", "            continue")]),
    ("HEAD not checked", Q, [off("    if here != commit:")]),
    ("the money boundary is exclusive", Q, [("    if cap > left:", "    if cap >= left:")]),
    ("the money not checked", Q, [off("    if cap > left:")]),
    ("every job holds only what it spent", Q, [('return rj.spent_nano(job) if job.data["state"] in SPENT_ONLY else to_nano(job.data["max_usd"])', "return rj.spent_nano(job)")]),
    ("APPLIED and REJECTED hold only what they spent", Q, [("SPENT_ONLY = (rj.ABANDONED, rj.BLOCKED, rj.REVIEW_INVALID)", "SPENT_ONLY = (rj.ABANDONED, rj.BLOCKED, rj.REVIEW_INVALID, rj.APPLIED, rj.REJECTED)")]),
    ("REJECTED does not stop the queue", Q, [("rj.BLOCKED, rj.REJECTED, rj.ABANDONED,", "rj.BLOCKED, rj.ABANDONED,")]),
    ("AGENT_FAILED does not stop the queue", Q, [("rj.DRAFT_FAILED, rj.AGENT_FAILED, rj.REVIEW_INVALID,", "rj.DRAFT_FAILED, rj.REVIEW_INVALID,")]),
    ("the environment not passed to the job", Q, [('                          environment=q["environment"])', "                          )")]),
    ("the job cap not passed", Q, [('max_usd=q["job_cap_usd"], jobs_dir=jobs_dir, job_id=job_id,', "jobs_dir=jobs_dir, job_id=job_id,")]),
    ("the issue files not checked at step", Q, [("        for item in q[\"items\"]:\n            _issue_text(d, item)\n        status, detail", "        status, detail")]),
    ("go does not compare the sha", Q, [off("        if not isinstance(sha, str) or not rj.SHA_SEEN.fullmatch(sha) or not want.startswith(sha):")]),
    ("the Argus checkout accepted", Q, [off("    if real == rj.ROOT.resolve():")]),
    ("two queues on one repository", Q, [off('            if other["repo"] == str(real) and derive(other)[0] not in (DONE, CLOSED):')]),
    ("a commit that is not HEAD accepted", Q, [off("    if full != here:")]),
    ("no ceiling on the queue's money", Q, [("if not (0 < money <= QUEUE_MAX_USD):", "if not (0 < money):")]),
    ("less money than one job accepted", Q, [off("    if money < cap:")]),
    ("no ceiling on the number of issues", Q, [("1 <= len(issues) <= QUEUE_MAX_ITEMS", "1 <= len(issues)")]),
    ("the queue id matched, not matched whole", Q, [("QUEUE_ID.fullmatch(qid)", "QUEUE_ID.match(qid)")]),
    ("an unknown queue gets a directory", Q, [off('    if not (d / "queue.json").is_file():')]),
    ("an abandoned stageless job is not made again", Q, [("(rj.NEW, rj.ABANDONED, rj.BLOCKED)))", "(rj.NEW, rj.BLOCKED)))")]),
    ("a job that is missing is not forgotten", Q, [('if item["job"] and (job is None or', 'if item["job"] and (False or')]),
    ("queue step exits 0 when stopped", "scripts/argus.py", [('return 1 if " STOPPED " in text.splitlines()[0] else 0', "return 0")]),
    ("the queue is not damage-checked", Q, [("    if not ok:\n        raise Refused", "    if False:\n        raise Refused")]),
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
            r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *T], cwd=WT, capture_output=True, text=True, timeout=900)
        finally:
            p.write_text(orig)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        fails = [line for line in r.stdout.splitlines() if line.startswith("FAILED tests/test_")][:1]
        k = bool(fails) and "error" not in last
        killed += k
        print(f"{'KILLED ' if k else 'ERROR  ' if 'error' in last else 'SURVIVED'} {name}: {fails or last}", flush=True)
    print(f"RESULT: {killed}/{ran} killed")
