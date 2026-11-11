"""Mutants for SPEC_STAGING_REAL_DATA amendment 9 (the job's title in the snapshot): each guarantee broken alone;
killed = a test failed. Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
S = "router/stage_data.py"
T = ["tests/test_stage_data.py"]
M = [
    ("no title", S, '        out["title"] = title', "        pass"),
    ("issue job titled", S, 'TITLE_FROM = {"code": "issue", "research": "question"}',
     'TITLE_FROM = {"code": "issue", "research": "question", "issue": "issue"}'),
    ("research from its issue", S, 'TITLE_FROM = {"code": "issue", "research": "question"}',
     'TITLE_FROM = {"code": "issue", "research": "issue"}'),
    ("only \\n breaks a line", S, "for ln in text.splitlines())", 'for ln in text.split("\\n"))'),
    ("first line even if empty", S, "    line = next((c for c in lines if c), \"\")", "    line = next(lines, \"\")"),
    ("control kept", S, '(" ".join(CONTROL.sub("", ln).split())', '(" ".join(ln.split())'),
    ("spaces kept", S, '(" ".join(CONTROL.sub("", ln).split())', '(CONTROL.sub("", ln).strip()'),
    ("no cut", S, "    if len(line) > TITLE_MAX:\n", "    if False:\n"),
    ("cut off by one", S, '        line = line[:TITLE_MAX - 1].rstrip() + "…"', '        line = line[:TITLE_MAX].rstrip() + "…"'),
    ("cut without mark", S, '        line = line[:TITLE_MAX - 1].rstrip() + "…"', '        line = line[:TITLE_MAX - 1].rstrip()'),
    ("space before the mark", S, '        line = line[:TITLE_MAX - 1].rstrip() + "…"', '        line = line[:TITLE_MAX - 1] + "…"'),
    ("key checked only after the cut", S, "    if not line or _keyish(line):", "    if not line:"),
    ("key only as published", S, "    return KEY.search(text.encode()) or KEY.search(json.dumps(text).encode())",
     "    return KEY.search(json.dumps(text).encode())"),
    ("source title read", S, "        text = inputs.get(TITLE_FROM.get(raw.get(\"kind\"))) if isinstance(inputs, dict) else None",
     "        text = inputs.get(TITLE_FROM.get(raw.get(\"kind\"))) if isinstance(inputs, dict) else raw.get(\"title\")"),
    ("published title not read", S, '        text = raw.get("title")', "        text = None"),
    ("validate in source mode", S, "            if project_job(job, job_id, published=True) != job:", "            if project_job(job, job_id) != job:"),
    ("not a string accepted", S, "    if not isinstance(text, str):\n        return None\n    line", "    if text is None:\n        return None\n    line"),
]

if __name__ == "__main__":
    killed = 0
    for name, f, old, new in M:
        p = WT / f
        orig = p.read_text()
        assert orig.count(old) == 1, (name, orig.count(old))
        p.write_text(orig.replace(old, new, 1))
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
