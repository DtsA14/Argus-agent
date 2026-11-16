"""Mutants for SPEC_PROXY_LEDGER_PATHS (router/stage_viewer.py: the two added proxy paths): each applied alone in a worktree; killed = a test FAILED and pytest reported no error.
Usage: <this> <worktree> <python> [name fragments to run only some]. Docker is not needed.
"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
ONLY = sys.argv[3:]
T = ["-rfEs", "tests/test_stage_viewer.py", "tests/test_prd_stage.py"]
SV, PRD = "router/stage_viewer.py", "router/prd.py"
NEW = ["-rfEs", "tests/test_stage_viewer.py", "-k", "two_ledger_paths or docstring or line_76"]   # only the new tests: -x must not stop on an old one


M = [
    ("no scoreboard/models path", SV, [("scoreboard|scoreboard/models|budget/jobs|jobs|", "scoreboard|budget/jobs|jobs|")]),
    ("no budget/jobs path", SV, [("scoreboard|scoreboard/models|budget/jobs|jobs|", "scoreboard|scoreboard/models|jobs|")]),
    ("scoreboard/models with an optional ending", SV, [("scoreboard/models|budget/jobs", "scoreboard/models/?|budget/jobs")]),
    ("budget/jobs with an optional ending", SV, [("scoreboard/models|budget/jobs", "scoreboard/models|budget/jobs/?")]),
    ("budget alone is a path", SV, [("scoreboard/models|budget/jobs", "scoreboard/models|budget(/jobs)?")]),
    ("scoreboard/models as a prefix", SV, [("scoreboard/models|budget/jobs", "scoreboard/models.*|budget/jobs")]),
    ("the two paths factored together", SV, [("scoreboard|scoreboard/models|budget/jobs|jobs|", "scoreboard|(scoreboard|budget)/(models|jobs)|jobs|")]),
    ("the docstring still says five paths", SV, [("Seven API\npaths", "Five API\npaths")]),
    ("the docstring forgets budget/jobs", SV, [("and /api/budget/jobs (SPEC_PROXY_LEDGER_PATHS)", "(SPEC_PROXY_LEDGER_PATHS)")]),
    ("the docstring forgets scoreboard/models", SV, [("/api/scoreboard/models and /api/budget/jobs", "and /api/budget/jobs")]),
    ("the regex accepts a query", SV, [("+ r\")(/draft)?)$\")", "+ r\")(/draft)?)(\\?.*)?$\")")]),
    ("no-store is dropped (new tests only)", SV, [("        self._send(status, body, api=True)", "        self._send(status, body, api=False)")], NEW),
    ("the regex accepts a query (new tests only)", SV, [("+ r\")(/draft)?)$\")", "+ r\")(/draft)?)(\\?.*)?$\")")], NEW),
    ("scoreboard/models with an s? ending", SV, [("scoreboard/models|budget/jobs", "scoreboard/models(s?)|budget/jobs")]),
    ("budget/jobs with an s? ending", SV, [("scoreboard/models|budget/jobs", "scoreboard/models|budget/jobs(s?)")]),
    ("the two upstream paths are swapped", SV, [("return self._api(f\"/{m.group(1)}\") if m else", "return self._api(f\"/{m.group(1)}\".replace(\"scoreboard/models\", \"@\").replace(\"budget/jobs\", \"scoreboard/models\").replace(\"@\", \"budget/jobs\")) if m else")], NEW),
    ("POST is served like GET", SV, [("    def do_HEAD(self):\n        self.do_GET()", "    def do_HEAD(self):\n        self.do_GET()\n\n    def do_POST(self):\n        self.do_GET()")], NEW),
    ("HEAD is refused", SV, [("    def do_HEAD(self):\n        self.do_GET()", "    def do_HEAD(self):\n        self._refuse()")], NEW),
    ("the regex moves off line 76", SV, [("# S2, A1: the proxy.\nAPI = re.compile(", "# S2, A1: the proxy.\n#\nAPI = re.compile(")], NEW),
    ("prd check ignores via_proxy", PRD, [("full = \"/api\" + path if p[\"via_proxy\"] else None", "full = \"/api\" + path")], ["-rfEs", "tests/test_prd_stage.py"]),
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
