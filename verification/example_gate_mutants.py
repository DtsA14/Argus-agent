"""Mutants for SPEC_EXAMPLE_GATE PR 2 (router/example_gate.py, the gate in router/job.py, router/apply.py, scripts/argus.py, acceptance/repro.py patched_tree, codetask/examples.py verdict): each applied alone in a worktree; killed = a test FAILED and pytest reported no error.
Usage: <this> <worktree> <python> [name fragments to run only some]. Docker is not needed.
"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
ONLY = sys.argv[3:]
T = ["-rfEs", "tests/test_example_gate.py", "tests/test_examples.py", "tests/test_repro_patched.py", "tests/test_xdist_groups.py"]
E, J, A, C, R, X = "router/example_gate.py", "router/job.py", "router/apply.py", "scripts/argus.py", "acceptance/repro.py", "codetask/examples.py"
GATE = ["-rfEs", "tests/test_example_gate.py"]


M = [
    ("a second block is accepted", E, [("    if len(found) > 1:", "    if False:")]),
    ("a block with problems still gives its examples", E, [("return True, ([] if problems else examples), problems", "return True, examples, problems")]),
    ("an environment never lacks a runner", E, [("return bool(env) and ct.runner(env) != \"pytest\"", "return False")]),
    ("a python environment lacks a runner", E, [("return bool(env) and ct.runner(env) != \"pytest\"", "return bool(env)")]),
    ("the audit key ignores the patch", E, [("f\"examples-audit\\n{patch_sha256}\\n{digest(examples)}\"", "f\"examples-audit\\n{digest(examples)}\"")]),
    ("the audit key ignores the examples", E, [("f\"examples-audit\\n{patch_sha256}\\n{digest(examples)}\"", "f\"examples-audit\\n{patch_sha256}\"")]),
    ("the intake key ignores the base", E, [("f\"examples-intake\\n{snapshot_sha256}\\n{digest(examples)}\"", "f\"examples-intake\\n{digest(examples)}\"")]),
    ("a stale result is not noticed", E, [("        if rec.get(\"key\") != key:", "        if False:")]),
    ("a skipped result is not read", E, [("        if rec.get(\"skipped\"):", "        if False:")]),
    ("a pending marker reads as results", E, [("        if rec.get(\"results\") is None:", "        if False:")]),
    ("the results need not be the examples", E, [(" or sorted(r[\"id\"] for r in results) != sorted(ids):", ":")]),
    ("a status of any word is read", E, [("or raw.get(\"status\") not in STATUSES:", "or False:")]),
    ("a damaged file is a finished result", E, [("    except Exception:\n        return \"error\", None", "    except Exception:\n        return \"results\", []")]),
    ("an error does not count as failed", E, [("return sorted(r[\"id\"] for r in results if r[\"status\"] != ex.PASS)", "return sorted(r[\"id\"] for r in results if r[\"status\"] == ex.FAIL)")]),
    ("an unchecked result counts as passed", E, [("return sorted(r[\"id\"] for r in results if r[\"status\"] != ex.PASS)", "return sorted(r[\"id\"] for r in results if r[\"status\"] not in (ex.PASS, ex.UNCHECKED))")]),
    ("the tautology check is not made", E, [("        why = ex.tautology_problem(e, tree)", "        why = None")]),
    ("an override that changes nothing is accepted", E, [("            if (b[\"status\"], json.dumps(b[\"actual\"], sort_keys=True)) ==", "            if False and (b[\"status\"], json.dumps(b[\"actual\"], sort_keys=True)) ==")]),
    ("the run without overrides uses them", E, [("ex.run_pass(whatif, runner, root=root, with_overrides=False)", "ex.run_pass(whatif, runner, root=root, with_overrides=True)")]),
    ("an after that passes on the base is accepted", E, [("            if r[\"status\"] == ex.PASS:\n                problems.append(f\"example {e['id']} (after)", "            if False:\n                problems.append(f\"example {e['id']} (after)")]),
    ("a wrong same is not a problem", E, [("        if r[\"status\"] != ex.PASS:\n            problems.append(f\"example {e['id']} ({e['tier']})", "        if False:\n            problems.append(f\"example {e['id']} ({e['tier']})")]),
    ("an after is recorded as a pass", E, [("\"tier\": \"after\", \"status\": ex.UNCHECKED", "\"tier\": \"after\", \"status\": ex.PASS")]),
    ("the audit applies the overrides", E, [("return ex.evaluate(examples, runner, root=root, with_overrides=False)", "return ex.evaluate(examples, runner, root=root, with_overrides=True)")]),
    ("the audit leaves out the after examples", E, [("return ex.evaluate(examples, runner, root=root, with_overrides=False)", "return ex.evaluate([e for e in examples if e[\"tier\"] != \"after\"], runner, root=root, with_overrides=False)")]),
    ("the gate is not called at intake", J, [("        _example_gate(job, cfg, deps)           #", "        pass                                    #")]),
    ("a block with problems does not block", J, [("    if problems:\n        block(\"examples: \"", "    if False:\n        block(\"examples: \"")]),
    ("a wrong example does not block", J, [("    if found:\n        block(", "    if False:\n        block(")]),
    ("a blocked job is not moved to BLOCKED", J, [("        job.move(BLOCKED, deps, reason=clean(reason)[:700])\n        raise Refused(f\"job {job.id}: {clean(what)", "        raise Refused(f\"job {job.id}: {clean(what)")]),
    ("an unavailable sandbox lets the job through", J, [("    except SandboxUnavailable as e:\n        block(f\"sandbox_unavailable: {e}\", f\"the sandbox is not available, so the examples could not be run ({e})\")", "    except SandboxUnavailable as e:\n        results, found = [], []")]),
    ("an unavailable sandbox is called a verdict", J, [("block(f\"sandbox_unavailable: {e}\"", "block(f\"examples: {e}\"")]),
    ("a crash of the check lets the job through", J, [("    except Exception as e:\n        block(f\"examples: the check could not run ({type(e).__name__})\", f\"the examples could not be run ({type(e).__name__})\")", "    except Exception as e:\n        found = []")]),
    ("an environment without a runner is run anyway at intake", J, [("    if eg.no_runner(cfg, job.data[\"inputs\"].get(\"environment\")):\n        eg.store(path, key, skipped=eg.RUNNER_NOTE)\n        return", "    if False:\n        return")]),
    ("an environment without a runner is run anyway at the audit", J, [("        if eg.no_runner(cfg, job.data[\"inputs\"].get(\"environment\")):\n            eg.store(path, key, skipped=eg.RUNNER_NOTE)\n            return True", "        if False:\n            return True")]),
    ("the runner gets no time for the examples", J, [(", \"timeout_s\": exl.pass_timeout_s(n)}", "}")]),
    ("the audit is not run after the agent", J, [("    _examples_audit(job, sid, cfg, deps)          # SPEC_EXAMPLE_GATE 4(3)", "    pass                                          # SPEC_EXAMPLE_GATE 4(3)")]),
    ("the pending marker is not written", J, [("        eg.store(path, key)                                   # the marker", "        pass                                                  # the marker")]),
    ("the reason of a failed audit is not kept", J, [("                eg.store(path, key, reason=reason)", "                pass")]),
    ("the audit runs on the unpatched tree", J, [("        with repro.patched_tree(job.root / \"fixtures\" / \"repos\" / BASE, patch) as tree:\n            runner, root = example_runner(job, cfg, deps, tree, len(examples))\n            results = eg.audit", "        with repro.patched_tree(job.root / \"fixtures\" / \"repos\" / BASE) as tree:\n            runner, root = example_runner(job, cfg, deps, tree, len(examples))\n            results = eg.audit")]),
    ("the audit of an invalid package runs", J, [("if not present or problems or not rv.get(\"valid\"):", "if not present or problems:")]),
    ("the decision ignores the sha it is given", J, [("    sha = sha or repro.patch_sha(Path(rv[\"dir\"]) / \"changes.patch\")", "    sha = repro.patch_sha(Path(rv[\"dir\"]) / \"changes.patch\")")]),
    ("any allow list is accepted", J, [("    if allow != failed:\n        if failed:", "    if False:\n        if failed:")]),
    ("a longer allow list is accepted", J, [("    if allow != failed:\n        if failed:", "    if not set(failed) <= set(allow):\n        if failed:")]),
    ("a pending audit is accepted", J, [("    if kind not in (\"nogate\", \"skipped\", \"results\"):", "    if kind not in (\"nogate\", \"skipped\", \"results\", \"pending\"):")]),
    ("a missing audit is accepted", J, [("    if kind not in (\"nogate\", \"skipped\", \"results\"):", "    if kind not in (\"nogate\", \"skipped\", \"results\", \"none\"):")]),
    ("a stale audit is accepted", J, [("    if kind not in (\"nogate\", \"skipped\", \"results\"):", "    if kind not in (\"nogate\", \"skipped\", \"results\", \"stale\"):")]),
    ("a block that cannot be read is accepted", J, [("    if kind == \"malformed\":\n        raise Refused(", "    if False:\n        raise Refused(")]),
    ("applied by hand is not gated", J, [("        failed = examples_decision(job, allow_failed_examples, sha=hashlib.sha256(data).hexdigest())", "        failed = []")]),
    ("the failed ids are not recorded at applied", J, [("**({\"examples_failed\": failed} if failed else {}), **extra)", "**extra)")]),
    ("resume does not run the audit again", J, [("        if state == REVIEW_READY and examples_audit_state(job)[0] in", "        if False and examples_audit_state(job)[0] in")]),
    ("resume does not run a pending audit", J, [("in (\"none\", \"stale\", \"pending\", \"error\"):\n            done", "in (\"none\", \"stale\", \"error\"):\n            done")]),
    ("resume answers a failed audit as done", J, [("            if not done:\n                why = examples_audit_state", "            if False:\n                why = examples_audit_state")]),
    ("status does not show the audit", J, [("        if d[\"state\"] == REVIEW_READY:\n            out += example_audit_lines(job)\n", "")]),
    ("the approve screen does not show the examples", J, [("                 *repro_lines(job),\n                 *example_lines(job),", "                 *repro_lines(job),")]),
    ("apply decides after the commit only", A, [("        failed = rj.examples_decision(job, allow, sha=sha)", "        failed = []")]),
    ("apply does not record the ids at apply_started", A, [("read_sha=read_sha, **({\"examples_failed\": failed} if failed else {}))", "read_sha=read_sha)")]),
    ("a recovered apply forgets the flag", A, [("read_sha, allow=allow, recovered=True)", "read_sha, recovered=True)")]),
    ("the record forgets the flag", A, [("require_as_is=True, allow_failed_examples=allow, **extra)", "require_as_is=True, **extra)")]),
    ("the command line drops the flag at apply", C, [("note=o.note, allow_failed_examples=o.allow_failed_examples)", "note=o.note)")]),
    ("the command line drops the flag at applied", C, [("                                      allow_failed_examples=o.allow_failed_examples).id", "                                      ).id")]),
    ("the flag takes any text", C, [("    if not ids or any(not re.fullmatch(r\"e[1-9][0-9]?\", t) for t in ids):", "    if False:")]),
    ("the patch is not applied to the copy", R, [("        if patch_file is not None:", "        if False:")]),
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
