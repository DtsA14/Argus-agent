"""Mutants for SPEC_VF_O1_CANARY_NONCE: each applied alone in a worktree, the tests run with -x; killed = a test FAILED and pytest reported
no error. Mutants marked DOCKER run tests/test_vf_forger.py (the image pins must be exported). Usage: <this> <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
UNIT = ["-rfEs", "tests/test_vf_canary.py", "tests/test_pytest_validation.py"]
DOCKER = ["-rfEs", "tests/test_vf_forger.py"]
V = "acceptance/validation.py"
M = [
    # --- the host side: reading the record
    ("record line kept in the text", V, [("            mine.append(l[len(nonce):])\n", "            mine.append(l[len(nonce):])\n            kept.append(l)\n")], UNIT),
    ("the script's blank line kept", V, [("            if kept and kept[-1] == \"\\n\":", "            if False:")], UNIT),
    ("several records accepted", V, [("    if len(mine) == 1:\n", "    if len(mine) >= 1:\n")], UNIT),
    ("a missing record accepted", V, [("    if rec is None:\n        return [(\"G1\"", "    if rec is None:\n        return []\n        return [(\"G1\"")], UNIT),
    ("canary never checked", V, [("    if rec.get(\"canary_error\") or type(rec.get(\"canary_rc\")) is not int or rec[\"canary_rc\"] != 1 or canary != CANARY_WANTED:", "    if False:")], UNIT),
    ("canary_rc not checked", V, [(" or type(rec.get(\"canary_rc\")) is not int or rec[\"canary_rc\"] != 1", "")], UNIT),
    ("canary_error not checked", V, [("rec.get(\"canary_error\") or ", "")], UNIT),
    ("canary content not checked", V, [(" or canary != CANARY_WANTED:", ":")], UNIT),
    ("rc not compared with the exit code", V, [("    if rec[\"rc\"] != r.get(\"exit_code\"):", "    if False:")], UNIT),
    ("counts not compared", V, [("    if rec[\"counts\"] != counts or rec[\"sha\"] != tests_sha(parsed[\"tests\"]):", "    if rec[\"sha\"] != tests_sha(parsed[\"tests\"]):")], UNIT),
    ("sha not compared", V, [("    if rec[\"counts\"] != counts or rec[\"sha\"] != tests_sha(parsed[\"tests\"]):", "    if rec[\"counts\"] != counts:")], UNIT),
    ("record problems never added to the reasons", V, [("        for code, _ in gate:", "        for code, _ in []:")], UNIT),
    ("the detail goes to the agent", V, [("problems.append(f\"{TRUST} (harness check {code})\")", "problems.append(f\"{TRUST} (harness check {code}): {dict(gate)[code]}\")")], UNIT),
    ("one reason for every rule", V, [("(harness check {code})", "(harness check)")], UNIT),
    ("the nonce is a constant", V, [("    return \"ARGUS-GREEN-\" + secrets.token_hex(16) + \":\"", "    return \"ARGUS-GREEN-\" + \"0\" * 32 + \":\"")], UNIT),
    ("the hash ignores the status", V, [("    pairs = sorted([n, s] for n, s in tests.items())\n    return hashlib.sha256(json.dumps(pairs, ensure_ascii=True, separators=(\",\", \":\")).encode()).hexdigest()\n\n\ndef split_record",
                                         "    pairs = sorted([n] for n, s in tests.items())\n    return hashlib.sha256(json.dumps(pairs, ensure_ascii=True, separators=(\",\", \":\")).encode()).hexdigest()\n\n\ndef split_record")], UNIT),
    # --- the script
    ("script: session 2 inherits PYTEST_ADDOPTS", V, [("for k in (\"PYTEST_ADDOPTS\", \"PYTEST_PLUGINS\"):\n    os.environ.pop(k, None)\n", "pass\n")], UNIT),
    ("script: exits 0 whatever session 1 returned", V, [("sys.exit(rc1)", "sys.exit(0)")], UNIT),
    ("script: session 2 output not discarded", V, [("    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):", "    if True:")], UNIT),
    ("script: a tie goes to the last report", V, [("        if old is None or RANK.get(status, 0) > RANK.get(old, 0):", "        if old is None or RANK.get(status, 0) >= RANK.get(old, 0):")], UNIT),
    ("script: the hash ignores the status", V, [("def sha(tests):\n    pairs = sorted([n, s] for n, s in tests.items())", "def sha(tests):\n    pairs = sorted([n] for n, s in tests.items())")], UNIT),
    ("script: subtest reports counted", V, [("        if hasattr(report, \"context\"):\n            return\n", "")], UNIT),
    ("script: the canary is never recorded", V, [("    for n, s in r2.tests.items():", "    for n, s in []:")], UNIT),
    ("script: the exception type is not recorded", V, [("s + \":\" + str(r2.exc.get(n))", "s")], UNIT),
    ("script: argv not reset", V, [("sys.argv = [_pm.__file__, *fixed, *targets]\n", "")], UNIT),
    ("script: the record without the leading newline", V, [("sys.stdout.write(\"\\n\" + nonce + json.dumps(rec", "sys.stdout.write(nonce + json.dumps(rec")], UNIT),
    ("a bool rc is read as an integer", V, [("all(type(got.get(k)) is t for k, t in RECORD_KEYS.items())", "all(isinstance(got.get(k), t) for k, t in RECORD_KEYS.items())")], UNIT),
    ("a bool canary_rc is read as an integer", V, [("type(rec.get(\"canary_rc\")) is not int or ", "")], UNIT),
    ("the shape check is the sha only", V, [("all(type(got.get(k)) is t for k, t in RECORD_KEYS.items())", "isinstance(got.get(\"sha\"), str)")], UNIT),
    ("pytest_run returns the raw text", V, [("    return {**r, \"stdout\": text}, rec", "    return r, rec")], UNIT),
    # -c, --confcutdir and the ini file written in the canary directory each protect alone (defence in depth): only all three removed can be seen
    ("script: no ini file, no -c and no confcutdir for session 2", V, [("\"-c\", d + \"/pytest.ini\", \"--confcutdir\", d, ", ""), ("    with open(d + \"/pytest.ini\", \"w\") as f:\n        f.write(\"[pytest]\\n\")\n", "")], UNIT),
    ("script: the canary write error is not caught", V, [("except OSError as e:\n    err = type(e).__name__\nif err is None:", "except ZeroDivisionError as e:\n    err = type(e).__name__\nif err is None:")], UNIT),
    ("script: the canary directory is kept", V, [("    shutil.rmtree(d, ignore_errors=True)\n", "")], UNIT),
    ("script: tempfile.tempdir not reset", V, [("tempfile.tempdir = None\n", "")], UNIT),
    ("script: sys.path not restored", V, [("sys.path[:] = saved_path\n", "")], UNIT),
    ("script: nodes keyed by nodeid, not by the printed line", V, [("            line = self.cfg.pluginmanager.get_plugin(\"terminalreporter\")._locationline(report.nodeid, *report.location)\n            return line[:-1] if line.endswith(\" \") else line", "            return report.nodeid")], UNIT),
    ("script: wasxfail not read before the phase", V, [("        if hasattr(report, \"wasxfail\") and report.skipped:\n            status = \"expected failure\"\n        elif hasattr(report, \"wasxfail\") and report.passed:\n            status = \"unexpected success\"\n        elif report.when != \"call\":", "        if report.when != \"call\":")], UNIT),
    # --- the wiring
    ("DOCKER: run_validation gives pytest no nonce", V, [("else green_nonce() if kind(spec) == \"pytest\" else None", "else None")], DOCKER),
    ("DOCKER: the runner is the old -m pytest", V, [("            return [*head, GREEN, nonce, json.dumps(PYTEST_FIXED), *spec[\"args\"][2:]]", "            return [\"python3\", \"-I\", \"-B\", *PYTEST_PREFIX, *PYTEST_FIXED, *spec[\"args\"][2:]]")], DOCKER),
]

if __name__ == "__main__":
    killed = 0
    for name, F, edits, T in M:
        p = WT / F
        orig = p.read_text()
        text = orig
        stale = [a[:60] for a, _ in edits if text.count(a) != 1]
        if stale:
            print(f"STALE   {name}: pattern not found exactly once: {stale}", flush=True)
            continue
        for a, b in edits:
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
