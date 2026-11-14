"""Mutants for SPEC_CHAT_APP C1 (router/chat.py): each applied alone in a worktree, tests/test_chat.py runs with -x;
killed = a test FAILED and pytest reported no error. Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
T = ["-rfEs", "tests/test_chat.py"]
C = "router/chat.py"
M = [
    ("Host not checked on GET", C, [("        if self.headers.get(\"Host\") not in HOSTS:            # every method", "        if False:            # every method")]),
    ("localhost accepted as Host", C, [("HOSTS = (f\"{BIND}:{PORT}\",)", "HOSTS = (f\"{BIND}:{PORT}\", f\"localhost:{PORT}\")")]),
    ("Host not checked before 405", C, [("    def _not_allowed(self):\n        if self.headers.get(\"Host\") not in HOSTS:\n            return self._refuse(421, \"wrong host\")\n", "    def _not_allowed(self):\n")]),
    ("same-site accepted", C, [("if site not in (None, \"same-origin\", \"none\"):", "if site not in (None, \"same-origin\", \"none\", \"same-site\"):")]),
    ("Sec-Fetch-Site not checked", C, [("            if site not in (None, \"same-origin\", \"none\"):", "            if False:")]),
    ("Sec-Fetch-Site skipped on /api/status", C, [("            if site not in (None, \"same-origin\", \"none\"):", "            if site not in (None, \"same-origin\", \"none\") and path != \"/api/status\":")]),
    ("CORP header dropped", C, [("    \"Cross-Origin-Resource-Policy\": \"same-origin\",\n", "")]),
    ("COOP header dropped", C, [("    \"Cross-Origin-Opener-Policy\": \"same-origin\",\n", "")]),
    ("X-Frame-Options dropped", C, [("    \"X-Frame-Options\": \"DENY\",\n", "")]),
    ("trusted types dropped", C, [("; \"\n            \"require-trusted-types-for 'script'; trusted-types 'none'\"", "\"")]),
    ("unsafe-inline in the CSP", C, [("style-src 'self';", "style-src 'self' 'unsafe-inline';")]),
    ("a cookie is set", C, [("    \"Cache-Control\": \"no-store\",", "    \"Cache-Control\": \"no-store\", \"Set-Cookie\": \"a=b\",")]),
    ("POST answered by the base class", C, [("    do_POST = do_PUT = do_DELETE = do_PATCH = do_OPTIONS = do_HEAD = _not_allowed", "    do_PUT = do_DELETE = do_PATCH = do_OPTIONS = do_HEAD = _not_allowed")]),
    # dropped: `close_connection` on a refused POST is equivalent while the server speaks HTTP/1.0 (it closes after every answer);
    # the explicit line keeps it true if the protocol version is ever raised, and test_a_post_with_a_body_does_not_poison... would then fail
    ("non-UI names listed", C, [("if UI_ID.fullmatch(n)), reverse=True)", "if n), reverse=True)")]),
    ("list not capped", C, [("        return names[:LIST_MAX]", "        return names")]),
    ("query string accepted", C, [("        path = self.path\n", "        path = self.path.split(\"?\", 1)[0]\n")]),
    ("static pin not checked", C, [("        if STATIC_SHA256 and hashlib.sha256(data).hexdigest() != STATIC_SHA256.get(name):", "        if False:")]),
    ("detail has no cost", C, [("\"spent_usd\": nano / 1e9}", "\"spent_usd\": 0}")]),
    ("raw job.json instead of the projection", C, [("out.append(card(sd.project_job(raw, name)))", "out.append(card(raw))")]),
]

if __name__ == "__main__":
    killed = 0
    for name, F, edits in M:
        p = WT / F
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
        fails = [line for line in r.stdout.splitlines() if line.startswith("FAILED tests/test_")][:1]
        k = bool(fails) and "error" not in last
        killed += k
        verdict = "KILLED " if k else "SKIPPED" if "skipped" in last and not fails else "ERROR  " if "error" in last else "SURVIVED"
        print(f"{verdict} {name}: {fails or last}", flush=True)
    print(f"RESULT: {killed}/{len(M)} killed")
