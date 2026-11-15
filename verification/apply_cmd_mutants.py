"""Mutants for SPEC_ARGUS_APPLY PR 2 (router/apply.py): each applied alone in a worktree; killed = a test FAILED and pytest reported no error.
Usage: <this> <worktree> <python> [name fragments to run only some]. DOCKER is not needed.
Not listed alone (each layer is redundant with the others, so only the combinations above can be seen): the fsmonitor pin, the gpg pin, --no-gpg-sign, and the global
configuration switched off protect together; --no-verify and the hooksPath pin; DIFF_PINS (no diff configuration reaches the command); `core.fsmonitor=false`.
Also equivalent (Fable): the state guard (the recorder checks it too), `rev-parse --show-toplevel` alone, `no_entries`, and the case variants of the metadata names."""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
ONLY = sys.argv[3:]
T = ["-rfEs", "tests/test_apply_cmd.py"]
A, J = "router/apply.py", "router/job.py"


def off(cond):
    """The condition's line with `if False:` in its place, keeping the indentation."""
    return (cond, cond[: len(cond) - len(cond.lstrip())] + "if False:")


M = [
    ("GIT_* of the caller kept", A, [('env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_") and k != "EMAIL"}', "env = dict(os.environ)")]),
    ("the hooksPath pin removed", A, [('PINS = ("-c", "core.hooksPath=/dev/null", ', "PINS = (")]),
    ("the local configuration allowlist ignored", A, [off("        if bad:")]),
    ("the allowlist accepts everything", A, [('LOCAL_OK = re.compile(r"^(core', 'LOCAL_OK = re.compile(r".*|^(core')]),
    ("no identity check", A, [off("        if identity is None:")]),
    ("the global identity is not read", A, [("env=_env(global_config=True))", "env=_env())")]),
    ("--read-sha not checked", A, [off("    if not (isinstance(read_sha, str) and len(read_sha) >= 12 and sha.startswith(read_sha.lower())):")]),
    ("the recorded and provenance shas not compared", A, [off('    if recorded != sha or (prov.get("patch") or {}).get("sha256") != sha:')]),
    ("only provenance compared (the recorded sha ignored)", A, [('if recorded != sha or (prov.get("patch") or {}).get("sha256") != sha:', 'if (prov.get("patch") or {}).get("sha256") != sha:')]),
    ("a job without a recorded sha accepted", A, [off("    if not recorded:")]),
    ("the protected globs not re-checked", A, [off("    if hit:")]),
    ("an empty patch accepted", A, [off("    if not patch.strip() or not listed:")]),
    ("a repository without its own .git directory accepted", A, [off('    if not (repo / ".git").is_dir():')]),
    ("the Argus checkout accepted", A, [off("    if real == ROOT.resolve():")]),
    ("the top level not compared", A, [off("        if top != real:")]),
    ("a dirty tree accepted", A, [off("        if dirty:")]),
    ("a detached HEAD accepted", A, [off('        if not ref.startswith("refs/heads/"):')]),
    ("a borrowed branch accepted", A, [off("        if len(held) > 1:")]),
    ("a HEAD that is not the base commit accepted", A, [off('        if head != job.data["intake"]["commit"]:')]),
    ("symlinks and submodules accepted", A, [off("        if old in BAD_MODES or new in BAD_MODES:")]),
    ("git metadata paths accepted", A, [off('        if METADATA & set(parts) or path.startswith("/") or ".." in parts:')]),
    (".gitignore refused as metadata", A, [('METADATA = {".git", ".gitattributes", ".gitmodules"}', 'METADATA = {".git", ".gitattributes", ".gitmodules", ".gitignore"}')]),
    ("the file list not compared", A, [off("    if sorted(p for _, _, _, p in entries) != listed:")]),
    ("no entries accepted", A, [off("    if not entries:")]),
    ("the staged change not compared byte for byte", A, [off("    if staged != patch:")]),
    ("a failed apply is not undone", A, [("        undone = _undo(repo, patch)", "        undone = True")]),
    ("apply_started not logged", A, [('    job.note(deps, "apply_started", head_before=head, branch=ref[11:], read_sha=read_sha)\n', "")]),
    ("a recovered commit of another job accepted", A, [('trailers.get("Argus-Job") != job.id or ', "")]),
    ("a recovered commit of another patch accepted", A, [(' or trailers.get("Argus-Patch-Sha256") != sha', "")]),
    ("a recovered commit with another parent accepted", A, [('if parent != started.get("head_before") or ', "if ")]),
    ("as_is not required", A, [("read_sha=read_sha, require_as_is=True, **extra)", "read_sha=read_sha, **extra)")]),
    ("as_is not required by the recorder", J, [("    if require_as_is and as_is is not True:", "    if False:")]),
    ("a failure after the commit is undone as if there was none", A, [off("        if now and now != head:")]),
    ("only git failures are undone (a bad title leaves the patch staged)", A, [("    except Exception as e:                                  # not BaseException", "    except GitFail as e:                                    # not BaseException")]),
    ("a NUL stays in the title", A, [('.decode("utf-8", "replace").replace("\\0", "")', '.decode("utf-8", "replace")')]),
    ("a HEAD that moved is not noticed", A, [off("    if parent != head:")]),
    ("the repository lock is by path, not by real path", A, [("key = hashlib.sha256(os.path.realpath(repo).encode()).hexdigest()[:16]\n    path = Path(jobs_dir)", "key = hashlib.sha256(str(repo).encode()).hexdigest()[:16]\n    path = Path(jobs_dir)")]),
    ("no global isolation and no fsmonitor pin", A, [('        env["GIT_CONFIG_GLOBAL"] = os.devnull', "        pass"), ('"-c", "core.fsmonitor=false", ', "")]),
    ("no global isolation, no gpg pin and no --no-gpg-sign", A, [('        env["GIT_CONFIG_GLOBAL"] = os.devnull', "        pass"), ('"-c", "commit.gpgsign=false", ', ""), ('"--no-verify", "--no-gpg-sign", ', '"--no-verify", ')]),
    ("the repository lock not taken", A, [("        with lock_repo(jobs_dir, repo):\n            return _apply(job, read_sha, deps=deps, note=note)", "        if True:\n            return _apply(job, read_sha, deps=deps, note=note)")]),
    ("the status prints no command", J, [('                  f"  argus apply {job.id} --read-sha {sha[:12]}",\n', "")]),
    ("the CLI does not apply", "scripts/argus.py", [("ra.apply(o.job, o.read_sha, deps=deps, jobs_dir=o.jobs_dir, note=o.note).id", "o.job")]),
]

if __name__ == "__main__":
    killed = ran = 0
    for name, F, edits in M:
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
            r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", "-n", "4", *T], cwd=WT, capture_output=True, text=True, timeout=1800)
        finally:
            p.write_text(orig)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        fails = [line for line in r.stdout.splitlines() if line.startswith("FAILED tests/test_")][:1]
        k = bool(fails) and "error" not in last
        killed += k
        print(f"{'KILLED ' if k else 'ERROR  ' if 'error' in last else 'SURVIVED'} {name}: {fails or last}", flush=True)
    print(f"RESULT: {killed}/{ran} killed")
