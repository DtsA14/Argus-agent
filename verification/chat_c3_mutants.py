"""Mutants for SPEC_CHAT_APP C3 (research mode): each applied alone in a worktree; the backend ones run the research, actions and CLI
tests with -x, the page ones tests/test_chat_ui.py. killed = a test FAILED and pytest reported no error.
Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
BACK = ["-rfEs", "tests/test_chat_research.py", "tests/test_chat_research_cli.py", "tests/test_chat_actions.py"]
UI = ["-rfEs", "tests/test_chat_ui.py"]
A, R, S, C = "router/chat_actions.py", "router/research.py", "scripts/argus.py", "router/chat.py"
J, H, CSS = "router/chat_static/app.js", "router/chat_static/index.html", "router/chat_static/app.css"
ISS = "router/issue.py"
M = [
    # ---- the daily cap
    ("research adds nothing to the cap", A, [('card["action"] in ("issue_new", "issue_start", "research_new")', 'card["action"] in ("issue_new", "issue_start")')], BACK),
    ("research jobs of the directory are not counted", A, [('            if data.get("kind") == "research":\n                try:', '            if False:\n                try:')], BACK),
    ("a research job of the directory is not marked seen", A, [('                            total += max(float(data["max_usd"]), rcap)\n                            seen.add(("new", n))', '                            total += max(float(data["max_usd"]), rcap)')], BACK),
    ("the config cap is not the floor of a counted job", A, [('total += max(float(data["max_usd"]), rcap)', 'total += float(data["max_usd"])')], BACK),
    ("a missing cap counts as zero", A, [('total += max(float(data["max_usd"]), rcap)', 'total += max(float(data.get("max_usd") or 0), 0)')], BACK),
    ("a research job without via counts", A, [('                        if isinstance(entry, dict) and entry.get("what") == "created" and entry.get("via") == "ui" \\\n                                and parse_time(entry["at"]) >= now - DAY:\n                            total += max', '                        if isinstance(entry, dict) and entry.get("what") == "created" \\\n                                and parse_time(entry["at"]) >= now - DAY:\n                            total += max')], BACK),
    ("a research job older than a day counts", A, [('                        if isinstance(entry, dict) and entry.get("what") == "created" and entry.get("via") == "ui" \\\n                                and parse_time(entry["at"]) >= now - DAY:\n                            total += max', '                        if isinstance(entry, dict) and entry.get("what") == "created" and entry.get("via") == "ui":\n                            total += max')], BACK),
    ("the audit net is dropped", A, [("for job_id, at in self.audited_jobs(now, action):", "for job_id, at in []:")], BACK),
    ("the audit net counts old lines", A, [('and parse_time(r["at"]) >= now - DAY:\n                    out.append', 'and True:\n                    out.append')], BACK),
    ("the audit net counts any action", A, [('if r.get("action") == action and r.get("ok") == "confirm"', 'if r.get("ok") == "confirm"')], BACK),
    ("the audit net counts attempts", A, [('r.get("action") == action and r.get("ok") == "confirm"', 'r.get("action") == action')], BACK),
    ("the audit net counts a job already seen", A, [('            if ("new", job_id) not in seen and (os.path.lexists(self.jobs_dir / job_id) or self.spawner.busy(job_id)):\n                total += rcap', '            if True:\n                total += rcap')], BACK),
    ("an unreadable audit is zero", A, [('        except OSError:\n            raise Refusal(503, "cap", "the daily exposure cannot be computed (the audit cannot be read)") from None', '        except OSError:\n            return []')], BACK),
    # ---- the card and its gates
    ("extra params are accepted", A, [('        if set(params) - {"message"}:', '        if False:')], BACK),
    ("the text rules are dropped", A, [('why = text_problem(q, "the question", QUESTION_MAX)', 'why = None')], BACK),
    ("the minimum length is dropped", A, [('        if why is None and len(q.strip()) < QUESTION_MIN:', '        if False:')], BACK),
    ("a key-like or invisible question passes", A, [('        if why is None and scrub(q) != q:', '        if False:')], BACK),
    ("more than the one key is accepted", A, [('        if [k[0] for k in keys] != ["deepseek"]:', '        if False:')], BACK),
    ("no code key needed for research", A, [('        self._need_key(False)\n        try:\n            models =', '        try:\n            models =')], BACK),
    ("research uses the writer's key", A, [('key = self.key_file(a in ("issue_new", "issue_reply"))', 'key = self.key_file(a in ("issue_new", "issue_reply", "research_new"))')], BACK),
    ("a cap below the need passes", A, [('            if not cap + 1e-9 >= need:', '            if False:')], BACK),
    ("the default cap is five dollars", A, [('cap = float(rcfg.get("max_usd", 1.0))\n            need', 'cap = float(rcfg.get("max_usd", 5.0))\n            need')], BACK),
    ("the facts are not in the card", A, [('"job_cap_usd": cap, "facts": facts}', '"job_cap_usd": cap}')], BACK),
    ("the CLI gets a max-usd", A, [('"--question-file", str(message), "--job-id", new_id)', '"--question-file", str(message), "--job-id", new_id, "--max-usd", "5")')], BACK),
    ("the research key is checked for the writer", A, [('        self._need_key(False)\n        try:\n            models =', '        self._need_key(True)\n        try:\n            models =')], BACK),
    # ---- reading
    ("a report is read up to any size", A, [("REPORT_MAX = 1024 * 1024 ", "REPORT_MAX = 1 << 40 ")], BACK),
    ("a report with a second name is read", A, [('sd._read_at(jfd, "REPORT.md", single=True, limit=REPORT_MAX)', 'sd._read_at(jfd, "REPORT.md", single=False, limit=REPORT_MAX)')], BACK),
    ("checked from the state alone", A, [('checked = state == rr.REPORT_READY and e1.get("status") == "CHECKED"', 'checked = state == rr.REPORT_READY')], BACK),
    ("a stalled job is never said so", A, [('"stalled": state in rr.RUNNING and not busy', '"stalled": False')], BACK),
    ("a job with a run is stalled too", A, [('"stalled": state in rr.RUNNING and not busy', '"stalled": state in rr.RUNNING')], BACK),
    ("an unreadable runs directory costs zero", A, [('            rfd = sd._open_dir("runs", jfd)\n        except OSError:\n            return None', '            rfd = sd._open_dir("runs", jfd)\n        except OSError:\n            return 0.0')], BACK),
    ("an unreadable ledger costs zero", A, [('        except (OSError, ValueError, KeyError, TypeError):\n            return None\n        finally:\n            os.close(rfd)', '        except (OSError, ValueError, KeyError, TypeError):\n            return 0.0\n        finally:\n            os.close(rfd)')], BACK),
    ("a symlinked run directory costs zero", A, [('                except OSError:\n                    return None\n                try:\n                    try:', '                except OSError:\n                    continue\n                try:\n                    try:')], BACK),
    ("the banner is empty", A, [('"banner": BANNER,', '"banner": "",')], BACK),
    ("the list is not capped at fifty", A, [("RESEARCH_LIST_MAX, RESEARCH_SCAN_MAX = 50, 200", "RESEARCH_LIST_MAX, RESEARCH_SCAN_MAX = 500, 2000")], BACK),
    ("an issue job is read as research", A, [('        if not isinstance(data, dict) or data.get("kind") != "research" or not isinstance(data.get("inputs"), dict):\n            return None\n        return data, report, spent', '        if not isinstance(data, dict) or not isinstance(data.get("inputs"), dict):\n            return None\n        return data, report, spent')], BACK),
    ("the research id is not checked", A, [('        if not UI_ID.fullmatch(job_id or ""):\n            return None\n        try:\n            sfd = os.open(self.jobs_dir, os.O_RDONLY | os.O_DIRECTORY)\n        except OSError:\n            return None\n        try:\n            jfd = sd._open_dir(job_id, sfd)\n            try:\n                data = json.loads(sd._read_at(jfd, "job.json", limit=JOB_JSON_MAX))\n                report = None', '        try:\n            sfd = os.open(self.jobs_dir, os.O_RDONLY | os.O_DIRECTORY)\n        except OSError:\n            return None\n        try:\n            jfd = sd._open_dir(job_id, sfd)\n            try:\n                data = json.loads(sd._read_at(jfd, "job.json", limit=JOB_JSON_MAX))\n                report = None')], BACK),
    ("starting is not shown", A, [('return {"id": job_id, "state": "starting", "busy": True}', 'return None')], BACK),
    ("a refusal before the job is not shown", A, [('return {"id": job_id, "state": "refused", "busy": False, "line": scrub(out["line"] or "")}', 'return None')], BACK),
    ("a withheld report does not say where to read it", A, [('report = {"withheld": f"{text} Baca di terminal: argus status {job_id}"}', 'report = {"withheld": text}')], BACK),
    ("format characters stay", A, [('unicodedata.category(ch) in ("Cf", "Co", "Cs", "Cn")', 'unicodedata.category(ch) in ()')], BACK),
    ("private-use and unassigned characters stay", A, [('unicodedata.category(ch) in ("Cf", "Co", "Cs", "Cn")', 'unicodedata.category(ch) in ("Cf",)')], BACK),
    ("variation selectors stay", A, [(' or 0xFE00 <= o <= 0xFE0D or 0xE0100 <= o <= 0xE01EF', '')], BACK),
    ("fillers stay", A, [('            or o in HIDDEN_POINTS)', '            )')], BACK),
    # ---- routes and wiring
    ("no research list route", C, [('        if a is not None and path == "/api/research":', '        if False:')], BACK),
    ("no research detail route", C, [('        if a is not None and m:\n            got = a.research_thread(m.group(1))', '        if False:\n            got = a.research_thread(m.group(1))')], BACK),
    ("actions only with an issue writer", C, [('(cfg.get("issue_writer") or cfg.get("research_job"))', 'cfg.get("issue_writer")')], BACK),
    # ---- the CLI
    ("via is not validated", R, [('    if via is not None and via not in rj.VIA:', '    if False:')], BACK),
    ("an id given with via is not checked", R, [('    if via is not None and job_id is not None:', '    if False:')], BACK),
    ("the id shape matches a trailing newline", R, [("UI_JOB_ID.fullmatch(job_id)", "UI_JOB_ID.match(job_id)")], BACK),
    ("the time skew is not checked", R, [("    if abs(named - at) > UI_ID_SKEW_S:", "    if False:")], BACK),
    ("a skew of an hour is allowed", R, [("UI_ID_SKEW_S = 600", "UI_ID_SKEW_S = 3600")], BACK),
    ("via is not recorded", R, [('by=os.environ.get("USER"), **({"via": via} if via else {}))\n        try:\n            with rj.live(deps, rj.stage_config(cfg, cap)', 'by=os.environ.get("USER"))\n        try:\n            with rj.live(deps, rj.stage_config(cfg, cap)')], BACK),
    ("a job that exists is overwritten after the lock", R, [("        if job.data is not None:                       # a second start of the same id", "        if False:                       # a second start of the same id")], BACK),
    ("issue new overwrites after the lock", ISS, [("        if job.data is not None:                       # the same id won the lock", "        if False:                       # the same id won the lock")], BACK),
    ("the CLI drops via", S, [("profile=o.profile, via=o.via, job_id=o.job_id)", "profile=o.profile, via=None, job_id=o.job_id)")], BACK),
    ("the CLI drops the job id", S, [("profile=o.profile, via=o.via, job_id=o.job_id)", "profile=o.profile, via=o.via, job_id=None)")], BACK),
    ("emoji selectors are removed", A, [(" or 0xFE00 <= o <= 0xFE0D or", " or 0xFE00 <= o <= 0xFE0F or")], BACK),
    ("a refused start with no directory and no run blocks the cap", A, [(' and (os.path.lexists(self.jobs_dir / job_id) or self.spawner.busy(job_id)):', ':')], BACK),
    ("a refused start counts when it has a directory only", A, [(' and (os.path.lexists(self.jobs_dir / job_id) or self.spawner.busy(job_id)):', ' and self.spawner.busy(job_id):')], BACK),
    ("a directory that is not research is starting", A, [('            if not UI_ID.fullmatch(job_id or "") or os.path.lexists(self.jobs_dir / job_id):', '            if not UI_ID.fullmatch(job_id or ""):')], BACK),
    ("the cut note is for the marker anywhere", A, [('"cut": bool(CUT_MARK.search(text))', '"cut": "[dipotong harness" in text')], BACK),
    ("a boolean cap is a number", A, [('and not isinstance(d.get("max_usd"), bool) else None', 'else None')], BACK),
    ("the card build is outside the guard", A, [('        except (KeyError, TypeError, ValueError):\n            raise Refusal(409, "config", "the research job\'s configuration is not complete") from None\n        return card', '        except ZeroDivisionError:\n            raise Refusal(409, "config", "x") from None\n        return card')], BACK),
    ("the CLI id without via is the old match", R, [("    if not rj.JOB_ID.fullmatch(job_id):\n        raise rj.Refused(f\"{job_id!r} is not a job id\")\n    job = rj.Job(Path(jobs_dir) / job_id)\n    if job.file.exists():\n        raise rj.Refused(f\"job {job_id} already exists\")\n    with job.lock():\n        if job.data is not None:                       # a second start", "    if not rj.JOB_ID.match(job_id):\n        raise rj.Refused(f\"{job_id!r} is not a job id\")\n    job = rj.Job(Path(jobs_dir) / job_id)\n    if job.file.exists():\n        raise rj.Refused(f\"job {job_id} already exists\")\n    with job.lock():\n        if job.data is not None:                       # a second start")], BACK),
    ("the tally is not shown", J, [(' + " didukung, " + (n.PARTIAL || 0) + " sebagian, " + (n.UNSUPPORTED || 0) + " tidak didukung."', ' + ""')], UI),
    ("the poll redraws a finished job", J, [("else if (researchLive) { showResearch(openResearch); }", "else { showResearch(openResearch); }")], UI),
    ("an older answer draws", J, [('if (mode !== "research" || my !== researchSeq) { return; }', 'if (mode !== "research") { return; }')], UI),
    ("the card says issue for research", J, [('card.action === "research_new" ? "Hasilnya ada di daftar riset." : "Hasilnya ada di daftar issue."', '"Hasilnya ada di daftar issue."')], UI),
    # ---- the page
    ("the banner is not shown", J, [('        c.appendChild(el("p", "note", d.banner));\n', '')], UI),
    ("the label is read from the report text", J, [('d.checked ? "Sudah dicek oleh e1', 'd.report.text.indexOf("Checked") !== -1 ? "Sudah dicek oleh e1')], UI),
    ("the report is written as html", J, [('c.appendChild(el("pre", "report", d.report.text));', 'var rp = el("pre", "report"); rp.innerHTML = d.report.text; c.appendChild(rp);')], UI),
    ("research prepares a profile too", J, [('prepare({ action: "research_new", message: message.value })', 'prepare({ action: "research_new", message: message.value, profile: "free" })')], UI),
    ("a research job gets an action button", J, [('      var link = viewerLink(d.state === "starting"', '      c.appendChild(act("Balas", function () { return { action: "issue_reply", job: id, message: "" }; }));\n      var link = viewerLink(d.state === "starting"')], UI),
    ("the poll redraws while a confirm is on its way", J, [('if (mode === "research" && !(pending && pending.sent))', 'if (mode === "research")')], UI),
    ("a late answer draws in another mode", J, [('      if (mode !== "research" || my !== researchSeq) { return; }', '      if (mode !== "research") { return; }')], UI),
    ("the repo stays in research mode", J, [("repoSel.hidden = r || openIssue !== null;", "repoSel.hidden = openIssue !== null;")], UI),
    ("the research chip is off", H, [('data-mode="research" aria-pressed="false">Riset', 'data-mode="research" disabled aria-pressed="false">Riset')], UI),
    ("the report box does not wrap", CSS, [(".report{white-space:pre-wrap;", ".report{")], UI),
    ("a starting job gets a viewer link", J, [('viewerLink(d.state === "starting" || d.state === "refused" ? null : VIA'.replace("VIA", "VIEWER + d.id)"), 'viewerLink(VIEWER + d.id)')], UI),
    ("the go-live fields are not labelled", J, [('["data_sent", "Data keluar"],', '')], UI),
    ("a stalled job is not said so", J, [('berjalan dari terminal atau terhenti', 'Berhenti')], UI),
    ("the form stays the issue form", J, [('var r = mode === "research";', 'var r = false;')], UI),
]

if __name__ == "__main__":
    killed = 0
    only = sys.argv[3:] or None
    for name, F, edits, T in M:
        if only and not any(o in name for o in only):
            continue
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
    print(f"RESULT: {killed}/{len(M) if not only else killed}")
