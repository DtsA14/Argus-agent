"""Mutants for SPEC_CHAT_CARDS (T2: router/cards.py and the issue page of router/chat_actions.py; the JS is covered by static tests and a node syntax check, since any change to app.js breaks its pin and every chat test errors): each applied alone in a worktree; killed = a test FAILED and pytest reported no error.
Usage: <this> <worktree> <python> [name fragments to run only some]. Docker is not needed.
"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
ONLY = sys.argv[3:]
T = ["-rfEs", "tests/test_chat_cards.py"]




M = [
    ('the key check is skipped', 'router/cards.py', [('        if self._leaks(calls):\n            return {"withheld": True}', '        if False:\n            return {"withheld": True}')]),
    ('a split key is not seen', 'router/cards.py', [('for text in (joined, re.sub(r"[\\s\\"\'+]", "", joined)):', 'for text in (joined,):')]),
    ('an item without stored examples shows nothing', 'router/cards.py', [('            else:\n                not_run()\n            return card', '            else:\n                pass\n            return card')]),
    ('an item with empty results shows nothing', 'router/cards.py', [('            if calls and not card["note"]:\n                not_run()', '            if False:\n                not_run()')]),
    ('the digest of the examples is not compared', 'router/cards.py', [('if not bound or not same:', 'if not bound:')]),
    ('the binding to the file is not checked', 'router/cards.py', [('if not bound or not same:', 'if not same:')]),
    ('results for only some calls are shown', 'router/cards.py', [(' or sorted(r["id"] for r in clean) != sorted(ids)', ' or False')]),
    ('a result of another tier is shown', 'router/cards.py', [('\n              or any(r["tier"] != tiers[r["id"]] for r in clean)):', '\n              or False):')]),
    ('tier moves are not validated', 'router/cards.py', [(' and m.get("from") in ex.TIERS and m.get("to") in ex.TIERS]', ']')]),
    ('a stored file is decoded loosely', 'router/cards.py', [('text = raw.decode("utf-8")                    # strict', 'text = raw.decode("utf-8", "replace")                    # strict')]),
    ('a missing audit reads as an error', 'router/cards.py', [('except FileNotFoundError:\n            return {"kind": "none", "why": None, "results": None}', 'except FileNotFoundError:\n            return {"kind": "error", "why": None, "results": None}')]),
    ('the last writer message is used', 'router/cards.py', [('m.get("issue_sha256") == want), None)', 'True), None)')]),
    ('the issue file is not bound to the sha', 'router/cards.py', [('_sha(issue_raw) == want)', 'True)')]),
    ('the turn name is not checked', 'router/cards.py', [('if not isinstance(turn, str) or not TURN.fullmatch(turn):', 'if not isinstance(turn, str):')]),
    ('the folder is not bound to its sha', 'router/cards.py', [('bound = rp.folder_sha(files) == t.get("folder_sha") if n_items else False', 'bound = True')]),
    ('a superseded folder is not flagged', 'router/cards.py', [('files["__superseded__"] = b"1" if _exists(dfd, "SUPERSEDED") else b""', 'files["__superseded__"] = b""')]),
    ('a stale folder is not flagged', 'router/cards.py', [('stale=t.get("commit") != i.get("commit"),', 'stale=False,')]),
    ('any queue id is opened', 'router/cards.py', [('if not isinstance(qid, str) or not rq.QUEUE_ID.fullmatch(qid):', 'if not isinstance(qid, str):')]),
    ('the shape of a queue is not checked', 'router/cards.py', [('if not rq.shape_ok(q, qid):', 'if False:')]),
    ('a queue of another jobs directory is opened', 'router/cards.py', [('return os.path.realpath(q["jobs_dir"]) == os.path.realpath(self.jobs_dir)', 'return True')]),
    ('the PRD link is not checked against the jobs directory', 'router/cards.py', [('if UI_ID.fullmatch(path.parent.name) and os.path.realpath(path.parent.parent) == os.path.realpath(self.jobs_dir):', 'if UI_ID.fullmatch(path.parent.name):')]),
    ("a job bound elsewhere counts as the item's", 'router/cards.py', [('and i.get("commit") == commit and i.get("repo") == q["repo"])', 'and True)')]),
    ('a job that cannot be read does not stop the queue', 'router/cards.py', [('            if status == "bad":\n                state, nxt = "STOPPED"', '            if False:\n                state, nxt = "STOPPED"')]),
    ('the money is not checked', 'router/cards.py', [('                if cap > left:\n                    state, nxt = "STOPPED"', '                if False:\n                    state, nxt = "STOPPED"')]),
    ('an applied job need not be the patch', 'router/cards.py', [('if not isinstance(commit_new, str) or as_is is not True:', 'if not isinstance(commit_new, str):')]),
    ('failed jobs do not stop the queue', 'router/cards.py', [('            if st in rq.FAILED:', '            if False:')]),
    ('a blocked job does not stop the queue', 'router/cards.py', [('                if status == "ok" and job.get("state") == "BLOCKED":', '                if False:')]),
    ('results of an unbound job are shown', 'router/cards.py', [('info.get("job") if info and info.get("bound") else None', 'info.get("job") if info else None')]),
    ('an unknown cost counts as 0', 'router/cards.py', [('or isinstance(st["usd"], bool):\n                return None', 'or isinstance(st["usd"], bool):\n                continue')]),
    ('a closed queue is not closed', 'router/cards.py', [('        if q.get("closed"):\n            return "CLOSED"', '        if False:\n            return "CLOSED"')]),
    ('the PRD card can raise', 'router/cards.py', [('def prd(self, job_id):\n        try:\n            return self._prd(job_id)\n        except Exception:', 'def prd(self, job_id):\n        try:\n            return self._prd(job_id)\n        except ZeroDivisionError:')]),
    ('the issue examples can raise', 'router/cards.py', [('            return self._issue_examples(data, issue_raw)\n        except Exception:', '            return self._issue_examples(data, issue_raw)\n        except ZeroDivisionError:')]),
    ('the queue card can raise', 'router/cards.py', [('            return self._queue(qid)\n        except Exception:', '            return self._queue(qid)\n        except ZeroDivisionError:')]),
    ('a FIFO blocks the server', 'router/cards.py', [('OPEN_FILE = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK', 'OPEN_FILE = os.O_RDONLY | os.O_NOFOLLOW')]),
    ('a linked directory below the base is followed', 'router/cards.py', [('OPEN_DIR if dir_fd is not None else OPEN_DIR & ~os.O_NOFOLLOW', 'OPEN_DIR & ~os.O_NOFOLLOW')]),
    ('the scan of jobs is not capped', 'router/cards.py', [('                if len(names) > SCAN_JOBS:', '                if False:')]),
    ('the rows are not capped', 'router/cards.py', [('return {"rows": rows[:ROWS_MAX],', 'return {"rows": rows,')]),
    ('the list is oldest first', 'router/cards.py', [('rows.sort(key=lambda r: (r["at"] or "", r["id"]), reverse=True)', 'rows.sort(key=lambda r: (r["at"] or "", r["id"]), reverse=False)')]),
    ('the queue row names the repository path', 'router/cards.py', [('"title": self.s(q["name"]), "state": state, "repo": self.s(q["name"]),', '"title": self.s(q["name"]), "state": state, "repo": self.s(q["repo"]),')]),
    ('the queue card names the repository path', 'router/cards.py', [('"repo": self.s(q["name"]), "jobs_dir_ok": ok,', '"repo": self.s(q["repo"]), "jobs_dir_ok": ok,')]),
    ('the issue page always keeps the block', 'router/chat_actions.py', [('shown = eg.without_block(v.issue_text) if examples and examples.get("calls") else v.issue_text', 'shown = v.issue_text')]),
    ('the issue page strips the block even without examples', 'router/chat_actions.py', [('if examples and examples.get("calls") else v.issue_text', 'if True else v.issue_text')]),
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
