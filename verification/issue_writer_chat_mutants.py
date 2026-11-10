"""Mutants for SPEC_ISSUE_WRITER amendment 1 (a reply without an issue, the steps of a running turn, the chat page):
each guarantee broken alone; killed = a test failed. Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
I, W, C = "router/issue.py", "codetask/issue_writer.py", "router/control_issues.py"
T = ["tests/test_issue_writer.py", "tests/test_control_issues.py"]
ONLY_END = '                                         "clashes": [], "questions": w["questions"]})\n'
M = [
    ("clashes without an issue", W, '    if only and args.get("clashes"):', "    if False:"),
    ("an empty issue is an issue", W, "    only = issue is None or (isinstance(issue, str) and not issue.strip())",
     "    only = issue is None"),
    ("never a reply only", W, "    only = issue is None or (isinstance(issue, str) and not issue.strip())", "    only = False"),
    ("target not cut", W, 'log.emit("writer_step", tool=name, target=target[:TARGET_MAX])',
     'log.emit("writer_step", tool=name, target=target)'),
    ("no writer step", W, '            log.emit("writer_step", tool=name, target=target[:TARGET_MAX])\n', ""),
    ("SubmitIssue version kept", W, '"SubmitIssue": "2"}', '"SubmitIssue": "1"}'),
    ("not told to be quick", W, '    "The human chats with you from a phone and waits for every answer: be quick.",\n', ""),
    ("a reply only writes an issue", I, '    if w["issue"] is None:                          # a reply only', "    if False:"),
    ("a reply only drops the issue", I, ONLY_END, ONLY_END + '        job.data["issue_sha256"] = None\n'),
    ("start offered without an issue", I,
     '        if d.get("issue_sha256"):\n            out.append(f"next: argus issue start',
     '        if True:\n            out.append(f"next: argus issue start'),
    ("steps not escaped", C, "{E(DOING.get(t, t))} <span class=\"mono\">{E(x)}</span></li>'",
     "{E(DOING.get(t, t))} <span class=\"mono\">{x}</span></li>'"),
    ("whole log read", C, "            f.seek(max(0, f.tell() - EVENTS_TAIL))", "            f.seek(0)"),
    ("broken line fails the page", C, "        except ValueError:\n            continue", "        except KeyError:\n            continue"),
    ("missing log fails the page", C, '    except OSError:\n        raw = b""', '    except KeyError:\n        raw = b""'),
    ("every step shown", C, "    return steps[-STEPS_SHOWN:], seconds", "    return steps, seconds"),
    ("seconds from the wall clock", C, "seconds = max(0, int((time.time() if now is None else now) - began))",
     "seconds = max(0, int(time.time() - began))"),
    ("start while busy", C, "        can_start = (not busy and state", "        can_start = (state"),
    ("slow reload", C, "REFRESH_S = 3\n", "REFRESH_S = 5\n"),
    ("search text not shown", W, 'for k in ("text", "path")', 'for k in ("path", "text")'),
    ("told to revise every turn", W, "(revise it only when the human's last message asks for \"\n",
     "(revise it as the human's last message asks \"\n"),
    ("status clashes of the last reply", I, "for c in wrote[\"clashes\"]]", "for c in last[\"clashes\"]]"),
    ("page not bound to the conversation", C, '        if job is not None and values["turn"] != str(turn_of(job)):',
     "        if False:"),
    ("no run looks like working", C, "this page reloads by itself.</p>' if busy else", "this page reloads by itself.</p>' if True else"),
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
