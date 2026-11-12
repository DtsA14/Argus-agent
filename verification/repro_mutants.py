"""Mutants for SPEC_REPRO_V0 R1 (acceptance/repro.py, router/job.py): each applied alone in a worktree, the named tests run
with -x; killed = a test failed (an error or a skip is not a kill). Usage: repro_mutants.py <worktree> <python>"""
import subprocess
import sys
from pathlib import Path

WT, PY = Path(sys.argv[1]), sys.argv[2]
R, J, T = "acceptance/repro.py", "router/job.py", "tests/test_repro.py"
M = [
    ("blocks: five instead of three", R, "MAX_BLOCKS = 3", "MAX_BLOCKS = 5", [T]),
    ("blocks: no limit applied", R, "enumerate(FENCE.finditer(issue))][:MAX_BLOCKS]", "enumerate(FENCE.finditer(issue))]", [T]),
    ("blocks: any language fenced", R, r"\{?\.?(python3?|py)\b", r"\{?\.?(\w+)\b", [T]),
    ("blocks: language must end the line", R, r"\b[^\n]*\n(.*?)^", r"[ \t]*\n(.*?)^", [T]),
    ("blocks: no dedent", R, "textwrap.dedent(m.group(3))", "m.group(3)", [T]),
    ("skip: no size limit", R, "MAX_CODE_BYTES = 4000", "MAX_CODE_BYTES = 10**9", [T]),
    ("skip: >>> allowed", R, 'any(ln.lstrip().startswith(">>>") for ln in lines)', "False", [T]),
    ("skip: bare ... allowed", R, 'any(ln.strip() == "..." for ln in lines)', "False", [T]),
    ("skip: shell prompt allowed", R, 'any(ln.startswith("$ ") for ln in lines)', "False", [T]),
    ("skip: empty block run", R, '    if not lines:\n        return "empty"\n', "", [T]),
    ("key: ignores the issue", R, 'f"{snapshot_sha256}\\n{issue}"', 'f"{snapshot_sha256}\\n"', [T]),
    ("key: ignores the base", R, 'f"{snapshot_sha256}\\n{issue}"', 'f"\\n{issue}"', [T]),
    ("load: key not checked", R, 'rec.get("key") != key(issue, snapshot_sha256) or ', "", [T]),
    ("load: not-run (null) read as a result", R, "or not isinstance(rec.get(\"results\"), list):", "or False:", [T]),
    ("cut: characters instead of bytes", R, '.encode("utf-8")[:limit].decode("utf-8", "ignore")', "[:limit]", [T]),
    ("cut: control characters kept", R, 'CONTROL.sub("?", (text or ""))', '(text or "")', [T]),
    ("cut: a tab becomes a placeholder", R, r"[\x00-\x08\x0b-\x1f\x7f-\x9f]", r"[\x00-\x1f\x7f-\x9f]", [T]),
    ("cut: C1 controls kept", R, r"\x0b-\x1f\x7f-\x9f]", r"\x0b-\x1f\x7f]", [T]),
    ("cut: bidi marks kept", R, r"\u061c\u200b-\u200f\u2028-\u202e\u2060-\u2069\ufeff]", r"\u061c]", [T]),
    ("cut: zero-width marks kept", R, r"\u200b-\u200f\u2028-\u202e", r"\u200e-\u200f\u2028-\u202e", [T]),
    ("line: last output not shown", R, "parts.append(f'ran clean, last output \"{last}\"' if last else \"ran clean\")", 'parts.append("ran clean")', [T]),
    ("line: first output line shown", R, "last = _last_line(r.get(\"stdout\"))[:OUT_SHOWN]", "last = (r.get(\"stdout\") or \"\").splitlines()[0][:OUT_SHOWN] if (r.get(\"stdout\") or \"\").strip() else \"\"", [T]),
    ("line: output not cut", R, "[:OUT_SHOWN]", "", [T]),
    ("out: no output limit", R, "MAX_OUT = 2000", "MAX_OUT = 10**9", [T]),
    ("result: a timeout is a clean run", R, '    if r.get("timed_out"):', "    if False:", [T]),
    ("result: any exit code is ok", R, 'ok = r.get("exit_code") == 0', "ok = True", [T]),
    ("result: error line kept for a clean run", R, '"stderr_last_line": "" if ok else _last_line(r.get("stderr"))',
     '"stderr_last_line": _last_line(r.get("stderr"))', [T]),
    ("run: timeout not set", R, 'cfg = {**(sandbox_cfg or {}), "timeout_s": TIMEOUT_S}', "cfg = {**(sandbox_cfg or {})}", [T]),
    ("run: a longer timeout", R, "TIMEOUT_S = 20", "TIMEOUT_S = 200", [T]),
    ("run: no prelude", R, "runner(PRELUDE + code,", "runner(code,", [T]),
    ("run: runs on the base itself, not a copy", R, "shutil.copytree(base_dir, work, symlinks=True)", "work = Path(base_dir)", [T]),
    ("run: an error is an empty list", R, "    except Exception:  # advisory: no result, never an error into the job\n        return None",
     "    except Exception:\n        return []", [T]),
    ("run: an error escapes", R, "    except Exception:  # advisory: no result, never an error into the job\n        return None",
     "    except ZeroDivisionError:\n        return None", [T]),
    ("run: skipped blocks are run anyway", R, "                if why:\n", "                if False:\n", [T]),
    ("store: not run is not recorded", R, '"results": results}), encoding="utf-8")', '"results": results or []}), encoding="utf-8")', [T]),
    ("store: an error escapes", R, "        Path(path).write_text(json.dumps", "        Path(path).parent.mkdir(exist_ok=False); Path(path).write_text(json.dumps", [T]),
    ("line: no-example case says not run", R, '        return "issue example at base: no runnable example in the issue"',
     '        return "issue example at base: not run"', [T]),
    ("line: clean warning dropped", R, 'if any(r["status"] == "ok" for r in ran) else ""))', 'if False else ""))', [T]),
    ("line: a timeout reads as clean", R, '            parts.append("timed out")', '            parts.append("ran clean")', [T]),
    ("line: error text uncut", R, '(r.get("stderr_last_line") or "an error")[:80]', '(r.get("stderr_last_line") or "an error")', [T]),
    ("job: the step is not run", J, "        _repro(job, cfg, deps)\n", "", [T]),
    ("job: nothing stored", J, '        repro.store(job.dir / REPRO, issue, job.data["intake"]["snapshot_sha256"], found)\n', "", [T]),
    ("job: stored for another issue", J, 'repro.store(job.dir / REPRO, issue, job.data["intake"]["snapshot_sha256"], found)',
     'repro.store(job.dir / REPRO, "x", job.data["intake"]["snapshot_sha256"], found)', [T]),
    ("job: no event noted", J, '        job.note(deps, "repro", blocks=', "        (lambda **k: None)(blocks=", [T]),
    ("job: a failure in the step escapes", J, "        try:\n            repro.store(job.dir / REPRO, job.data[\"inputs\"][\"issue\"]",
     "        raise\n        try:\n            repro.store(job.dir / REPRO, job.data[\"inputs\"][\"issue\"]", [T]),
    ("job: a failure leaves no not-run file", J, 'job.data["inputs"]["issue"], job.data["intake"]["snapshot_sha256"], None)',
     'job.data["inputs"]["issue"], job.data["intake"]["snapshot_sha256"], [])', [T]),
    ("job: sandbox environment not passed", J, '({"environment": name} if name else {})}\n        issue',
     '{}}\n        issue', [T]),
    ("lines: an old job gets a line", J, "        if not (job.dir / REPRO).exists():\n            return []\n", "", [T]),
    ("lines: not checked against the issue", J, 'repro.load(job.dir / REPRO, job.data["inputs"]["issue"],',
     'repro.load(job.dir / REPRO, json.loads((job.dir / REPRO).read_text()) and "x",', [T]),
    ("lines: an error escapes", J, "        return [repro.line(found)]\n    except Exception:\n        return []",
     "        return [repro.line(found)]\n    except ZeroDivisionError:\n        return []", [T]),
    ("approve: the line is missing", J, "                 *leak_lines(job, draft),\n                 *repro_lines(job),\n",
     "                 *leak_lines(job, draft),\n", [T]),
    ("status: the line is missing", J, "                *leak_lines(job, draft),\n                *repro_lines(job),\n",
     "                *leak_lines(job, draft),\n", [T]),
]

if __name__ == "__main__":
    killed = 0
    for name, f, old, new, tests in M:
        p = WT / f
        orig = p.read_text()
        assert orig.count(old) == 1, (name, orig.count(old))
        p.write_text(orig.replace(old, new, 1))
        r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *tests], cwd=WT,
                           capture_output=True, text=True)
        p.write_text(orig)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        k = "failed" in last
        killed += k
        fails = [line for line in r.stdout.splitlines() if line.startswith("FAILED")][:1]
        print(f"{'KILLED ' if k else 'SURVIVED'} {name}: {fails or last}", flush=True)
    print(f"RESULT: {killed}/{len(M)} killed")
