"""Mutants for SPEC_CHAT_APP C4a (reject and abandon in the chat, the Decide link, the port binding); each applied alone in a worktree,
killed = a test FAILED and pytest reported no error. Usage: <this> <worktree> <python> [name fragment ...]"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
BACK = ["-rfEs", "tests/test_chat_decide.py", "tests/test_chat_research.py", "tests/test_chat_actions.py"]
UI = ["-rfEs", "tests/test_chat_ui.py"]
SINK = ["-rfEs", "tests/test_chat.py", "-k", "whatever_the_spacing"]
A, C, S = "router/chat_actions.py", "router/chat.py", "scripts/argus.py"
J, H = "router/chat_static/app.js", "router/chat_static/index.html"
M = [
    ("the CLI gets no sha", A, [('rp["reason"] or ABANDON_DEFAULT, rp["sha"])', 'rp["reason"] or ABANDON_DEFAULT, "")')], BACK),
    ("the card has no sha12", A, [('"state": state, "sha12": live or None,', '"state": state, "sha12": None,')], BACK),
    ("the card has no state", A, [('"state": state, "sha12": live or None,', '"sha12": live or None,')], BACK),
    ("an error reading the draft is no draft", A, [("        except Exception:\n            raise bad from None", "        except Exception:\n            return \"\"")], BACK),
    ("a missing job in the sha read is no draft", A, [("                if got is None:\n                    raise bad", "                if got is None:\n                    return \"\"")], BACK),
    ("an issue job is decided here", A, [('        if kind == "issue":\n            raise Refusal(409, "kind"', '        if False:\n            raise Refusal(409, "kind"')], BACK),
    ("the state is not checked", A, [("        if verb not in allowed(state):", "        if False:")], BACK),
    ("a busy job gets a card", A, [("        if self.spawner.busy(job_id):\n            raise Refusal(409, \"busy\", \"a run of this service is still working on this job\")", "        if False:\n            raise Refusal(409, \"busy\", \"x\")")], BACK),
    ("the sha of the card is not compared", A, [("        if sha != live:", "        if False:")], BACK),
    ("the sha shape is not checked", A, [('if not isinstance(sha, str) or not (sha == "" or SHA12.fullmatch(sha)):', "if not isinstance(sha, str):")], BACK),
    ("a reject needs no reason", A, [('required=verb == "reject")', "required=False)")], BACK),
    ("an approve action exists", A, [('"job_reject", "job_abandon")   # never', '"job_reject", "job_abandon", "job_approve")   # never')], BACK),
    ("a decision reads the config first", A, [('        if action in ("job_reject", "job_abandon"):\n            return self.build_job(action, params)', '        if False:\n            return self.build_job(action, params)')], BACK),
    ("the exit code is not kept", A, [("            self.last_exit = code if code is not None else \"timeout\"\n", "")], BACK),
    ("the attempt is not audited", C, [('        if not self._audit(a, **rec, attempt="confirm"):', "        if False:")], BACK),
    ("the sha is not audited", C, [('        if card.get("sha12"):\n            rec["sha"] = card["sha12"]', '        if False:\n            rec["sha"] = card["sha12"]')], BACK),
    ("an issue job is listed as a decision", A, [(' and got[0].get("kind") != "issue":\n                    rows.append', ':\n                    rows.append')], BACK),
    ("every state is listed", A, [('if got is not None and got[0].get("state") in REJECTABLE and', "if got is not None and")], BACK),
    ("the list is not cut", A, [("            if scanned >= RESEARCH_SCAN_MAX or len(rows) >= RESEARCH_LIST_MAX:", "            if False:")], BACK),
    ("an issue job is not named by the detail", A, [('        if got[0].get("kind") == "issue":\n            return {"id": job_id, "kind": "issue"', '        if False:\n            return {"id": job_id, "kind": "issue"')], BACK),
    ("an unreadable config breaks the repo list", A, [("        except Refusal:\n            return []                                  # an unreadable config", "        except KeyError:\n            return []                                  # an unreadable config")], BACK),
    ("the Host is the module's", C, [("hosts[0] in self.hosts", "hosts[0] in HOSTS")], BACK),
    ("the Origin is the module's", C, [('self.headers.get("Origin") not in self.origins', 'self.headers.get("Origin") not in ORIGINS')], BACK),
    ("the headers are the module's", C, [("        for k, v in self.hdrs.items():", "        for k, v in HEADERS.items():")], BACK),
    ("8711 does not answer to localhost", C, [('    return (BIND, "localhost") if port == 8711 else (BIND,)', "    return (BIND,)")], BACK),
    ("8712 answers to localhost", C, [('    return (BIND, "localhost") if port == 8711 else (BIND,)', '    return (BIND, "localhost")')], BACK),
    ("any port is possible", C, [("    if port not in PORTS:\n        raise ValueError", "    if False:\n        raise ValueError")], BACK),
    ("any /jobs path is the shell", C, [('        if UI_ID.fullmatch(path[len("/jobs/"):]) and path.startswith("/jobs/"):', '        if path.startswith("/jobs/"):')], BACK),
    ("a trailing slash is the shell", C, [('        if UI_ID.fullmatch(path[len("/jobs/"):]) and path.startswith("/jobs/"):', '        if UI_ID.fullmatch(path[len("/jobs/"):].rstrip("/")) and path.startswith("/jobs/"):')], BACK),
    ("no decisions list", C, [('        if a is not None and path == "/api/decisions":', "        if False:")], BACK),
    ("no decision detail", C, [('        if a is not None and m:\n            got = a.decision(m.group(1))', '        if False:\n            got = a.decision(m.group(1))')], BACK),
    ("sha is not a parameter", C, [('PARAMS = {"repo", "message", "job", "reason", "sha"}', 'PARAMS = {"repo", "message", "job", "reason"}')], BACK),
    ("the chat has actions only with a writer or research config", C, [("    actions = Actions(jobs_dir, load or (lambda: cfg), config_path=config_path)   # always", "    actions = Actions(jobs_dir, load or (lambda: cfg), config_path=config_path) if cfg is not None and (cfg.get(\"issue_writer\") or cfg.get(\"research_job\")) else None   # always")], BACK),
    ("the CLI takes any port", S, [("chs.add_argument(\"--port\", type=int, choices=(8711, 8712), default=8712,", "chs.add_argument(\"--port\", type=int, default=8712,")], BACK),
    ("a non-string kind breaks the title", A, [("            return sd.job_title(data) if isinstance(data.get(\"kind\"), str) else None\n        except Exception:\n            return None", "            return sd.job_title(data)\n        except KeyError:\n            return None")], BACK),
    ("the list opens ledgers", A, [("            got = self._read_data(n, ledgers=False)\n            try:", "            got = self._read_data(n)\n            try:")], BACK),
    ("a bad row breaks the list", A, [("            except Exception:\n                skipped += 1", "            except KeyError:\n                skipped += 1")], BACK),
    ("the draft is read by path", A, [("            return rj.draft_sha_of(json.loads(raw))[:12]", "            return rj.draft_sha_of(json.loads(Path(self.jobs_dir, job_id, 'runs', run, 'draft.json').read_text()))[:12]")], BACK),
    ("any run id is a name", A, [("            if not isinstance(run, str) or not self.RUN_NAME.fullmatch(run):\n                raise bad", "            if not isinstance(run, str):\n                raise bad")], BACK),
    ("a sha is taken for issue actions", C, [('            if action in ACTIONS and not action.startswith("job_"):', "            if False:")], BACK),
    ("the timeout has no exit", A, [('self.last_exit = code if code is not None else "timeout"', "self.last_exit = code")], BACK),
    ("the opened card stays after a decision", J, [("if (openDecision !== null) { showDecision(openDecision); } else { loadDecisions(); }", "loadDecisions();")], UI),
    ("the decision text says issue", J, [('card.action.indexOf("job_") === 0 ? "Keputusan tercatat; keadaan job ada di daftar keputusan." : ', "")], UI),
    ("the decision form submits", J, [('    if (mode === "decide") { return; }\n    if (mode === "research")', '    if (mode === "research")')], UI),
    ("the reason box keeps old text", J, [('else if (m === "decide") { message.value = ""; loadDecisions(); renderDecisions(); }', 'else if (m === "decide") { loadDecisions(); renderDecisions(); }')], UI),
    # ---- the page
    ("a decision always sends an empty sha", J, [('action: "job_reject", job: r.id, sha: r.sha12 || ""', 'action: "job_reject", job: r.id, sha: ""')], UI),
    ("the Decide link prepares", J, [('if (deep) { setMode("decide"); showDecision(deep[1]); }', 'if (deep) { setMode("decide"); showDecision(deep[1]); prepare({ action: "job_abandon", job: deep[1], sha: "", reason: "" }); }')], UI),
    ("an issue from the Decide link is a decision", J, [('      if (d.kind === "issue") { setMode("issue"); showIssue(id); return; }\n', "")], UI),
    ("a late decision answer draws", J, [('      if (mode !== "decide" || openDecision !== id) { return; }\n', "")], UI),
    ("the prepare button shows in decisions", J, [('document.getElementById("prepare").hidden = dc;', 'document.getElementById("prepare").hidden = false;')], UI),
    ("the poll redraws decisions while a confirm is on its way", J, [('if (mode === "decide" && openDecision === null && !(pending && pending.sent))', 'if (mode === "decide" && openDecision === null)')], UI),
    ("a decision card has no viewer link", J, [("    var link = viewerLink(VIEWER + r.id);\n    if (link) { c.appendChild(link); }\n    var acts = el(\"div\", \"actions\");\n    if (!r.busy && r.allowed)", "    var acts = el(\"div\", \"actions\");\n    if (!r.busy && r.allowed)")], UI),
    ("the decisions chip is off", H, [('data-mode="decide" aria-pressed="false">Keputusan', 'data-mode="decide" disabled aria-pressed="false">Keputusan')], UI),
    ("the page says approve", J, [("no draft is accepted here.", "approve here.")], UI),
    ("a busy job still has buttons", J, [("    if (!r.busy && r.allowed) {", "    if (r.allowed) {")], UI),
    ("the page writes to location", J, [("exec(location.pathname);", "exec(location.pathname); location.hash = \"x\";")], SINK),
    ("the page rewrites history", J, [("exec(location.pathname);", "exec(location.pathname); history.replaceState(null, \"\", \"/\");")], SINK),
]

if __name__ == "__main__":
    killed = 0
    only = sys.argv[3:] or None
    ran = 0
    for name, F, edits, T in M:
        if only and not any(o in name for o in only):
            continue
        ran += 1
        p = WT / F
        orig = p.read_text()
        text = orig
        for a, b in edits:
            assert text.count(a) == 1, (name, a[:60], text.count(a))
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
    print(f"RESULT: {killed}/{ran}")
