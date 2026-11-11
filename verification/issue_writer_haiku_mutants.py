"""Mutants for SPEC_ISSUE_WRITER amendment 5 (touches too broad, Haiku as the writer, the writer's own key file): each
guarantee broken alone; killed = a test failed. Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
W = "codetask/issue_writer.py"
C = "router/control_issues.py"
T = ["tests/test_issue_writer.py", "tests/test_control_issues.py"]
HAIKU = '    model: "openrouter:anthropic/claude-haiku-5.5"\n    max_output_tokens: 16384\n    timeout_s: 180\n'
M = [
    ("broad allowed", W, "    if len(hits) > HITS_SHOWN:", "    if False:"),
    ("broad at forty", W, "    if len(hits) > HITS_SHOWN:", "    if len(hits) >= HITS_SHOWN:"),
    ("broad gets a code", W, "        return [broad_report(hits, per)], terms, len(hits)",
     "        return [hits_report(hits, hits_code(hits), incomplete)], terms, len(hits)"),
    ("lines per touch miscounted", W, "                            per[t][0] += 1",
     "                            per[t][0] += 2"),
    ("files per touch not counted", W, "                            per[t][1].add(rel)", "                            pass"),
    ("counts not shown", W, '    out += [f"  {t!r}: {n} line(s) in {k} file(s)" for t, (n, k) in per.items()]', ""),
    ("model kept", "config.yaml", 'model: "openrouter:anthropic/claude-haiku-5.5"', 'model: "deepseek:deepseek-flash"'),
    ("thinking params kept", "config.yaml", HAIKU, HAIKU + "    params: {extra_body: {thinking: {type: enabled}}}\n"),
    ("input bound changed", "config.yaml", "max_input_tokens: 40000, max_steps: 20, max_submits: 4}",
     "max_input_tokens: 30000, max_steps: 20, max_submits: 4}"),
    ("writer key ignored", C,
     "        k = (self.environ.get(WRITER_KEY_ENV) if writer else None) or self.environ.get(KEY_ENV)",
     "        k = self.environ.get(KEY_ENV)"),
    ("writer key for start", C, '        key = self.key_file(writer=action in ("new", "reply"))',
     "        key = self.key_file(writer=True)"),
    ("writer key for reply only", C, '        key = self.key_file(writer=action in ("new", "reply"))',
     '        key = self.key_file(writer=action == "reply")'),
    ("new page wants the start key", C, "        if self.key_file(writer=True) is None:\n",
     "        if self.key_file() is None:\n"),
    ("reply form wants the start key", C, "            if self.key_file(writer=True) is None and state in ri.REPLYABLE:",
     "            if self.key_file() is None and state in ri.REPLYABLE:"),
    ("start offered with the writer key", C, "and self.key_file() is not None and sha)",
     "and self.key_file(writer=True) is not None and sha)"),
    ("old clash list kept", W, "        final = with_clashes(without_clash_list(issue.strip()), kept)",
     "        final = with_clashes(issue.strip(), kept)"),
    ("old list's blank line kept", W, "            if out and not out[-1].strip():\n                out.pop()\n", ""),
    ("old list's lines kept", W, '            while i < len(lines) and lines[i].startswith("- "):\n                i += 1\n', ""),
    ("a non-test file wants a code", W, "    if (hits or tests_unread) and", "    if (hits or unread) and"),
    ("an unread test wants no code", W, "    if (hits or tests_unread) and", "    if hits and"),
    ("unread tests not named", W, '+ ", ".join(unread[:5])', '+ ""'),
    ("writer variable not named", C, "f'<p class=\"bad\">{E(WRITER_KEY_ENV)} (or {E(KEY_ENV)}) is not set for the service: '\n                              'the writer",
     "f'<p class=\"bad\">{E(KEY_ENV)} is not set for the service: '\n                              'the writer"),
    ("refusal names only the old variable", C, '(f"{WRITER_KEY_ENV} (or {KEY_ENV})" if action in ("new", "reply") else KEY_ENV)', "KEY_ENV"),
]

if __name__ == "__main__":
    killed = 0
    for name, f, old, new in M:
        p = WT / f
        orig = mutated = p.read_text()
        for o, n in zip(*((old, new) if isinstance(old, list) else ([old], [new]))):
            assert mutated.count(o) == 1, (name, o, mutated.count(o))
            mutated = mutated.replace(o, n, 1)
        p.write_text(mutated)
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
