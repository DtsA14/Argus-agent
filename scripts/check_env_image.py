"""Check a sandbox environment built from a Python image before any job may use it
(docs/reviews/SPEC_ENV_FROM_PYTHON_IMAGE.md 2.3). Every check runs through Argus's own sandbox path, as validations do.

  python scripts/check_env_image.py NAME [--log FILE]
  python scripts/check_env_image.py NAME --defs DIR --out DIR --like ENV [--log FILE]

The second form (docs/reviews/SPEC_CHAT_PACKAGES.md, S0) checks an environment that is NOT adopted yet: its definition is DIR/NAME (the
requirements or the lock), its pins are OUT/.sandbox_image_NAME and .json, the check record is written in OUT (never in the
checkout), and its config block is a copy of the configured environment ENV with the image of the pin file. The three options go
together, are refused for a name that is already configured, and an inherited ARGUS_SANDBOX_IMAGE_<NAME> is ignored.

Checks: the isolation of fixtures/repos/pytest_demo (no network, read-only workspace, runs as nobody); the per-node
classification of pytest_demo is the one the `argus` environment gives (Argus's parser was built on pytest 9 output); the
red-by-assertion check (#179) and the harness's collection work under this environment's pytest; no /bin/sh, git or pip in
the image; the Python and pytest versions are the definition's. Only when every check passes it writes
.sandbox_image_NAME.check.json (git-ignored): {environment, image, result: "pass", checked_at, log_sha256}. The router and
the grader refuse an environment defined in environments/ without such a record for exactly the image they resolve.
A vitest environment (runner: vitest, docs/reviews/SPEC_PWA_VIEWER.md E) is checked on fixtures/repos/vitest_demo
instead: the isolation (no network, read-only workspace and /node_modules, nobody); every test classified as expected;
only the requested file runs (vitest's filter matches substrings); the red check tells an assertion from other errors;
no /bin/sh, git or npm; the Node version is the build's and vitest's the lock's.
Exit codes: 0 all checks passed, 1 a check failed (no record), 2 the check could not run.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from acceptance import contract as ct  # noqa: E402
from acceptance import validation as va  # noqa: E402
from tools import sandbox as sb  # noqa: E402

DEMO = ROOT / "fixtures" / "repos" / "pytest_demo"
VITEST_DEMO = ROOT / "fixtures" / "repos" / "vitest_demo"
VITEST_ISOLATION = [f"src/isolation.test.js::{n}" for n in ("no network", "workspace is read-only",
                                                             "node_modules is read-only", "runs as nobody")]
VITEST_EXPECTED = {f"src/demo.test.jsx::{n}": s for n, s in (
    ("adds", "ok"), ("group > nested name", "ok"), ("renders", "ok"), ("fails by assertion", "FAIL"),
    ("fails in code", "FAIL"), ("element not found", "FAIL"), ("message names a path", "FAIL"),
    ("caught with its cause", "FAIL"), ("message with a stack line", "FAIL"),
    ("awaits code that fails", "FAIL"), ("skipped", "skipped"))}
NODE_PROBE = ("const fs = require('node:fs'); console.log('ARGUS-PROBE:' + JSON.stringify({node: process.versions.node, "
              "vitest: JSON.parse(fs.readFileSync('/node_modules/vitest/package.json')).version, "
              "sh: fs.existsSync('/bin/sh'), bash: fs.existsSync('/bin/bash'), git: fs.existsSync('/usr/bin/git'), "
              "npm: fs.existsSync('/usr/local/bin/npm') || fs.existsSync('/usr/local/lib/node_modules/npm')}))")
ISOLATION = ["tests/test_isolation.py::test_no_network", "tests/test_isolation.py::test_workspace_is_read_only",
             "tests/test_isolation.py::test_runs_as_nobody"]
PROBE = ("import importlib.util, json, os, shutil, sys, pytest; print('ARGUS-PROBE:' + json.dumps({'python': "
         "'%d.%d.%d' % sys.version_info[:3], 'pytest': pytest.__version__, 'sh': os.path.exists('/bin/sh'), "
         "'bash': os.path.exists('/bin/bash'), 'git': shutil.which('git'), 'pip': importlib.util.find_spec('pip') "
         "is not None}))")


def record_path(name, root=None):
    return Path(ROOT if root is None else root) / f".sandbox_image_{name}.check.json"      # the default is read at the call, so a test that points ROOT elsewhere cannot write in the checkout


def definition(name, root=None, defs=None):
    """The folder of the environment's definition: DEFS/NAME for a staged one, else ROOT/environments/NAME."""
    return Path(defs) / name if defs is not None else Path(ROOT if root is None else root) / "environments" / name


def pinned(name, root=None, defs=None):
    """{package: version} of the environment's requirements, and its Python version from the build metadata."""
    reqs = {}
    for line in (definition(name, root, defs) / "requirements.txt").read_text().splitlines():
        m = re.match(r"^([A-Za-z0-9._-]+)==(\S+)", line.strip())
        if m:
            reqs[m.group(1).lower()] = m.group(2)
    return reqs


def spec(*targets, must=(), environment, **extra):
    return {"id": "envcheck", "executable": "python", "args": ["-m", "pytest", *targets], "timeout_s": 300,
            "min_tests": 1, "max_skipped": 10, "must_pass": list(must), "environment": environment, **extra}


def checks(name, cfg, workdir, defs=None, out=None):
    """[(check, ok, detail)] for environment `name`, all through the sandbox. workdir: a copy of pytest_demo. defs and out: a staged
    definition folder and the directory of its pins (S0); both None is the checkout's own environment."""
    pins = Path(ROOT if out is None else out)
    out = []
    v = va.run_validation(spec("tests/test_isolation.py", must=ISOLATION, min_tests=3, environment=name), workdir, cfg)
    out.append(("isolation", v["status"] == "pass", v["reason"] or "ok"))
    runs, canary = {}, {}
    for env in ("argus", name):
        s = spec("tests", max_skipped=5, environment=env)
        r, rec = va.pytest_run(s, workdir, {**cfg, "environment": env, "timeout_s": 300})
        runs[env] = va.parse_pytest(r.get("stdout") or "")
        canary[env] = bool(rec) and rec.get("canary") == va.CANARY_WANTED and rec.get("canary_rc") == 1 and not rec.get("canary_error")
    out.append(("canary (harness record)", all(canary.values()), "ok" if all(canary.values()) else f"canary by environment: {canary}"))
    same = runs[name]["tests"] == runs["argus"]["tests"] and runs[name]["consistent"]
    out.append(("classification like argus", bool(same and runs["argus"]["tests"]),
                "same" if same else f"{runs[name]['tests']} vs argus {runs['argus']['tests']}"))
    got, why = va.red_check(["tests/test_demo.py::test_fails", "tests/test_demo.py::test_add"], workdir, cfg,
                            timeout_s=300, environment=name)
    red_ok = bool(got) and got.get("tests/test_demo.py::test_fails", {}).get("assertion") is True \
        and got.get("tests/test_demo.py::test_add", {}).get("outcome") == "passed"
    out.append(("red check", red_ok, why or json.dumps(got, sort_keys=True)[:300]))
    nodes, why = va.collect_nodes("tests/test_demo.py", workdir, cfg, timeout_s=300, environment=name)
    out.append(("collection", bool(nodes) and "tests/test_demo.py::test_add" in nodes, why or f"{len(nodes)} nodes"))
    r = sb.run_command(["python3", "-I", "-B", "-c", PROBE], workdir=workdir,
                       cfg={**cfg, "environment": name, "timeout_s": 60})
    line = next((l for l in (r.get("stdout") or "").splitlines() if l.startswith("ARGUS-PROBE:")), None)
    probe = json.loads(line[len("ARGUS-PROBE:"):]) if line else {}
    want = pinned(name) if defs is None else pinned(name, defs=defs)       # the old call is kept as it was (a test may stub `pinned(name)`)
    content_ok = bool(probe) and not probe["sh"] and not probe["bash"] and probe["git"] is None and not probe["pip"]
    out.append(("no shell, git or pip", content_ok, json.dumps(probe, sort_keys=True)))
    meta_path = pins / f".sandbox_image_{name}.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    ver_ok = bool(probe) and probe["pytest"] == want.get("pytest") and \
        probe["python"].startswith(str(meta.get("python", "?")) + ".")
    out.append(("versions", ver_ok, f"python {probe.get('python')} (built {meta.get('python')}), pytest "
                                    f"{probe.get('pytest')} (pinned {want.get('pytest')})"))
    return out


def vitest_spec(*files, must=(), environment, **extra):
    return {"id": "envcheck", "executable": "vitest", "args": ["run", *files], "timeout_s": 300, "min_tests": 1,
            "max_skipped": 10, "must_pass": list(must), "environment": environment, **extra}


def locked(name, root=None, defs=None):
    """{package: version} of the environment's package-lock.json (top-level packages only)."""
    lock = json.loads((definition(name, root, defs) / "package-lock.json").read_text())
    return {k[len("node_modules/"):]: v.get("version") for k, v in lock.get("packages", {}).items()
            if k.startswith("node_modules/") and "/node_modules/" not in k[len("node_modules/"):]}


def vitest_checks(name, cfg, workdir, defs=None, out=None):
    """[(check, ok, detail)] for a vitest environment, all through the sandbox. workdir: a copy of vitest_demo. defs and out: as for `checks`."""
    pins = Path(ROOT if out is None else out)
    out = []
    v = va.run_validation(vitest_spec("src/isolation.test.js", must=VITEST_ISOLATION, min_tests=4, environment=name),
                          workdir, cfg)
    out.append(("isolation", v["status"] == "pass", v["reason"] or "ok"))
    nonce = va.vitest_nonce()
    r = sb.run_command(va.vitest_argv(nonce, ["src/demo.test.jsx"]), workdir=workdir,
                       cfg={**cfg, "environment": name, "timeout_s": 300})
    parsed = va.parse_vitest(r.get("stdout") or "", nonce, ["src/demo.test.jsx"])
    out.append(("classification", parsed["tests"] == VITEST_EXPECTED and parsed["consistent"],
                "as expected" if parsed["tests"] == VITEST_EXPECTED else json.dumps(parsed["tests"])[:300]))
    v = va.run_validation(vitest_spec("src/sum.test.js", must=["src/sum.test.js::js"], environment=name), workdir, cfg)
    out.append(("only the requested file", v["status"] == "pass" and v["evidence"]["tests_run"] == 1,
                v["reason"] or "ok"))
    nodes = ["src/demo.test.jsx::fails by assertion", "src/demo.test.jsx::element not found"]
    got, why = va.red_check(nodes, workdir, cfg, timeout_s=300, environment=name, runner="vitest")
    red_ok = bool(got) and got.get(nodes[0], {}).get("assertion") is True and \
        got.get(nodes[1], {}).get("assertion") is False
    out.append(("red check", red_ok, why or json.dumps(got, sort_keys=True)[:300]))
    r = sb.run_command(["node", "-e", NODE_PROBE], workdir=workdir, cfg={**cfg, "environment": name, "timeout_s": 60})
    line = next((l for l in (r.get("stdout") or "").splitlines() if l.startswith("ARGUS-PROBE:")), None)
    probe = json.loads(line[len("ARGUS-PROBE:"):]) if line else {}
    out.append(("no shell, git or npm", bool(probe) and not any(probe[k] for k in ("sh", "bash", "git", "npm")),
                json.dumps(probe, sort_keys=True)))
    meta_path = pins / f".sandbox_image_{name}.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    want = locked(name) if defs is None else locked(name, defs=defs)       # the old call is kept as it was (a test stubs `locked(name)`)
    ver_ok = bool(probe) and probe["node"] == meta.get("node") and probe["vitest"] == want.get("vitest")
    out.append(("versions", ver_ok, f"node {probe.get('node')} (built {meta.get('node')}), vitest "
                                    f"{probe.get('vitest')} (locked {want.get('vitest')})"))
    return out


def checker(name, cfg):
    """(demo repository, checks) for the environment's runner."""
    if ct.runner(cfg["environments"][name]) == "vitest":
        return VITEST_DEMO, vitest_checks
    return DEMO, checks


PIN_DIGEST = re.compile(r"(?:[A-Za-z0-9._/-]+@)?sha256:[0-9a-f]{64}")


def staged_pin(out, name):
    """The image of a staged environment: the pin file `.sandbox_image_NAME` of OUT, a regular file holding one digest, else None."""
    path = Path(out) / f".sandbox_image_{name}"
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 512:
            return None
        text = path.read_text().strip()
    except (OSError, UnicodeDecodeError):
        return None
    return text if PIN_DIGEST.fullmatch(text) else None


def staged(o, cfg):
    """(cfg with an overlay, image, defs, out, problem) for the options of S0. The overlay is a copy, for this run only: the block of the
    environment named by --like with the image of the pin file; an inherited ARGUS_SANDBOX_IMAGE_<NAME> is dropped so it cannot win."""
    envs = (cfg or {}).get("environments") or {}
    if not (o.defs and o.out and o.like):
        return None, None, None, None, "--defs, --out and --like go together"
    if not sb.ENV_NAME.match(o.name):
        return None, None, None, None, f"{o.name!r} is not an environment name"
    if o.name in envs:
        return None, None, None, None, f"{o.name!r} is already configured: check it without the options"
    if not isinstance(envs.get(o.like), dict):
        return None, None, None, None, f"--like {o.like!r} is not a configured environment"
    defs, out = Path(o.defs).resolve(), Path(o.out).resolve()
    if not (defs / o.name).is_dir() or not out.is_dir():
        return None, None, None, None, f"no definition in {defs / o.name} or no directory {out}"
    image = staged_pin(out, o.name)
    if image is None:
        return None, None, None, None, f"no pinned image: {out / ('.sandbox_image_' + o.name)} must be a regular file with one sha256 digest"
    os.environ.pop(f"ARGUS_SANDBOX_IMAGE_{o.name.upper()}", None)
    return {**cfg, "environments": {**envs, o.name: {**envs[o.like], "image": image}}}, image, defs, out, None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("name")
    ap.add_argument("--log")
    ap.add_argument("--defs", help="a staged definition folder: DEFS/NAME (S0; with --out and --like)")
    ap.add_argument("--out", help="the directory of the staged environment's pins; the check record is written there (S0)")
    ap.add_argument("--like", help="a configured environment whose block (runner, protected_required) the staged one copies (S0)")
    o = ap.parse_args(argv)
    from approve_draft import sandbox_cfg
    cfg = sandbox_cfg()
    extra, where = {}, ROOT
    if o.defs or o.out or o.like:
        cfg, image, defs, out, problem = staged(o, cfg)
        if problem:
            print(f"cannot check {o.name!r}: {problem}", file=sys.stderr)
            return 2
        extra, where = {"defs": defs, "out": out}, out
    else:
        image, problem = sb.environment_image(cfg, o.name)
        if problem or not image or not (ROOT / "environments" / o.name).is_dir():
            print(f"cannot check {o.name!r}: {problem or 'no image' if not image else 'no definition in environments/'}",
                  file=sys.stderr)
            return 2
    record_path(o.name, where).unlink(missing_ok=True)
    demo, run_checks = checker(o.name, cfg)
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "ws"
        shutil.copytree(demo, ws)
        results = run_checks(o.name, cfg, str(ws), **extra)
    lines = [f"environment {o.name}, image {image}"] + [f"{'PASS' if ok else 'FAIL'} {c}: {d}" for c, ok, d in results]
    ok = all(r[1] for r in results)
    lines.append(f"RESULT: {'PASS' if ok else 'FAIL'}")
    text = "\n".join(lines) + "\n"
    print(text, end="")
    if o.log:
        Path(o.log).write_text(text)
    if ok:
        record_path(o.name, where).write_text(json.dumps({
            "environment": o.name, "image": image, "result": "pass",
            "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "log_sha256": hashlib.sha256(text.encode()).hexdigest()}) + "\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
