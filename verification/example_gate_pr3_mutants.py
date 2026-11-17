"""Mutants for SPEC_EXAMPLE_GATE PR 3 (the writers: codetask/issue_writer.py, codetask/prd_writer.py, router/issue.py, router/prd_job.py, router/chat_actions.py, router/example_gate.py, codetask/examples.py observed): each applied alone in a worktree; killed = a test FAILED and pytest reported no error.
Usage: <this> <worktree> <python> [name fragments to run only some]. Docker is not needed.
"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
ONLY = sys.argv[3:]
T = ["-rfEs", "tests/test_example_writer.py", "tests/test_example_prd.py", "tests/test_examples.py"]



M = [
    ('the examples gate is not called', 'codetask/issue_writer.py', [('problems, result = issue_gate(args, source=source, environment=env, examples_check=sup.hook)', 'problems, result = issue_gate(args, source=source, environment=env)')]),
    ('examples are not required', 'codetask/issue_writer.py', [('            problems.append("an issue needs examples, or no_examples with the reason there are none (one line)")', '            pass')]),
    ('examples and a reason together are fine', 'codetask/issue_writer.py', [('    if given and reason:\n        problems.append("give examples or no_examples, not both")', '    if False:\n        pass')]),
    ('examples are accepted where no runner runs them', 'codetask/issue_writer.py', [('            problems.append("this environment has no example runner: leave examples empty")', '            pass')]),
    ('the form check is skipped', 'codetask/issue_writer.py', [('    parsed, found = ex.parse(raw)\n    problems += found', '    parsed, found = ex.parse(raw)')]),
    ('the examples are not run', 'codetask/issue_writer.py', [('    if not found and execute:', '    if False:')]),
    ('the block is not written into the issue', 'codetask/issue_writer.py', [('            final = eg.with_block(final, info["examples"])', '            pass')]),
    ("the writer's own block is not stripped", 'codetask/issue_writer.py', [('        issue = eg.without_block(issue.strip())              # a block the harness wrote earlier is not written twice', '        issue = issue.strip()')]),
    ('a fence is not refused', 'codetask/issue_writer.py', [('if eg.mentions(issue) or issue.count("```") % 2 or re.search(', 'if False and re.search(')]),
    ('example lines left over are not refused', 'codetask/issue_writer.py', [('or re.search(r\'^\\s*\\{"id":\\s*"e\\d\', issue, re.M):', 'or False:')]),
    ('code output is not labelled in a rejection', 'codetask/issue_writer.py', [('        problems += [f"{p} {ex.RUN_LABEL}" if "the code gave" in p else p for p in why]', '        problems += why')]),
    ('a pass that printed nothing blocks the writer', 'codetask/issue_writer.py', [('        except eg.NoResult:', '        except ZeroDivisionError:')]),
    ('the tier is not tracked by id', 'codetask/issue_writer.py', [('        fresh = [{"id": i, "from": prev[i], "to": t} for i, t in tiers.items() if i in prev and prev[i] != t]', '        fresh = []')]),
    ('the tier is not tracked by content', 'codetask/issue_writer.py', [('            if was and was != e["tier"] and not any(m["id"] == e["id"] for m in fresh):', '            if False:')]),
    ('the tier records are shared by items', 'codetask/issue_writer.py', [('kt, km = f"tiers:{self.run_id}:{scope}", f"moves:{self.run_id}:{scope}"', 'kt, km = f"tiers:{self.run_id}", f"moves:{self.run_id}"')]),
    ('the count of tries starts at 0 on a new object', 'codetask/issue_writer.py', [('        while self.memo.get(f"runexample:{self.run_id}:{n}") is not None:      # counted from the memo: a resume does not restart at 0\n            n += 1', '        pass')]),
    ('the limit of tries is gone', 'codetask/issue_writer.py', [('        if n >= RUN_EXAMPLE_MAX:', '        if False:')]),
    ('RunExample runs without the permission', 'codetask/issue_writer.py', [('        if "run_example" not in self.allowed or not self.runs:', '        if not self.runs:')]),
    ('RunExample is offered without the permission', 'codetask/issue_writer.py', [('        return [RunExample] if self.runs and "run_example" in self.allowed else []', '        return [RunExample] if self.runs else []')]),
    ('RunExample output is not labelled', 'codetask/issue_writer.py', [('        return f"RunExample result {ex.RUN_LABEL}: {ex.observed(raw)}"', '        return f"RunExample result: {ex.observed(raw)}"')]),
    ('the memo versions do not carry the image', 'codetask/issue_writer.py', [('versions, runs = {**VERSIONS, **sup.versions}, sup.runs', 'versions, runs = dict(VERSIONS), sup.runs')]),
    ('the prompt always asks for examples', 'codetask/issue_writer.py', [('    if not runs:\n        return SYSTEM + "\\n" + NO_RUNNER_RULES', '    if False:\n        return SYSTEM + "\\n" + NO_RUNNER_RULES')]),
    ("an unavailable sandbox blocks the writer's job again", 'codetask/issue_writer.py', [('            return {**out, "status": FAILED, "stop_reason": a["result"]["sandbox_unavailable"]}', '            return {**out, "status": BLOCKED, "stop_reason": a["result"]["sandbox_unavailable"]}')]),
    ("an unavailable sandbox blocks the PRD job again", 'codetask/prd_writer.py', [('                return {**out, "status": FAILED, "stop_reason": a["result"]["sandbox_unavailable"]}', '                return {**out, "status": BLOCKED, "stop_reason": a["result"]["sandbox_unavailable"]}')]),
    ('an environment is a runner when it is not configured', 'codetask/issue_writer.py', [('    return bool(env) and ct.runner(env) == "pytest"', '    return True')]),
    ('the first item is not run', 'codetask/prd_writer.py', [('examples=lambda k: (lambda a: sup.hook(a, scope=str(k), execute=(k == 1))))', 'examples=lambda k: (lambda a: sup.hook(a, scope=str(k), execute=False)))')]),
    ('every item is run', 'codetask/prd_writer.py', [('examples=lambda k: (lambda a: sup.hook(a, scope=str(k), execute=(k == 1))))', 'examples=lambda k: (lambda a: sup.hook(a, scope=str(k), execute=True)))')]),
    ('a later example may use a created name as same', 'codetask/prd_writer.py', [('            if e["tier"] != "after" and used:', '            if False:')]),
    ('only same is held to the created-name rule', 'codetask/prd_writer.py', [('            if e["tier"] != "after" and used:', '            if e["tier"] == "same" and used:')]),
    ('a short created name matches too', 'codetask/prd_writer.py', [('len(n) >= iw.TOUCH_MIN and n in e["setup"] + " " + e["run"]', 'n in e["setup"] + " " + e["run"]')]),
    ('the examples of an item are not kept', 'codetask/prd_writer.py', [('                    **({"examples": res["examples"]} if res.get("examples") else {})})', '                    })')]),
    ('the PRD blocks no sandbox failure', 'codetask/prd_writer.py', [('            except SandboxUnavailable as e:\n                log.emit("prd_checked", submit=n, ok=False, problems=["sandbox_unavailable"], kinds=["sandbox"])', '            except ZeroDivisionError as e:\n                log.emit("prd_checked", submit=n, ok=False, problems=["sandbox_unavailable"], kinds=["sandbox"])')]),
    ('the first issue turn does not pin', 'router/issue.py', [('            try:\n                _pin_environment(job, cfg)\n            except rj.Refused as e:\n                job.move(ABANDONED, deps, reason=f"not started: {str(e)[:200]}")\n                raise', '            pass')]),
    ('a reply does not pin', 'router/issue.py', [('        _pin_environment(job, cfg)\n        with rj.live(deps, rj.stage_config(cfg, float(s["turn"]["cap_usd"])), [s["role"]],\n                     _screen(job, cfg, "next turn"), job=job):', '        with rj.live(deps, rj.stage_config(cfg, float(s["turn"]["cap_usd"])), [s["role"]],\n                     _screen(job, cfg, "next turn"), job=job):')]),
    ('a resume does not pin', 'router/issue.py', [('    _preflight(cfg, job.data["max_usd"])\n    _pin_environment(job, cfg)', '    _preflight(cfg, job.data["max_usd"])')]),
    ('a changed image is not refused', 'router/issue.py', [('    why = rj.environment_changed(job, cfg)\n    if why:\n        raise rj.Refused(f"job {job.id}: {why}; nothing was started")', '    why = None')]),
    ('an environment without a runner is pinned', 'router/issue.py', [('    if not iw.has_runner(cfg, env):\n        return\n    if "environment_image" not in job.data:', '    if "environment_image" not in job.data:')]),
    ('the screen does not say code runs', 'router/issue.py', [('example code written by the model RUNS in the sandbox (RunExample and the gate: no network', 'example (RunExample and the gate: no network')]),
    ('the runner is not given to the writer', 'router/issue.py', [('prepare=lambda run_dir: source, example_runner=deps.example_runner)', 'prepare=lambda run_dir: source)')]),
    ('the card data is not kept', 'router/issue.py', [('                                     **({"examples": w["examples"]} if w.get("examples") else {})})     # the card\'s data (T2)', '                                     })')]),
    ('the PRD turn does not pin on a reply', 'router/prd_job.py', [('        ri._pin_environment(job, cfg)\n        with rj.live(deps, rj.stage_config(cfg, float(s["turn"]["cap_usd"])), [s["role"]],\n                     _screen(job, cfg, "next turn"), job=job):\n            if rebase:', '        with rj.live(deps, rj.stage_config(cfg, float(s["turn"]["cap_usd"])), [s["role"]],\n                     _screen(job, cfg, "next turn"), job=job):\n            if rebase:')]),
    ('the PRD turn does not pin on a resume', 'router/prd_job.py', [('    ri._pin_environment(job, cfg)\n    with rj.live(', '    with rj.live(')]),
    ('the PRD runner is not given', 'router/prd_job.py', [('item_max=int(ri._settings(cfg)["message_max"]), example_runner=deps.example_runner)', 'item_max=int(ri._settings(cfg)["message_max"]))')]),
    ('the PRD card data is not kept', 'router/prd_job.py', [('            "examples": [it.get("examples") for it in w["items"]],', '            "examples": [None for it in w["items"]],')]),
    ('the chat card never says code runs', 'router/chat_actions.py', [('        if not has_runner(cfg, environment):\n            return {}', '        return {}')]),
    ('the chat card always says it', 'router/chat_actions.py', [('        if not has_runner(cfg, environment):\n            return {}', '        if False:\n            return {}')]),
    ('a docker failure is a verdict', 'router/example_gate.py', [('if r.get("exit_code") in (125, 126, 127) or r.get("cleanup_failed"):', 'if False:')]),
    ('only one docker code counts', 'router/example_gate.py', [('if r.get("exit_code") in (125, 126, 127) or r.get("cleanup_failed"):', 'if r.get("exit_code") in (125,) or r.get("cleanup_failed"):')]),
    ('the bare pass may print nothing', 'router/example_gate.py', [('    if whatif and _no_pass_ran([{"actual": r.get("error", "") + ""} for r in bare.values()]):', '    if False:')]),
    ('the block is written twice', 'router/example_gate.py', [('    return "\\n".join(body + [""] + block_text(examples).split("\\n") + ["", lines[-1]])', '    return "\\n".join(body + [""] + block_text(examples).split("\\n") + block_text(examples).split("\\n") + ["", lines[-1]])')]),
    ('a stored block is not taken out', 'router/example_gate.py', [('    return re.sub(r"\\n*" + FENCE.pattern + r"\\n*", "\\n\\n", text, flags=FENCE.flags)', '    return text')]),
    ('observed shows a non-JSON value as a value', 'codetask/examples.py', [('        if raw.get("invalid"):\n            return f"not JSON', '        if False:\n            return f"not JSON')]),
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
