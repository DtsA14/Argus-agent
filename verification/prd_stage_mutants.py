"""Mutants for SPEC_PRD_STAGE B1 (router/prd.py, the prd parts of router/queue.py): each applied alone in a worktree; killed = a test FAILED and pytest reported no error.
Usage: <this> <worktree> <python> [name fragments to run only some]. Docker is not needed.
Not listed: the O_NONBLOCK on the read (without it a FIFO named PRD.md hangs the test, so a mutant there only wastes the timeout); `m.end() != len(path)` in the proxy
check and the PLAIN check in it cover each other (equivalent alone, killed together below)."""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
ONLY = sys.argv[3:]
T = ["-rfEs", "tests/test_prd_stage.py", "tests/test_queue.py"]
P, Q = "router/prd.py", "router/queue.py"


def off(cond):
    """The condition's line with `if False:` in its place, keeping the indentation."""
    return (cond, cond[: len(cond) - len(cond.lstrip())] + "if False:")


M = [
    ("symlinks followed", P, [("os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)", "os.O_RDONLY | os.O_CLOEXEC | os.O_NONBLOCK)")]),
    ("a file that is not regular accepted", P, [off("        if not stat.S_ISREG(os.fstat(fd).st_mode):")]),
    ("no size cap", P, [off("        if len(data) > cap:")]),
    ("other files in the folder accepted", P, [off("    if extra:")]),
    ("the sha framing changed", P, [('separators=(",", ":")', 'separators=(", ", ": ")')]),
    ("a field of a table not checked", P, [('return None if parts[1] in TABLES[parts[0]] or parts[1] in PUBLISHED_EXTRA.get(parts[0], ()) else "is not published by the snapshot"', "return None")]),
    ("an event field not checked", P, [('return None if parts[2] in sd.EVENT_FIELDS[parts[1]] else "is not published by the snapshot"', "return None")]),
    ("the published extras are not known", P, [('PUBLISHED_EXTRA = {"JOB_FIELDS": {"title", "stages", "log"}}', "PUBLISHED_EXTRA = {}")]),
    ("an undeclared path in the text is accepted", P, [("            elif path not in declared:", "            elif False:")]),
    ("a templated path is not warned", P, [off("                if not any(d.startswith(path) for d in declared):")]),
    ("via_proxy not required", P, [off('                if not isinstance(p.get("via_proxy"), bool):')]),
    ("a ledger path may start with /api", P, [('if not path.startswith("/") or path == "/api" or path.startswith("/api/") or path.startswith("/api?"):', 'if not path.startswith("/"):')]),
    ("via_proxy true is not checked against the proxy", P, [('full = "/api" + path if p["via_proxy"] else None', "full = None")]),
    ("via_proxy allowed on a viewer path", P, [off('                if "via_proxy" in p:')]),
    ("no left boundary in the text rule", P, [('LEFT = r"(?<![A-Za-z_.@~\\\\-])"', 'LEFT = r""')]),
    ("trailing punctuation kept", P, [("TAIL = \".,;:)?]'\\\"\"", 'TAIL = ""')]),
    ("only GET, HEAD and POST are seen", P, [("(?:GET|HEAD|POST|PUT|PATCH|DELETE)", "(?:GET|HEAD|POST)")]),
    ("a bare prefix counts as a path", P, [('        if path in ("", "/", "/api/"):', '        if path == "":')]),
    ("a template needs no trailing slash", P, [('template = path.endswith("/") and (', "template = (")]),
    ("approve ignores the sha", P, [off("    if not isinstance(sha, str) or not rj.SHA_SEEN.fullmatch(sha) or not full.startswith(sha):")]),
    ("approve ignores the blocks", P, [("    if blocks or parsed is None:", "    if parsed is None:")]),
    ("approve does not record the prd", P, [('issues=parsed["texts"], cfg=cfg, deps=deps, queues_dir=queues_dir, jobs_dir=jobs_dir,\n                  prd={"sha": full, "dir": str(Path(dir_).resolve())})',
                                             'issues=parsed["texts"], cfg=cfg, deps=deps, queues_dir=queues_dir, jobs_dir=jobs_dir)')]),
    ("max_usd may be a string or a boolean", P, [('type(spec["max_usd"]) not in (int, float) or ', "")]),
    ("the commit may be short", P, [('or not re.fullmatch(r"[0-9a-f]{40}", spec["commit"]) ', "")]),
    ("n may be a boolean or a float", P, [('type(item.get("n")) is not int or ', "")]),
    ("unknown top-level keys accepted", P, [("set(spec) != TOP_KEYS or ", "")]),
    ("unknown keys in a path accepted", P, [("not set(p) <= PATH_KEYS or ", "")]),
    ("a deeply nested issues.json crashes", P, [("except (ValueError, KeyError, TypeError, AttributeError, RecursionError):\n        raise Folder", "except (ValueError, KeyError, TypeError, AttributeError):\n        raise Folder")]),
    ("the queue does not keep the prd", Q, [('"approved": None, "closed": None, **({"prd": prd} if prd else {})}', '"approved": None, "closed": None}')]),
    ("the list sha ignores the prd", Q, [('"issues": [i["issue_sha256"] for i in q["items"]], **({"prd": q["prd"]} if q.get("prd") else {})}', '"issues": [i["issue_sha256"] for i in q["items"]]}')]),
    ("a damaged prd is not refused when loading", Q, [('and (q.get("prd") is None or (', "and (True or (")]),
    ("a damaged prd argument is not refused by new", Q, [('    if prd is not None and not (isinstance(prd, dict)', '    if False and not (isinstance(prd, dict)')]),
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
