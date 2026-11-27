"""Mutants for SPEC_CHAT_PACKAGES S3 (the build in router/env_job.py, the lock hash in router/job.py check_problem, scripts/build_env_node.sh, `argus env build`). Applied alone;
killed = a test FAILED. Equivalent in behaviour (documented, not mutated further): "the sha may be shorter", "the sha may be upper case", "the sha may be matched, not fully matched" (the compare with the
candidate's own first 12 hex refuses every one of them anyway; the shape check only gives a clearer sentence).
Run in a throwaway worktree. Usage: <this> <worktree> <python> [name-part ...]"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
ONLY = sys.argv[3:]
E, J, B, A = "router/env_job.py", "router/job.py", "scripts/build_env_node.sh", "scripts/argus.py"
T = ["-rfEs", "tests/test_env_build.py", "tests/test_env_job.py", "tests/test_env_cli.py"]
M = [
    ("the chat is not required to build", E, [('    if via != "ui":\n        raise rj.Refused("a package build is started from the chat', '    if False:\n        raise rj.Refused("a package build is started from the chat')]),
    ("the sha may be shorter", E, [('SHA12 = re.compile(r"[0-9a-f]{12}")', 'SHA12 = re.compile(r"[0-9a-f]{1,12}")')]),
    ("the sha may be upper case", E, [('SHA12 = re.compile(r"[0-9a-f]{12}")', 'SHA12 = re.compile(r"[0-9a-fA-F]{12}")')]),
    ("the sha may be matched, not fully matched", E, [("if not isinstance(sha, str) or not SHA12.fullmatch(sha):", "if not isinstance(sha, str) or not SHA12.match(sha):")]),
    ("an old report is not settled first", E, [("    if job.data.get(\"kind\") == KIND:\n        settle(job, deps, cfg, docker=docker, builder=builder)\n", "")]),
    ("any kind of job is built", E, [("        if d.get(\"kind\") != KIND:\n            raise rj.Refused(f\"job {job_id} is not a package request; nothing was changed\")", "        if False:\n            raise rj.Refused(f\"job {job_id} is not a package request; nothing was changed\")")]),
    ("a job made another way is built", E, [("        if not _created_via_ui(job):\n            raise rj.Refused(f\"job {job_id} was not started from the chat; nothing was changed\")\n        if d[\"state\"] != AWAITING_HUMAN:", "        if d[\"state\"] != AWAITING_HUMAN:")]),
    ("a job in any state is built", E, [("        if d[\"state\"] != AWAITING_HUMAN:\n            raise rj.Refused(f\"job {job_id} is {d['state']}, not AWAITING_HUMAN", "        if False:\n            raise rj.Refused(f\"job {job_id} is {d['state']}, not AWAITING_HUMAN")]),
    ("a refused report is built", E, [("if not isinstance(report, dict) or report.get(\"status\") != \"OK\" or not isinstance(cand, dict):", "if not isinstance(report, dict) or not isinstance(cand, dict):")]),
    ("a job without a recorded hash is built", E, [("        if not (isinstance(want, str) and SHA64.fullmatch(want) and isinstance(want_pkg, str) and SHA64.fullmatch(want_pkg)):", "        if False:")]),
    ("another sha is accepted", E, [("        if want[:12] != sha:", "        if False:")]),
    ("a changed lock is accepted", E, [("        if ep.lock_sha(lock_raw) != want or ep.lock_sha(pkg_raw) != want_pkg:", "        if ep.lock_sha(pkg_raw) != want_pkg:")]),
    ("a changed package.json is accepted", E, [("        if ep.lock_sha(lock_raw) != want or ep.lock_sha(pkg_raw) != want_pkg:", "        if ep.lock_sha(lock_raw) != want:")]),
    ("the candidate is not re-hashed", E, [("        if ep.lock_sha(lock_raw) != want or ep.lock_sha(pkg_raw) != want_pkg:", "        if False:")]),
    ("the free space is not checked", E, [("        if builder.free_bytes() < DISK_MIN_BYTES:", "        if False:")]),
    ("exactly three gigabytes is too little", E, [("        if builder.free_bytes() < DISK_MIN_BYTES:", "        if builder.free_bytes() <= DISK_MIN_BYTES:")]),
    ("the minimum is two gigabytes", E, [("DISK_MIN_BYTES = 3 * 1024 ** 3", "DISK_MIN_BYTES = 2 * 1024 ** 3")]),
    ("existing pins do not stop the build", E, [("        if any((root / n).exists() or (root / n).is_symlink() for n in pin_names(name)):", "        if False:")]),
    ("a linked pin does not stop the build", E, [("(root / n).exists() or (root / n).is_symlink() for n in pin_names(name)", "(root / n).exists() for n in pin_names(name)")]),
    ("the staged package.json is the environment's", E, [("        (defs / \"package.json\").write_bytes(pkg_raw)", "        (defs / \"package.json\").write_bytes(b\"{}\")")]),
    ("the staged lock is not the verified one", E, [("        (defs / \"package-lock.json\").write_bytes(lock_raw)", "        (defs / \"package-lock.json\").write_bytes((job.dir / \"candidate\" / \"package-lock.json\").read_bytes() + b\"\")")]),
    ("the staged base is not the pinned one", E, [("        (defs / \"base\").write_text(inp[\"base_image\"] + \"\\n\")", "        (defs / \"base\").write_text(\"node:22\\n\")")]),
    ("the build budget is another", E, [("s[\"build_timeout_s\"])\n        except Docker.Timeout:\n            return fail(f\"the build took longer", "s[\"resolve_timeout_s\"])\n        except Docker.Timeout:\n            return fail(f\"the build took longer")]),
    ("the builder container has the resolve name", E, [("container_name(job.id, \"-b\"), s[\"build_timeout_s\"])", "container_name(job.id), s[\"build_timeout_s\"])")]),
    ("the check takes the wrong base block", E, [("builder.check(name, work / \"defs\", out, inp[\"base_environment\"], left)", "builder.check(name, work / \"defs\", out, name, left)")]),
    ("the check has no time limit of its own", E, [("        left = max(30, int(s[\"build_timeout_s\"] - (time.monotonic() - t0)))", "        left = 10 ** 6")]),
    ("a timed out build is not a failure", E, [("        except Docker.Timeout:\n            return fail(f\"the build took longer", "        except KeyError:\n            return fail(f\"the build took longer")]),
    ("a build that cannot start is not a failure", E, [("        except OSError:\n            return fail(\"the build could not be started\")", "        except KeyError:\n            return fail(\"the build could not be started\")")]),
    ("the build's exit code is not read", E, [("        if rc != 0 or image is None or not isinstance(meta, dict):", "        if image is None or not isinstance(meta, dict):")]),
    ("a build without a pin is accepted", E, [("        if rc != 0 or image is None or not isinstance(meta, dict):", "        if rc != 0 or not isinstance(meta, dict):")]),
    ("a build without metadata is accepted", E, [("        if rc != 0 or image is None or not isinstance(meta, dict):", "        if rc != 0 or image is None:")]),
    ("another lock in the metadata is accepted", E, [("        if meta.get(\"lock_sha256\") != want or meta.get(\"image\") != image:", "        if meta.get(\"image\") != image:")]),
    ("another image in the metadata is accepted", E, [("        if meta.get(\"lock_sha256\") != want or meta.get(\"image\") != image:", "        if meta.get(\"lock_sha256\") != want:")]),
    ("the check's exit code is not read", E, [("        if rc != 0 or not isinstance(rec, dict) or rec.get(\"result\") != \"pass\"", "        if not isinstance(rec, dict) or rec.get(\"result\") != \"pass\"")]),
    ("a failed check record is accepted", E, [("or rec.get(\"result\") != \"pass\" or rec.get(\"image\") != image", "or rec.get(\"image\") != image")]),
    ("a check of another image is accepted", E, [("or rec.get(\"image\") != image or rec.get(\"environment\") != name:", "or rec.get(\"environment\") != name:")]),
    ("a check of another environment is accepted", E, [("or rec.get(\"image\") != image or rec.get(\"environment\") != name:", "or rec.get(\"image\") != image:")]),
    ("a timed out check is not a failure", E, [("        except Docker.Timeout:\n            return fail(\"the environment check took too long\")", "        except KeyError:\n            return fail(\"the environment check took too long\")")]),
    ("a check that cannot start is not a failure", E, [("        except OSError:\n            return fail(\"the environment check could not be started\")", "        except KeyError:\n            return fail(\"the environment check could not be started\")")]),
    ("a failed build leaves its image", E, [("        def fail(reason):\n            _clean_build(job, builder, docker, root)\n            job.move(FAILED, deps, reason=reason)", "        def fail(reason):\n            job.move(FAILED, deps, reason=reason)")]),
    ("a failed move leaves its image", E, [("            _clean_build(job, builder, docker, root, keep_image_of=None)\n            job.move(FAILED, deps, reason=f\"the pins could not be moved", "            job.move(FAILED, deps, reason=f\"the pins could not be moved")]),
    ("an existing pin's image is removed too", E, [("        if existing != image and image != keep_image_of:", "        if True:")]),
    ("the image is never removed", E, [("    if image is not None:\n        existing = _pin_of(root, name)", "    if False:\n        existing = _pin_of(root, name)")]),
    ("the pins of a failed build stay", E, [("    if isinstance(name, str):\n        for n in pin_names(name):\n            (out / n).unlink(missing_ok=True)", "    if False:\n        pass")]),
    ("the container is not removed", E, [("    if remove_container:\n        try:\n            docker.remove(container_name(job.id, \"-b\"))", "    if False:\n        try:\n            docker.remove(container_name(job.id, \"-b\"))")]),
    ("a settled building job removes the container twice", E, [("_clean_build(job, builder or Builder(), docker, rj.ROOT, remove_container=False)", "_clean_build(job, builder or Builder(), docker, rj.ROOT)")]),
    ("a settled building job keeps its image", E, [("                    if was_building:\n                        _clean_build", "                    if False:\n                        _clean_build")]),
    ("the pins are renamed over the checkout's", E, [("                os.link(out / n, root / n)", "                os.replace(out / n, root / n)")]),
    ("the pins move in the other order", E, [("    names = pin_names(name)\n    linked = []", "    names = list(reversed(pin_names(name)))\n    linked = []")]),
    ("the record is not last in the table", E, [('PIN_SUFFIXES = ("", ".json", ".check.json")', 'PIN_SUFFIXES = (".check.json", "", ".json")')]),
    ("what was linked is not undone", E, [("        for n in linked:\n            (root / n).unlink(missing_ok=True)\n        raise", "        raise")]),
    ("a missing source is not a refusal", E, [("            if not (out / n).is_file():\n                raise PinsExist", "            if False:\n                raise PinsExist")]),
    ("an existing pin is not a refusal", E, [("            except FileExistsError:\n                raise PinsExist", "            except KeyError:\n                raise PinsExist")]),
    ("another link error is not a refusal", E, [("            except OSError as e:\n                raise PinsExist(f\"{n} could not be linked", "            except KeyError as e:\n                raise PinsExist(f\"{n} could not be linked")]),
    ("the sources stay after the move", E, [("    for n in names:\n        (out / n).unlink(missing_ok=True)\n\n\nclass Builder", "    for n in []:\n        (out / n).unlink(missing_ok=True)\n\n\nclass Builder")]),
    ("the process group is not killed", E, [("                os.killpg(p.pid, signal.SIGKILL)", "                p.kill()")]),
    ("the child is not in its own group", E, [("text=True, start_new_session=True, cwd=str(self.root))", "text=True, cwd=str(self.root))")]),
    ("a timed out container is not removed", E, [("            if container:\n                Docker().remove(container)", "            if False:\n                Docker().remove(container)")]),
    ("the free space is the larger one", E, [("        return min(sizes) if sizes else 0", "        return max(sizes) if sizes else 0")]),
    ("the free space ignores docker's root", E, [("            if r.returncode == 0 and r.stdout.strip():\n                paths.append(r.stdout.strip())", "            pass")]),
    ("the free space of no path is plenty", E, [("        return min(sizes) if sizes else 0", "        return min(sizes) if sizes else 10 ** 12")]),
    ("the build gets no container name", E, [('"ARGUS_ENV_CONTAINER": container}', '"ARGUS_ENV_CONTAINER": ""}')]),
    ("the build runs on the checkout's definitions", E, [('"ARGUS_ENV_DEFS": str(defs), "ARGUS_ENV_OUT": str(out)', '"ARGUS_ENV_DEFS": "environments", "ARGUS_ENV_OUT": str(out)')]),
    ("the build writes into the checkout", E, [('"ARGUS_ENV_DEFS": str(defs), "ARGUS_ENV_OUT": str(out)', '"ARGUS_ENV_DEFS": str(defs), "ARGUS_ENV_OUT": str(self.root)')]),
    ("the check runs without the staged folders", E, [(', "--defs", str(defs), "--out", str(out), "--like", like]', ', "--like", like]')]),
    ("the adoption bundle names the base environment", E, [('        f"    {name}:",', '        f"    {base}:",')]),
    ("the adoption bundle lists every package as direct", E, [('for p in (report.get("packages") or []) if p.get("direct")]', 'for p in (report.get("packages") or [])]')]),
    ("the adoption bundle holds the wrong lock hash", E, [("must be   {built['lock_sha256']}", "must be   {job.data['candidate']['package_sha256']}")]),
    ("the built record has no node version", E, [('"node": meta.get("node") if isinstance(meta.get("node"), str) else None,', '"node": None,')]),
    ("the job is not saved as READY with its record", E, [('        d["built"] = built\n        job.save()\n        job.move(READY, deps)', '        job.move(READY, deps)')]),
    ("the bundle's files are the environment's", E, [("            shutil.copyfile(defs / f, adoption / f)", "            shutil.copyfile(root / 'environments' / inp['base_environment'] / f, adoption / f)")]),
    ("the lock hash of a Node environment is not compared", J, [("        if have != want:\n            return f\"sandbox environment {name!r}: environments/{name}/package-lock.json is not the lock", "        if False:\n            return f\"sandbox environment {name!r}: environments/{name}/package-lock.json is not the lock")]),
    ("a different lock passes and the same fails", J, [("        if have != want:\n            return f\"sandbox environment", "        if have == want:\n            return f\"sandbox environment")]),
    ("missing metadata is not a problem", J, [("            return f\"sandbox environment {name!r} has no readable build metadata", "            return None  # f\"sandbox environment {name!r} has no readable build metadata")]),
    ("a metadata without a lock hash passes", J, [("        if not isinstance(want, str) or not re.fullmatch(r\"[0-9a-f]{64}\", want):\n            return", "        if False:\n            return")]),
    ("an upper case lock hash passes", J, [("re.fullmatch(r\"[0-9a-f]{64}\", want)", "re.fullmatch(r\"[0-9a-fA-F]{64}\", want)")]),
    ("metadata of another image passes", J, [("        if meta.get(\"image\") != image:\n            return f\"sandbox environment {name!r}: the build metadata is of image", "        if False:\n            return f\"sandbox environment {name!r}: the build metadata is of image")]),
    ("a Python environment needs a lock hash", J, [("    if lock.is_file():                       # SPEC_CHAT_PACKAGES S3", "    if True:                       # SPEC_CHAT_PACKAGES S3")]),
    ("the build script ignores the container name", B, [('[ -z "${ARGUS_ENV_CONTAINER:-}" ] || NAME_ARGS=(--name "$ARGUS_ENV_CONTAINER")', 'true')]),
    ("the build script always names a container", B, [('[ -z "${ARGUS_ENV_CONTAINER:-}" ] || NAME_ARGS=(--name "$ARGUS_ENV_CONTAINER")', 'NAME_ARGS=(--name "${ARGUS_ENV_CONTAINER:-argus-env}")')]),
    ("the build script does not pass the name to docker", B, [('docker run --rm ${NAME_ARGS[@]+"${NAME_ARGS[@]}"} --user', 'docker run --rm --user')]),
    ("build needs no --sha", A, [('    ec.add_argument("--sha", required=True,', '    ec.add_argument("--sha",')]),
    ("build needs no --yes", A, [('    ec.add_argument("--yes", action="store_true", required=True, help="the build was confirmed in chat")', '    ec.add_argument("--yes", action="store_true", help="the build was confirmed in chat")')]),
    ("build takes any --via", A, [('    ec.add_argument("--via", choices=rj.VIA, required=True)', '    ec.add_argument("--via", required=True)')]),
    ("a failed build exits zero", A, [('                    return 0 if rj.open_job(o.job, o.jobs_dir).data["state"] == ej.READY else 1', '                    return 0')]),
]
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
