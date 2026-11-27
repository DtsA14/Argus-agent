"""Mutants for SPEC_CHAT_PACKAGES S2 (router/env_job.py, the env job kind, `argus env add|abandon`, the snapshot rule). Applied alone; killed = a test FAILED.
Run in a throwaway worktree. Usage: <this> <worktree> <python> [name-part ...]"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
ONLY = sys.argv[3:]
E, J, S, A = "router/env_job.py", "router/job.py", "router/stage_data.py", "scripts/argus.py"
T = ["-rfEs", "tests/test_env_job.py", "tests/test_env_cli.py"]
FLAGS = [("--cap-drop", '"--cap-drop", "ALL", '), ("--security-opt", '"--security-opt", "no-new-privileges", '), ("--read-only", '"--read-only", '),
         ("--user", '"--user", f"{uid}:{gid}", '), ("--memory", '"--memory", f"{s[\'memory_mb\']}m", "--memory-swap", f"{s[\'memory_mb\']}m", '),
         ("--pids-limit", '"--pids-limit", str(s["pids_limit"]), '), ("the read-only definition mount", '"-v", f"{in_dir}:/in:ro", '),
         ("the tmpfs", '"--tmpfs", f"/tmp:rw,size={s[\'tmp_mb\']}m,mode=1777",\n'), ("--entrypoint", '"--entrypoint", "node", ')]
M = [
    ("a bool is a setting", E, [("if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:", "if not isinstance(v, int) or not lo <= v <= hi:")]),
    ("a setting has no upper bound", E, [("or not lo <= v <= hi:", "or not lo <= v:")]),
    ("a setting has no lower bound", E, [("or not lo <= v <= hi:", "or not v <= hi:")]),
    ("an unknown setting key is accepted", E, [("    if extra:\n        raise rj.Refused(f\"config env_packages has unknown keys", "    if False:\n        raise rj.Refused(f\"config env_packages has unknown keys")]),
    ("a missing setting key is accepted", E, [("    if miss:\n        raise rj.Refused(f\"config env_packages lacks", "    if False:\n        raise rj.Refused(f\"config env_packages lacks")]),
    ("BUILDING cannot fail", E, [(", (BUILDING, READY), (BUILDING, REFUSED), (BUILDING, FAILED)}", ", (BUILDING, READY), (BUILDING, REFUSED)}")]),
    ("a built environment can be abandoned in the table", E, [(", (BUILDING, READY), (BUILDING, REFUSED), (BUILDING, FAILED)}", ", (BUILDING, READY), (BUILDING, REFUSED), (BUILDING, FAILED), (READY, ABANDONED)}")]),
    ("a report that waits is not live", E, [("LIVE = (NEW, RESOLVING, AWAITING_HUMAN, BUILDING)", "LIVE = (NEW, RESOLVING, BUILDING)")]),
    ("the creation lock is shared", E, [("fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)\n        except OSError:\n            raise rj.Refused(\"another package", "fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)\n        except OSError:\n            raise rj.Refused(\"another package")]),
    ("a report expires at the limit", E, [("if at is not None and now is not None and now - at > s[\"report_ttl_hours\"] * 3600:", "if at is not None and now is not None and now - at >= s[\"report_ttl_hours\"] * 3600:")]),
    ("a report never expires", E, [("if at is not None and now is not None and now - at > s[\"report_ttl_hours\"] * 3600:", "if False:")]),
    ("a dead job is not failed", E, [("                    job.move(FAILED, deps, reason=\"the process that ran it is gone\")\n                    _remove_containers(job.id, docker)", "                    pass")]),
    ("a dead job's containers stay", E, [("                    job.move(FAILED, deps, reason=\"the process that ran it is gone\")\n                    _remove_containers(job.id, docker)", "                    job.move(FAILED, deps, reason=\"the process that ran it is gone\")")]),
    ("one container name is not removed", E, [('    for part in ("", "-v", "-b"):', '    for part in ("", "-v"):')]),
    ("a live job is settled too", E, [("        try:\n            with job.lock():\n                job.data = rj.open_job(job.id, job.dir.parent).data\n", "        try:\n            if True:\n                job.data = rj.open_job(job.id, job.dir.parent).data\n")]),
    ("a python repository is accepted", E, [("    if envs[env].get(\"runner\") != \"vitest\":", "    if False:")]),
    ("the chat is not required to start", E, [("    if via != \"ui\":\n        raise rj.Refused(\"a package request is started from the chat", "    if False:\n        raise rj.Refused(\"a package request is started from the chat")]),
    ("the job id is not checked", E, [("    if why:\n        raise rj.Refused(f\"{why}; nothing was started\")\n    s = settings(cfg)", "    if False:\n        raise rj.Refused(f\"{why}; nothing was started\")\n    s = settings(cfg)")]),
    ("the lines are not checked", E, [("    items, problem = ep.parse_lines(text)\n    if problem:", "    items, problem = ep.parse_lines(text)\n    if False:")]),
    ("a base that is not pinned is accepted", E, [("    if not BASE_IMAGE.fullmatch(base):", "    if False:")]),
    ("a base only starts with a digest shape", E, [("    if not BASE_IMAGE.fullmatch(base):", "    if not BASE_IMAGE.match(base):")]),
    ("a locked name is accepted", E, [("    problem = ep.refuse_locked(items, old)\n    if problem:", "    problem = ep.refuse_locked(items, old)\n    if False:")]),
    ("a dead job blocks the slot", E, [("            for j in env_jobs(jobs_dir):\n                settle(j, deps, cfg, docker=docker)\n", "")]),
    ("two live requests are allowed", E, [("            if live:\n                raise rj.Refused(f\"package request", "            if False:\n                raise rj.Refused(f\"package request")]),
    ("the day's limit is one more", E, [("if len(today) >= s[\"max_per_day\"]:", "if len(today) > s[\"max_per_day\"]:")]),
    ("the day is not counted", E, [("if len(today) >= s[\"max_per_day\"]:", "if False:")]),
    ("the unadopted limit is one more", E, [("if len(unadopted) >= s[\"max_ready_images\"]:", "if len(unadopted) > s[\"max_ready_images\"]:")]),
    ("an adopted environment still counts as unadopted", E, [("unadopted = [j for j in jobs if j.data.get(\"state\") == READY and j.data.get(\"inputs\", {}).get(\"name\") not in adopted]", "unadopted = [j for j in jobs if j.data.get(\"state\") == READY]")]),
    ("the folders of environments/ are not taken names", E, [("        taken |= {p.name for p in (Path(root) / \"environments\").iterdir() if p.is_dir()}", "        taken |= set()")]),
    ("configured environments are not taken names", E, [("    taken |= set(_environments(cfg))", "    taken |= set()")]),
    ("pins are not taken names", E, [("            taken.add(n)\n    except OSError:", "            pass\n    except OSError:")]),
    ("a pin's suffix stays in the name", E, [("            for suffix in (\".check.json\", \".json\"):", "            for suffix in ():")]),
    ("a live request does not reserve its name", E, [("        if j.data.get(\"state\") in LIVE + (READY,) and", "        if j.data.get(\"state\") in () and")]),
    ("a built request does not reserve its name", E, [("        if j.data.get(\"state\") in LIVE + (READY,) and", "        if j.data.get(\"state\") in LIVE and")]),
    ("an existing job is overwritten", E, [("            if job.file.exists():\n                raise rj.Refused(f\"job {job_id} already exists\")\n            holder", "            holder")]),
    ("the job lock is not held for the run", E, [("            holder.__enter__()                                  # held until the caller's `with` ends", "            holder.__enter__(); holder.__exit__(None, None, None); holder = None")]),
    ("the logged origin is lost", E, [("            job.note(deps, \"created\", via=via)\n", "            job.note(deps, \"created\")\n")]),
    ("the request file carries the wrong cutoff", E, [("t = _epoch(now_text) - days * 86400", "t = _epoch(now_text) - days * 3600")]),
    ("the npmrc is not written", E, [("    (in_dir / \"npmrc\").write_text(NPMRC)\n", "    (in_dir / \"npmrc\").write_text(\"\")\n")]),
    ("the scripts are not the fixed ones", E, [("    (in_dir / \"resolve.js\").write_text(RESOLVE_JS)", "    (in_dir / \"resolve.js\").write_text(RESOLVE_JS + \"\\n\")")]),
    ("--before is dropped from the script", E, [("'--save-exact', '--before=' + req.before, ...common, ...req.specs", "'--save-exact', ...common, ...req.specs")]),
    ("--strict-peer-deps is dropped from the script", E, [("['install', '--package-lock-only', '--strict-peer-deps', '--save-exact'", "['install', '--package-lock-only', '--save-exact'")]),
    ("--ignore-scripts is dropped from the script", E, [("'--no-audit', '--no-fund', '--ignore-scripts'];", "'--no-audit', '--no-fund'];")]),
    ("the script starts a shell", E, [("{ cwd: '/tmp/w', encoding: 'utf8', maxBuffer: 8 * 1024 * 1024 }", "{ cwd: '/tmp/w', encoding: 'utf8', shell: true, maxBuffer: 8 * 1024 * 1024 }")]),
    ("the npmrc names another registry", E, [('NPMRC = "registry=https://registry.npmjs.org/\\n', 'NPMRC = "registry=https://registry.example.org/\\n')]),
    ("npm ls is not run", E, [("  const ls = npm(['ls', '--all', '--package-lock-only', ...common]);", "  const ls = { stdout: '', stderr: '', status: 0 };")]),
    ("a failed install is not a refusal", E, [("    if status.get(\"install_rc\") != 0:\n        return _refuse", "    if False:\n        return _refuse")]),
    ("an ERESOLVE line with a zero exit passes", E, [("    if \"ERESOLVE\" in install_log:", "    if False:")]),
    ("the ls exit code is not read", E, [("    if status.get(\"ls_rc\") != 0 or LS_PROBLEM.search", "    if LS_PROBLEM.search")]),
    ("the ls text is not read", E, [("status.get(\"ls_rc\") != 0 or LS_PROBLEM.search(_read_log(out_dir / \"ls.log\")):", "status.get(\"ls_rc\") != 0:")]),
    ("npm's text is shown", E, [("        return _refuse(job, deps, [_classify(install_log)])", "        return _refuse(job, deps, [install_log[:200]])")]),
    ("ETARGET reads as a missing package", E, [('("ETARGET", "no version of that package is old enough or exists (a version published after the age cutoff is not offered)")', '("ETARGET", "npm found no such package or version")')]),
    ("a container that did not finish is a refusal", E, [("    if rc != 0 or not isinstance(status, dict):\n        job.move(FAILED, deps, reason=\"the resolve container did not finish\")", "    if False:\n        job.move(FAILED, deps, reason=\"the resolve container did not finish\")")]),
    ("a timeout is not a failure", E, [("    except Docker.Timeout:\n        job.move(FAILED, deps, reason=f\"the resolve step took longer", "    except Docker.Timeout:\n        job.move(REFUSED, deps, reason=f\"the resolve step took longer")]),
    ("a missing docker is not a failure", E, [("    except OSError:\n        job.move(FAILED, deps, reason=\"docker could not be started\")\n        return None\n    try:\n        status", "    except KeyError:\n        job.move(FAILED, deps, reason=\"docker could not be started\")\n        return None\n    try:\n        status")]),
    ("the key shape is not checked before the registry step", E, [("all(ep.key_name(k) for k in new[\"packages\"] if k != \"\")", "True")]),
    ("the registry step runs over the limit", E, [("if shape_ok and 0 < len(wanted) <= lim[\"max_new\"]:", "if shape_ok and 0 < len(wanted):")]),
    ("the second step has the whole budget", E, [("        return max(1, int(s[\"resolve_timeout_s\"] - (time.monotonic() - t0)))", "        return max(1, int(s[\"resolve_timeout_s\"]))")]),
    ("the views container name is the first one's", E, [("container_name(job.id, \"-v\"))\n        except Docker.Timeout:\n            job.move(FAILED, deps, reason=f\"the registry step", "container_name(job.id))\n        except Docker.Timeout:\n            job.move(FAILED, deps, reason=f\"the registry step")]),
    ("a views container that did not finish is accepted", E, [("        if rc != 0 or not isinstance(got, dict):\n            job.move(FAILED, deps, reason=\"the registry container did not finish\")", "        if False:\n            job.move(FAILED, deps, reason=\"the registry container did not finish\")")]),
    ("a failed npm view is a record", E, [("ep.parse_view(r.get(\"out\")) if isinstance(r, dict) and r.get(\"rc\") == 0 else None", "ep.parse_view(r.get(\"out\")) if isinstance(r, dict) else None")]),
    ("the candidate sha is of the parsed lock", E, [("\"lock_sha256\": ep.lock_sha(raw)", "\"lock_sha256\": ep.lock_sha(json.dumps(new))")]),
    ("the candidate lock is not kept", E, [("    (cand / \"package-lock.json\").write_bytes(raw)\n", "")]),
    ("a refused report is not kept", E, [("    job.data[\"report\"] = report or {\"status\": \"REFUSED\"", "    job.data[\"x\"] = report or {\"status\": \"REFUSED\"")]),
    ("a refused report waits for the human", E, [("    if report[\"status\"] == \"REFUSED\":\n        job.move(REFUSED, deps, reason=\"a gate refused the request\")\n    else:\n        job.move(AWAITING_HUMAN, deps)", "    job.move(AWAITING_HUMAN, deps)")]),
    ("resolve runs on any job", E, [("    if d.get(\"kind\") != KIND or d.get(\"state\") != NEW:", "    if False:")]),
    ("abandon does not need the chat", E, [("    if via != \"ui\":\n        raise rj.Refused(\"a package request is ended from the chat", "    if False:\n        raise rj.Refused(\"a package request is ended from the chat")]),
    ("abandon takes any kind", E, [("        if job.data.get(\"kind\") != KIND:\n            raise rj.Refused(f\"job {job_id} is not a package request\")", "        if False:\n            raise rj.Refused(f\"job {job_id} is not a package request\")")]),
    ("abandon takes a job not made through the chat", E, [("        if not _created_via_ui(job):\n            raise rj.Refused(f\"job {job_id} was not started from the chat", "        if False:\n            raise rj.Refused(f\"job {job_id} was not started from the chat")]),
    ("abandon takes a building job", E, [("        if job.data[\"state\"] not in (NEW, RESOLVING, AWAITING_HUMAN):", "        if job.data[\"state\"] not in (NEW, RESOLVING, AWAITING_HUMAN, BUILDING):")]),
    ("abandon leaves the containers", E, [("    _remove_containers(job_id, docker or Docker())\n    return job", "    return job")]),
    ("the container runs with a network none", E, [("\"--log-driver\", \"none\",", "\"--log-driver\", \"none\", \"--network\", \"none\",")]),
    ("the container name has no part", E, [("def container_name(job_id, part=\"\"):\n    return f\"argus-env-{job_id}{part}\"", "def container_name(job_id, part=\"\"):\n    return f\"argus-env-{job_id}\"")]),
    ("a container runs a shell", E, [("\"--entrypoint\", \"node\", base, f\"/in/{script}\"]", "\"--entrypoint\", \"sh\", base, f\"/in/{script}\"]")]),
    ("the env table is the code job's", J, [("        elif self.data.get(\"kind\") == \"env\":            # SPEC_CHAT_PACKAGES: a request for new npm packages (router/env_job.py)\n            from router.env_job import LEGAL as legal\n", "")]),
    ("an env job is resumed as a code job", J, [("        if job.data.get(\"kind\") == \"env\":\n            raise Refused(f\"job {job.id}: a package request is not resumed", "        if False:\n            raise Refused(f\"job {job.id}: a package request is not resumed")]),
    ("an env job's status is a code job's", J, [("    if d.get(\"kind\") == \"env\":\n        from router import env_job\n", "    if False:\n        from router import env_job\n")]),
    ("an env job is published to the viewer", S, [("                return None                                # SPEC_CHAT_PACKAGES: a package request is never published, and is no exclusion that counts\n", "                pass\n")]),
    ("project_job accepts an env job", S, [("    if raw.get(\"kind\") == \"env\":\n        raise Excluded(", "    if False:\n        raise Excluded(")]),
    ("status does not settle an env job", A, [("                    ej.settle(j, deps, cfg)", "                    pass")]),
    ("add does not need --yes", A, [("    ea.add_argument(\"--yes\", action=\"store_true\", required=True, help=\"the request was confirmed in chat\")", "    ea.add_argument(\"--yes\", action=\"store_true\", help=\"the request was confirmed in chat\")")]),
    ("add takes any --via", A, [("    ea.add_argument(\"--via\", choices=rj.VIA, required=True)", "    ea.add_argument(\"--via\", required=True)")]),
    ("the packages file has no size limit", A, [("                    if len(raw) > ej.PACKAGES_FILE_MAX:", "                    if False:")]),
    ("a refusal exits zero", A, [("                print(f\"refused: {e}\", file=sys.stderr)\n                return 2\n        if o.cmd == \"env\":", "                print(f\"refused: {e}\", file=sys.stderr)\n                return 0\n        if o.cmd == \"env\":")]),
]
M += [(f"the argv loses {name}", E, [(frag, "")]) for name, frag in FLAGS]
killed = ran = 0
for name, f, edits in M:
    if ONLY and not any(o in name for o in ONLY):
        continue
    ran += 1
    p = WT / f
    orig = p.read_text()
    text = orig
    if any(text.count(a) != 1 for a, _ in edits):
        print("STALE  ", name, flush=True)
        continue
    for a, b in edits:
        text = text.replace(a, b, 1)
    p.write_text(text)
    try:
        r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *T], cwd=WT, capture_output=True, text=True, timeout=900,
                           env={**__import__("os").environ, "PYTHONPATH": f"{WT}:{WT}/scripts:{WT}/tests"})
    finally:
        p.write_text(orig)
    last = (r.stdout.strip().splitlines() or [""])[-1]
    k = "FAILED tests/" in r.stdout or "FAILED" in last or "error" in last.lower()
    killed += k
    print("KILLED " if k else "SURVIVED", name, flush=True)
print(f"RESULT: {killed}/{ran} killed")
