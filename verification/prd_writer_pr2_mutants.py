"""Mutants for SPEC_PRD_WRITER PR 2 (codetask/prd_writer.py, router/prd_job.py, the prd hooks of router/job.py, scoreboard and chat): each applied alone in a worktree; killed = a test FAILED and pytest reported no error.
Usage: <this> <worktree> <python> [name fragments to run only some]. Docker is not needed.
"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
ONLY = sys.argv[3:]
T = ["-rfEs", "tests/test_prd_writer.py", "tests/test_prd_writer_base.py", "tests/test_issue_writer.py"]
PW, PJ, IW, J, SB, CA = "codetask/prd_writer.py", "router/prd_job.py", "codetask/issue_writer.py", "router/job.py", "scripts/scoreboard.py", "router/chat_actions.py"


def off(cond):
    """The condition's line with `if False:` in its place, keeping the indentation."""
    return (cond, cond[: len(cond) - len(cond.lstrip())] + "if False:")


M = [
    ("the folder check is skipped", PW, [("if not problems and result[\"items\"] and finish is not None:", "if False:")]),
    ("the folder check's blocks are ignored", PJ, [("        if not blocks:\n            return [], None", "        if True:\n            return [], None")]),
    ("known is not passed to the issue gate", PW, [("known=known, strict=True)", "known=frozenset(), strict=True)")]),
    ("strict is not passed to the issue gate", PW, [("known=known, strict=True)", "known=known, strict=False)")]),
    ("an item may excuse its own touch", PW, [("known = frozenset(n for names in created for n in names)", "known = frozenset(n for names in created + [shape[\"creates\"]] for n in names)")]),
    ("the order of the items is ignored", PW, [("known = frozenset(n for names in created for n in names)", "known = frozenset(n for it in items if isinstance(it, dict) for n in (it.get(\"creates\") or []) if isinstance(n, str))")]),
    ("the later-creates hint is dropped", PW, [("and f\"touch {t.strip()!r}\" in p:", "and False:")]),
    ("an unknown top-level key is allowed", IW if False else PW, [("    extra = sorted(set(args) - TOP_KEYS)\n    if extra:", "    extra = sorted(set(args) - TOP_KEYS)\n    if False:")]),
    ("an unknown item key is allowed", PW, [("    extra = sorted(set(item) - ITEM_KEYS)\n    if extra:", "    extra = sorted(set(item) - ITEM_KEYS)\n    if False:")]),
    ("an unknown path key is allowed", PW, [("or set(p) - PATH_KEYS or", "or False or")]),
    ("one more item than the maximum", PW, [("len(items) > max_items:", "len(items) > max_items + 1:")]),
    ("a reply without items may carry a prd", PW, [("        if isinstance(prd_md, str) and prd_md.strip():", "        if False:")]),
    ("the per-issue limit is not enforced", PW, [("        if len(text.strip()) > item_max:", "        if False:")]),
    ("the total limit is not enforced", PW, [("    if total > TOTAL_MAX:", "    if False:")]),
    ("the notes may close their block", PW, [('if "<<<" in notes or ">>>" in notes:', "if False:")]),
    ("max_usd is the queue ceiling, not the issues' caps", PJ, [('max_usd=max_usd_for(cfg, len(result["items"])))', "max_usd=rq.QUEUE_MAX_USD)")]),
    ("max_usd takes the larger of the two", PJ, [("round(min(rq.QUEUE_MAX_USD, n *", "round(max(rq.QUEUE_MAX_USD, n *")]),
    ("the folder's commit is not the frozen one", PJ, [('files = pw.folder_files(w, repo=i["repo_name"], commit=i["commit"],', 'files = pw.folder_files(w, repo=i["repo_name"], commit="0" * 40,')]),
    ("rebase does not freeze the commit again", PJ, [('                i["commit"] = commit\n', "                pass\n")]),
    ("rebase keeps the notes", PJ, [('                job.data["repo_notes"] = None\n', "                pass\n")]),
    ("reply does not preflight the repository", PJ, [("        _repo_state(cfg, i[\"repo_name\"], commit, queues_dir, Path(jobs_dir))\n", "")]),
    ("new does not preflight the repository", PJ, [("    _repo_state(cfg, repo, commit, queues_dir, jobs_dir)\n    job_id =", "    job_id =")]),
    ("a repository-state refusal is sent to the model", PJ, [("                return [], str(e)", "                return [str(e)], None")]),
    ("the repository state is never asked", PJ, [('        if parsed is None or parsed["valid"] is None:', "        if False:")]),
    ("the new folder is written in place", PJ, [("    for p in (part, final):\n        if p.exists():", "    for p in (part,):\n        if p.exists():")]),
    ("an old folder is not marked on a new turn", PJ, [("    mark_superseded(job, keep=sid)\n", "    pass\n")]),
    ("the new folder is marked too", PJ, [('d.name != (f"prd-{keep}" if keep else None)', "True")]),
    ("abandon does not mark the folders", J, [('        if job.data.get("kind") == "prd":         # its folders', '        if False:         # its folders')]),
    ("the recorded sha is not the folder's", PJ, [("    sha = rp.folder_sha(files)\n    _write_folder", '    sha = "0" * 64\n    _write_folder')]),
    ("the previous folder is not carried", PJ, [('"previous": _previous(job),', '"previous": None,')]),
    ("the notes are not kept", PJ, [('        job.data["repo_notes"] = w["notes"]', "        pass")]),
    ("status drops the check line", PJ, [('                f"check it: argus prd check {folder}"]', '                "check it"]')]),
    ("status drops the touches", PJ, [('out.append(f"  issue {n}: touches {touch}; creates {make}; {len(clash)} clash(es)")', 'out.append(f"  issue {n}")')]),
    ("reply takes a job of another kind", PJ, [('        if job.data.get("kind") != "prd":', "        if False:")]),
    ("reply from any state", PJ, [('        if job.data["state"] not in REPLYABLE:', "        if False:")]),
    ("reply without a whole turn left", PJ, [("        if left + 1e-12 < float(s[\"turn\"][\"cap_usd\"]):", "        if False:")]),
    ("the first turn without a whole turn left", PJ, [("        if left + 1e-12 < cap:", "        if False:")]),
    ("the message is not screened", PJ, [("    why = message_problem(cfg, message, first=True)\n    if why:", "    why = None\n    if why:")]),
    ("the human's message is recorded after the turn starts", PJ, [('            job.data["conversation"].append({"from": "human", "at": deps.clock(), "text": message.strip()})\n            job.move(WRITING, deps, stage=ri._next_sid(job), by=os.environ.get("USER"))', '            job.move(WRITING, deps, stage=ri._next_sid(job), by=os.environ.get("USER"))\n            job.data["conversation"].append({"from": "human", "at": deps.clock(), "text": message.strip()})')]),
    ("a reply-only turn writes a folder anyway", PJ, [("    if not w[\"items\"]:", "    if False:")]),
    ("the chat opens a prd job as a code job", CA, [('if got[0].get("kind") in ("issue", "prd"):', 'if got[0].get("kind") in ("issue",):')]),
    ("prd money has no total", SB, [('prd = sum(nano[d["job"]] for _, d in jobs if d.get("kind") == "prd")', "prd = 0")]),
    ("a rejection says there are more submits than there are", PW, [('(f"{left} submit(s) left:" if left > 0', '(f"{left + 1} submit(s) left:" if left > 0')]),
    ("the submit limit is not enforced", PW, [('"exhausted": left <= 0}', '"exhausted": False}')]),
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
