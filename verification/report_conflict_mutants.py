"""Mutants for SPEC_REPORT_CONFLICT v1-v3 (acceptance/conflict.py, codetask/tools.py, agent.py, run.py, router/job.py, ...): each applied
alone in a worktree, tests/test_report_conflict.py run with -x; killed = a test failed (an error or a skip is not a kill).
Usage: report_conflict_mutants.py <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
C, T, A, R, J = "acceptance/conflict.py", "codetask/tools.py", "codetask/agent.py", "codetask/run.py", "router/job.py"
TT = "tests/test_report_conflict.py"
M = [
    # the file list
    ("files: no maximum", C, "MAX_FILES = 5", "MAX_FILES = 50"),
    ("files: .. allowed", C, '                or ".." in f.split("/")):', "                ):"),
    ("files: absolute allowed", C, 'or f.startswith("/")', "or False"),
    ("files: repeats allowed", C, "if len(set(files)) != len(files):", "if False:"),
    # the checks
    ("check 1: criteria ignored", C, 'if c["layer"] != "C" and c["status"] != "pass":', "if False:"),
    ("check 2: no validation is fine", C, "if not validations:", "if False:"),
    ("check 2: any runner", C, 'if ev.get("runner") not in ("pytest", "vitest"):', "if False:"),
    ("check 2: timeout ignored", C, 'if (ev.get("timed_out") or ev.get("killed")', 'if (ev.get("killed")'),
    ("check 2: output limit ignored", C, 'or ev.get("output_limit_exceeded") or', "or"),
    ("check 2: inconsistent ignored", C, 'or ev.get("consistent") is False', "or False"),
    ("check 2: no tests run ignored", C, 'or ev.get("tests_run") is None):', "or False):"),
    ("check 2: truncated list accepted", C, 'if (ev.get("failures") or 0) + (ev.get("errors") or 0) != len(listed):', "if False:"),
    ("check 5: a required test that is not ok", C, 'if s != "ok" and t not in listed:', "if False:"),
    ("check 3: nothing red is fine", C, "if not red_nodes:", "if False:"),
    ("check 3: a stray red test", C, "    if stray:", "    if False:"),
    ("check 3: a quiet named file", C, "    if quiet:", "    if False:"),
    ("check 6: no change is fine", C, 'if not [p for p in d["added"] + d["removed"] + d["modified"] if p != SUMMARY]:', "if False:"),
    ("check 6: SUMMARY.json counts as a change", C, 'd["modified"] if p != SUMMARY]:', 'd["modified"]]:'),
    ("check 4: the drafts tests", C, "    if path in draft_files:", "    if False:"),
    ("check 4: not an input file", C, "    if path not in before:", "    if False:"),
    ("check 4: changed by the agent", C, "    if after.get(path) != before[path]:", "    if False:"),
    ("check 4: not protected", C, "    if not matches(path, protected):", "    if False:"),
    ("check 4: no file in the failure", C, "    if path is None:", "    if False:"),
    ("check 4: the repository's list ignored", C, 'protected = list(contract["scope"]["protected"]) + list(repo_protected)',
     'protected = list(contract["scope"]["protected"])'),
    ("check 4: the red nodes' files not checked", C, "        why = _untouched_old(f, before, after, protected, draft_files)", "        why = None"),
    ("check 8: the failure's path not checked", C, 'why = _untouched_old(a.get("path"), before, after, protected, draft_files)', "why = None"),
    ("check 7: the baseline not checked", C, '        if (base.get(n) or {}).get("outcome") != "passed":', "        if False:"),
    ("check 7: an unreadable baseline", C, "        if base is None:", "        if False:"),
    ("check 8: a node that does not fail", C, '            if a.get("outcome") != "failed":', "            if False:"),
    ("check 8: a flaky node", C, '            if (a.get("outcome"), a.get("type"), a.get("path")) != (b.get("outcome"), b.get("type"), b.get("path")):',
     "            if False:"),
    ("check 8: one run instead of two", C, "        for _ in range(2):", "        for _ in range(1):"),
    ("check 8: an unreadable run", C, '            if got is None:\n                no("red"', '            if False:\n                no("red"'),
    # sandbox trouble
    ("C4: a missing sandbox in the baseline is a miss", C, "        if unavailable:\n            return _blocked(out, why)\n        if base is None:",
     "        if False:\n            return _blocked(out, why)\n        if base is None:"),
    ("C4: a missing sandbox in the runs is a miss", C, "            if unavailable:\n                return _blocked(out, why)\n            if got is None:",
     "            if False:\n                return _blocked(out, why)\n            if got is None:"),
    ("C4: blocked reads as unconfirmed", C, 'out["state"] = "blocked"', 'out["state"] = "unconfirmed"'),
    ("bug in the check confirms or escapes", C, "    except Exception as e:                      # the harness's own bug",
     "    except ZeroDivisionError as e:              # the harness's own bug"),
    # per validation
    ("groups: always pytest", C, '"runner": "vitest" if kind(spec) == "vitest" else "pytest"}))', '"runner": "pytest"}))'),
    ("groups: a fixed timeout", C, '"timeout_s": spec["timeout_s"],', '"timeout_s": 60,'),
    ("groups: no environment", C, '"environment": spec.get("environment"),', '"environment": None,'),
    ("groups: an unknown validation", C, "        if spec is None:", "        if False:"),
    # the tool
    ("tool: a second report accepted", T, "        if self.conflict is not None:", "        if False:"),
    ("tool: a malformed report accepted", T, "        if bad:\n            return {\"content\": f\"Rejected, nothing was written:\\n- {bad}\"",
     "        if False:\n            return {\"content\": f\"Rejected, nothing was written:\\n- {bad}\""),
    ("tool: SUMMARY.json not written", T, "self.jail.write_text(SUMMARY, json.dumps(doc,", "(lambda *a, **k: None)(SUMMARY, json.dumps(doc,"),
    ("tool: does not end the attempt", T, '"finished": True, "conflict": {"files": list(files)}}', '"finished": False, "conflict": {"files": list(files)}}'),
    ("tool: no files in the result", T, '"finished": True, "conflict": {"files": list(files)}}', '"finished": True}'),
    ("tool: not gated", T, '"ReportConflict": "report_conflict"}', '"ReportConflict": "read_file"}'),
    ("tool: the refusal says nothing", T, 'why = "; ".join(str(x)[:160] for x in items[:3]) or "no reason recorded"', 'why = "no reason recorded"'),
    # the loop and prompts
    ("loop: the result's conflict is lost", A, 'conflict = conflict or record.get("conflict")', "conflict = None"),
    ("loop: ends as finish", A, 'return end("conflict_reported" if conflict else "finished", step, conflict)', 'return end("finished", step, conflict)'),
    ("loop: a report beside another call runs", A, 'if ("Finish" in names or "ReportConflict" in names) and len(calls) != 1:',
     'if "Finish" in names and len(calls) != 1:'),
    ("reply: only Finish must be alone", A, 'ender = next((n for n in ("Finish", "ReportConflict") if n in names), None)',
     'ender = next((n for n in ("Finish",) if n in names), None)'),
    ("prompt: no rule", A, '    if "ReportConflict" in names:\n        lines +=', '    if False:\n        lines +='),
    ("feedback: no unconfirmed report", A, 'if isinstance(c, dict) and c.get("state") == "unconfirmed":', "if False:"),
    ("prompt: the findings not shown", A, '        if feedback.get("conflict"):   #', '        if False:   #'),
    ("prompt: the humans judgement not shown", A, '        if feedback.get("not_a_conflict"):', "        if False:"),
    # the run
    ("run: tool version ignores the state", R, 'json.dumps(state.get("conflict"), sort_keys=True)', "json.dumps(None, sort_keys=True)"),
    ("run: the toolbox gets no state", R, '                      conflict=state.get("conflict"))', "                      conflict=None)"),
    ("run: the attempt does not carry the report", R, '**({"conflict": a["conflict"]} if a.get("conflict") else {})},', "},"),
    ("run: a failed verdict is not verified", R, '            if v["outcome"] == "fail":\n                record = intake.record_for', '            if False:\n                record = intake.record_for'),
    ("run: a passing verdict records nothing", R, '            elif v["outcome"] == "pass":      #', "            elif False:      #"),
    ("run: blocked is not handled", R, '            if conf["state"] == "blocked":', "            if False:"),
    ("run: confirmed is not handled", R, '            if conf["state"] == "confirmed":', "            if False:"),
    ("run: confirmed gets another reason", R, 'blocked="test_conflict", verdict=summary', 'blocked="invalid_contract", verdict=summary'),
    ("run: the state is not kept when the run stops", R, "failures=history, **new_conflict)", "failures=history)"),
    ("run: the state is not kept for the next attempt", R, "failures=history, **new_conflict,", "failures=history,"),
    ("run: no initial state", R, '**({"conflict": initial_conflict} if initial_conflict else {}))', ")"),
    ("run: the result lacks the state", R, '"loop_policy", "conflict")}', '"loop_policy")}'),
    ("status: test_conflict is not a reason", "codetask/status.py", ', "provider_failed", "test_conflict"}', ', "provider_failed"}'),
    ("config: the tool is not offered", "config.yaml", "run_validation, report_conflict]", "run_validation]"),
    # the router
    ("retry: a bare retry after a confirmed report", J, "        if confirmed and not not_a_conflict:", "        if False:"),
    ("retry: the flag for any job", J, "        if not_a_conflict and not confirmed:", "        if False:"),
    ("retry: the judgement is forgotten", J, "        if before_nc and not not_a_conflict:", "        if False:"),
    ("retry: the flag does not reach the run", J, "if nc else None, red=deps.conflict_red)", "if False else None, red=deps.conflict_red)"),
    ("retry: the humans state looks like a report", J, 'and not r["conflict"].get("by_human"):', ":"),
    ("retry: no log of the flag", J, '**({"not_a_conflict": True} if not_a_conflict else {}))', ")"),
    ("status: a bare retry is offered", J, 'f"argus retry {job.id} --not-a-conflict"] if blocked == "test_conflict"',
     'f"argus retry {job.id} --not-a-conflict"] if False'),
    ("status: the confirmed text is missing", J, 'if c.get("state") == "confirmed" or blocked == "test_conflict":', "if False:"),
]

if __name__ == "__main__":
    killed = 0
    for name, f, old, new in M:
        p = WT / f
        orig = p.read_text()
        assert orig.count(old) == 1, (name, orig.count(old))
        p.write_text(orig.replace(old, new, 1))
        r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", TT], cwd=WT, capture_output=True, text=True)
        p.write_text(orig)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        k = "failed" in last
        killed += k
        fails = [line for line in r.stdout.splitlines() if line.startswith("FAILED")][:1]
        print(f"{'KILLED ' if k else 'SURVIVED'} {name}: {fails or last}", flush=True)
    print(f"RESULT: {killed}/{len(M)} killed")
