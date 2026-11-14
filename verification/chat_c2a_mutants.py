"""Mutants for SPEC_CHAT_APP C2a (router/chat.py POST routes, router/chat_actions.py): each applied alone in a worktree, tests/test_chat_actions.py and test_chat.py run with -x;
killed = a test FAILED and pytest reported no error. Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
T = ["-rfEs", "tests/test_chat_actions.py", "tests/test_chat.py"]
C, A = "router/chat.py", "router/chat_actions.py"
M = [
    ("confirm without the minimum delay", A, [("        if now - p[\"issued\"] < MIN_DELAY:", "        if False:")]),
    ("a token is not spent", A, [("        del self.prepared[token]                   # spent: once", "        pass")]),
    ("the card digest is not compared", A, [("        if self.digest(card) != p[\"digest\"]:", "        if False:")]),
    ("a token never expires", A, [("        if p is None or now - p[\"issued\"] > TOKEN_TTL:", "        if p is None:")]),
    ("the daily cap is not checked", A, [("            if used + extra > self.daily_cap() + 1e-9:", "            if False:")]),
    ("pending confirms are not counted", A, [("        total += sum(usd for _, key, usd in self.pending if key not in seen)", "        total += 0")]),
    ("an unreadable job is skipped", A, [("            except (OSError, ValueError):\n                raise unknown from None", "            except (OSError, ValueError):\n                continue")]),
    ("handoffs are not counted", A, [("                if isinstance(h, dict) and h.get(\"via\") == \"ui\" and", "                if False and isinstance(h, dict) and h.get(\"via\") == \"ui\" and")]),
    ("jobs of any origin are counted", A, [("entry.get(\"via\") == \"ui\"", "True")]),
    ("the 24 hour window is not applied to a created job", A, [("                            and parse_time(entry[\"at\"]) >= now - DAY:", "                            and True:")]),
    ("text is not scrubbed", A, [("        return sd.clean_text(text.encode(\"utf-8\"))", "        return text")]),
    ("start in any state", A, [("            if state != ri.AWAITING_HUMAN or v.issue_text is None:", "            if v.issue_text is None:")]),
    ("a busy writer takes another action", A, [("        if busy:\n            raise Refusal(409, \"busy\"", "        if False:\n            raise Refusal(409, \"busy\"")]),
    ("duplicate JSON keys accepted", A, [("        if len(keys) != len(set(keys)):", "        if False:")]),
    ("any repository", A, [("            if repo not in self.repos():", "            if False:")]),
    ("a job id that is not UI shaped is read", A, [("        if not UI_ID.fullmatch(job_id or \"\"):\n            return None\n        try:\n            sfd = os.open(self.jobs_dir, os.O_RDONLY | os.O_DIRECTORY)\n        except OSError:\n            return None\n        try:\n            jfd", "        try:\n            sfd = os.open(self.jobs_dir, os.O_RDONLY | os.O_DIRECTORY)\n        except OSError:\n            return None\n        try:\n            jfd")]),
    ("the start card has no issue text", A, [("\"issue_text\": scrub(v.issue_text),", "\"issue_text\": \"\",")]),
    ("the start uses the writer's key", A, [("        key = self.key_file(a in (\"issue_new\", \"issue_reply\"))", "        key = self.key_file(True)")]),
    ("an abandon is allowed after the handoff", A, [("        if state in (rj.ABANDONED, ri.HANDED_OFF, ri.WRITING):", "        if state in (rj.ABANDONED,):")]),
    ("the message goes in argv", A, [("argv = issue_cli(c, key, \"new\", \"--repo\", rp[\"repo\"], \"--job-id\", new_id, \"--message-file\", str(message))", "argv = issue_cli(c, key, \"new\", \"--repo\", rp[\"repo\"], \"--job-id\", new_id, \"--message\", rp[\"message\"])")]),
    ("the Origin is not checked", C, [("        if self.headers.get(\"Origin\") not in ORIGINS or len(self.headers.get_all(\"Origin\") or []) != 1:", "        if False:")]),
    ("the Content-Type is not checked", C, [("        if (self.headers.get_all(\"Content-Type\") or []) != [\"application/json\"]:", "        if False:")]),
    ("Sec-Fetch-Site is not checked on a POST", C, [("        if len(sites) > 1 or (sites and sites[0] not in (\"same-origin\", \"none\")):\n            raise Refusal(403, \"origin\", \"a cross-site request\")", "        if False:\n            raise Refusal(403, \"origin\", \"a cross-site request\")")]),
    ("the Host is not checked on a POST", C, [("        if not self._host_ok():\n            raise Refusal(421, \"host\", \"wrong host\")", "        if False:\n            raise Refusal(421, \"host\", \"wrong host\")")]),
    ("the body size is not limited", C, [("        if not 0 < length <= BODY_MAX:", "        if False:")]),
    ("a confirm may carry more than the token", C, [("        if set(body) != {\"token\"} or not isinstance(body[\"token\"], str):", "        if not isinstance(body.get(\"token\"), str):")]),
    ("a prepare may carry unknown fields", C, [("        if set(params) - PARAMS or any(", "        if any(")]),
    ("the audit is not required before the action", C, [("        if not self._audit(a, **rec, attempt=\"confirm\"):", "        if False:")]),
    ("other POST routes are handled", C, [("        if a is None or self.path not in POST_ROUTES:", "        if a is None or (self.path not in POST_ROUTES and self.path not in (\"/api/threads\",)):")]),
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
