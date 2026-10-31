"""Validation commands: structured (executable + args), checked against an allowlist, run in the sandbox without a
shell, and judged from their own output. Never a shell string, never chosen by the agent.

Two shapes are allowed:
  python -m unittest discover [-s DIR] [-t DIR] [-p PATTERN] [-k NAME ...]
      run as  python3 -I -m unittest discover ... -v
  python -m pytest TARGET [TARGET ...] [-k NAME ...]      (M6 W1; TARGET: a relative path or a pytest node id)
      run as  python3 -I -B -m pytest <fixed harness options> TARGET ... ; the harness alone chooses the options
      (no plugins, ini overrides or rootdir from the contract) and pins the rootdir to /workspace, so node ids are
      relative to the workspace root.
  vitest run FILE [FILE ...]      (docs/reviews/SPEC_PWA_VIEWER.md V; FILE: a relative *.test.js|jsx|ts|tsx path)
      run as  node --input-type=module -e VITEST_RECORDER NONCE LIMITS FILE ... : the harness's own script starts vitest
      from /node_modules with exactly these files (`include`, never vitest's substring filter) and its own recorder,
      and prints one JSON record after a fresh nonce. Judged from that record, never from text: trusted only when it
      ran exactly the requested files, every test was recorded once, vitest started, and nothing failed outside a test.
All run with the workspace mounted read-only, so the check cannot change what it checks; unittest and pytest are
judged from the runner's verbose per-test lines and its summary. A pytest run is trusted only when the per-test lines
account for the summary exactly (same count per outcome, every collected test seen); otherwise the result fails closed.
Node ids may contain spaces (parametrize ids often do): a line is the node id, one space, and the status word at the
end (with pytest's reason in parentheses for skips and xfails). A line read wrongly cannot make a run pass: the counts
would no longer match the summary. Required tests (must_pass) are written without spaces.

Limits (stated, not hidden): the result is read from the test runner's own output, and the code under test runs in
the same process. Code that deliberately forges unittest output from inside the process is not detected here; it
is contained by the sandbox, and the protected test files (scope) keep the tests themselves honest.
"""
import hashlib
import json
import os
import re
import secrets

from tools import sandbox as sb

PREFIX = ["-m", "unittest", "discover"]
OPTIONS = {"-s": False, "-t": False, "-p": False, "-k": True}   # option -> may repeat
VALUE = re.compile(r"^[A-Za-z0-9_*?.][A-Za-z0-9_*?./-]{0,199}$")
MAX_ARGS = 16

PYTEST_PREFIX = ["-m", "pytest"]
PYTEST_OPTIONS = {"-k"}
# a relative path, optionally with a node id: dir/test_x.py::Class::test_name[param]. No spaces, no '..'.
PYTEST_TARGET = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_./-]{0,199}(::[A-Za-z_][A-Za-z0-9_]{0,99}){0,3}"
                           r"(\[[A-Za-z0-9_.,=+-]{1,100}\])?$")
PYTEST_NODE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_./-]{0,199}\.py(::[A-Za-z_][A-Za-z0-9_]{0,99}){1,3}"
                         r"(\[[A-Za-z0-9_.,=+-]{1,100}\])?$")
# The harness's own options, never the contract's: no cache, no ini addopts, classic per-test lines, a fixed rootdir.
PYTEST_FIXED = ["-p", "no:cacheprovider", "-o", "addopts=", "-o", "console_output_style=classic",
                "--rootdir", "/workspace", "-v", "--tb=short", "--color=no", "-rN"]

TEST_LINE = re.compile(r"^(\w+) \(([\w.]+)\)(?: (.*))?$")
RAN = re.compile(r"^Ran (\d+) tests? in ")
FINAL = re.compile(r"^(OK|FAILED)(?: \((.*)\))?$")
MAX_NODES = 50                  # failed_nodes kept in the evidence
SKIPPED_NAMED = 10              # skipped nodes named in a reason (SPEC_DRAFTER_SKIPPED_STEPS 2.1); all in the evidence
# Statuses a no_skip rule refuses (W2a-ext): skipped, xfailed, and xpassed (an xfail marker on a test that passed)
NOT_RUN = {"skipped", "expected failure", "unexpected success"}


def kind(spec):
    """"vitest", "pytest" or "unittest", from the command's own executable and prefix (validate_command decides whether
    it is allowed)."""
    if spec.get("executable") == "vitest":
        return "vitest"
    args = spec.get("args")
    return "pytest" if isinstance(args, list) and args[:2] == PYTEST_PREFIX else "unittest"


def _plain(val):
    return ".." not in val.split("/") and not val.startswith("/")


def validate_pytest(rest):
    errors, targets, i = [], 0, 0
    while i < len(rest):
        a = rest[i]
        if a.startswith("-"):
            if a not in PYTEST_OPTIONS:
                errors.append(f"pytest option {a!r} is not allowed (allowed: {sorted(PYTEST_OPTIONS)}; the harness "
                              "sets every other option itself)")
                i += 1
                continue
            if i + 1 >= len(rest):
                errors.append(f"option {a!r} needs a value")
                break
            val = rest[i + 1]
            if not VALUE.match(val) or not _plain(val):
                errors.append(f"value {val!r} for {a} is not a plain name")
            i += 2
            continue
        if not PYTEST_TARGET.match(a) or not _plain(a):
            errors.append(f"pytest target {a!r} is not a plain relative path or node id")
        targets += 1
        i += 1
    if not targets:
        errors.append("a pytest validation must name at least one test path or node id")
    return errors


def validate_vitest(args):
    if not args or args[0] != "run":
        return ["a vitest validation must be ['run', FILE, ...] (the harness runs it once, never in watch mode)"]
    files, errors = args[1:], []
    if not files:
        errors.append("a vitest validation must name at least one test file")
    for f in files:
        if f.startswith("-"):
            errors.append(f"vitest option {f!r} is not allowed (the harness sets every option itself)")
        elif not VITEST_FILE.match(f) or not _plain(f):
            errors.append(f"vitest target {f!r} is not a plain relative test file (*.test.js, .jsx, .ts or .tsx)")
    if len(set(files)) != len(files):
        errors.append("a vitest validation names a test file twice")
    return errors


def validate_command(executable, args):
    """Problems with a validation command, or []."""
    if executable not in ("python", "vitest"):
        return [f"executable {executable!r} is not allowed (allowlist: python, vitest)"]
    if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
        return ["args must be a list of strings"]
    if len(args) > MAX_ARGS:
        return [f"at most {MAX_ARGS} args"]
    if executable == "vitest":
        return validate_vitest(args)
    if args[:2] == PYTEST_PREFIX:
        return validate_pytest(args[2:])
    if args[:3] != PREFIX:
        return [f"args must start with {PREFIX} or {PYTEST_PREFIX}"]
    errors, seen, rest = [], set(), args[3:]
    if len(rest) % 2:
        return ["every option needs exactly one value"]
    for opt, val in zip(rest[::2], rest[1::2]):
        if opt not in OPTIONS:
            errors.append(f"option {opt!r} is not allowed (allowed: {sorted(OPTIONS)})")
            continue
        if opt in seen and not OPTIONS[opt]:
            errors.append(f"option {opt!r} given twice")
        seen.add(opt)
        if not VALUE.match(val) or ".." in val.split("/"):
            errors.append(f"value {val!r} for {opt} is not a plain relative name")
    return errors


def argv(spec, nonce=None):
    """The exact argv run in the container (no shell). Verbose output is always on: it names each test. A vitest
    command needs the run's nonce; without one (evidence) the recorder and the nonce are shown by name only."""
    errors = validate_command(spec["executable"], spec["args"])
    if errors:
        raise ValueError("; ".join(errors))
    if kind(spec) == "vitest":
        a = vitest_argv(nonce or "<nonce>", spec["args"][1:])
        return a if nonce else [*a[:3], f"<harness vitest recorder sha256:{RECORDER_SHA}>", *a[4:]]
    if kind(spec) == "pytest":
        return ["python3", "-I", "-B", *PYTEST_PREFIX, *PYTEST_FIXED, *spec["args"][2:]]
    return ["python3", "-I", *spec["args"], "-v"]


def parse_unittest(text):
    """Per-test statuses and the summary from unittest's verbose output. Missing pieces stay None."""
    tests, pending = {}, None
    ran = outcome = None
    counts = {}
    rank = {"ERROR": 2, "FAIL": 1}

    def record(tid, status):
        # a failing or erroring subTest outranks the test's own (empty or passing) status; ERROR outranks FAIL
        old = tests.get(tid)
        if old is not None and rank.get(old, 0) > rank.get(status, 0):
            return
        if old is not None and rank.get(old, 0) == rank.get(status, 0) and not status:
            return
        tests[tid] = status

    for line in text.splitlines():
        m = TEST_LINE.match(line)
        subtest = False
        if not m and line[:1].isspace():
            m2 = TEST_LINE.match(line.strip())
            # an indented subTest line: "(i=1) ... FAIL", "[message] ... FAIL" or "[message] (i=1) ... FAIL"
            if m2 and (m2.group(3) or "").startswith(("(", "[")):
                m, subtest = m2, True
        if m:
            name, tid, rest = m.groups()
            if tid.rsplit(".", 1)[-1] == name:
                if rest and rest.startswith("... "):
                    record(tid, rest[4:].strip())
                    pending = None
                elif subtest and " ... " in rest:
                    record(tid, rest.rsplit(" ... ", 1)[1].strip())     # a subTest line
                    pending = None
                else:
                    pending = tid             # a docstring line comes first, then " ... status"
                continue
        if pending and " ... " in line:
            record(pending, line.rsplit(" ... ", 1)[1].strip())
            pending = None
            continue
        m = RAN.match(line)
        if m:
            ran, outcome, counts = int(m.group(1)), None, {}
            continue
        m = FINAL.match(line)
        if m and ran is not None:
            outcome = m.group(1)
            for part in (m.group(2) or "").split(","):
                if "=" in part:
                    k, v = part.strip().split("=", 1)
                    if v.isdigit():
                        counts[k] = int(v)
        elif line.strip() == "NO TESTS RAN":
            ran, outcome = 0, "NO TESTS RAN"
    return {"tests": tests, "tests_run": ran, "outcome": outcome,
            "skipped": counts.get("skipped", 0), "failures": counts.get("failures", 0),
            "errors": counts.get("errors", 0)}


# pytest's verbose line for one test phase; statuses are mapped to the unittest words the rest of the harness uses
PYTEST_LINE = re.compile(r"^(\S.*?::.*\S) (PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS)(?: \(.*\))?$")
PYTEST_STATUS = {"PASSED": "ok", "FAILED": "FAIL", "ERROR": "ERROR", "SKIPPED": "skipped",
                 "XFAIL": "expected failure", "XPASS": "unexpected success"}
PYTEST_COUNT = {"PASSED": "passed", "FAILED": "failed", "ERROR": "errors", "SKIPPED": "skipped",
                "XFAIL": "xfailed", "XPASS": "xpassed"}
PYTEST_SUMMARY = re.compile(r"^=+ (.+?) in [\d.]+s(?: \([^)]*\))? =+$")
PYTEST_COLLECTED = re.compile(r"^collecting \.\.\. collected (\d+) items?(?: / (\d+) errors?)?"
                              r"(?: / (\d+) deselected)?(?: / (\d+) selected)?$")
PLURAL = {"error": "errors", "warning": "warnings"}


def parse_pytest(text):
    """Per-node statuses and the summary from pytest's verbose output, and whether the per-test lines account for
    the summary exactly: the same count per outcome, and one node per collected, selected test. A test that passed
    and then failed in teardown has two lines; its status is the worse one (ERROR > FAIL > the rest)."""
    tests, lines = {}, {k: 0 for k in PYTEST_COUNT.values()}
    rank = {"ERROR": 2, "FAIL": 1}
    collected = deselected = summary = None
    for line in text.splitlines():
        m = PYTEST_LINE.match(line)
        if m:
            node, word = m.groups()
            lines[PYTEST_COUNT[word]] += 1
            status = PYTEST_STATUS[word]
            if node not in tests or rank.get(status, 0) > rank.get(tests[node], 0):
                tests[node] = status
            continue
        m = PYTEST_COLLECTED.match(line)
        if m:
            collected, deselected = int(m.group(1)), int(m.group(3) or 0)
            continue
        m = PYTEST_SUMMARY.match(line)
        if m:
            summary = {}
            for part in m.group(1).split(", "):
                n, _, word = part.partition(" ")
                if n.isdigit():
                    summary[PLURAL.get(word, word)] = int(n)
                elif part == "no tests ran":
                    summary["no tests ran"] = 1
    counts = {k: (summary or {}).get(k, 0) for k in PYTEST_COUNT.values()}
    consistent = (summary is not None and collected is not None and lines == counts
                  and len(tests) == collected - deselected)
    if summary is None:
        outcome = None
    elif "no tests ran" in summary or not tests:
        outcome = "NO TESTS RAN"
    else:
        outcome = "FAILED" if counts["failed"] or counts["errors"] else "OK"
    return {"tests": tests, "tests_run": None if summary is None else len(tests), "outcome": outcome,
            "skipped": counts["skipped"] + counts["xfailed"] + counts["xpassed"], "failures": counts["failed"],
            "errors": counts["errors"], "consistent": consistent, "collected": collected, "deselected": deselected}


def skip_violations(no_skip, tests):
    """W2a-ext: nodes of a changed test file that ended skipped or xfail and are not allowed (marked so in the
    intake version; an allowed prefix is the file, a class or a function, with its parametrized ids)."""
    allowed = no_skip["allowed"]
    return sorted(n for n, s in tests.items() if s in NOT_RUN and n.split("::", 1)[0] in no_skip["paths"]
                  and not any(n == a or n.startswith((a + "::", a + "[")) for a in allowed))


def criteria_problems(spec, parsed, must, skipped):
    """The contract's own criteria, the same for every runner: at least min_tests ran, at most max_skipped were
    skipped (named), and every required test is ok."""
    problems = []
    if parsed["tests_run"] is not None and parsed["tests_run"] < spec["min_tests"]:
        problems.append(f"{parsed['tests_run']} tests ran, contract requires at least {spec['min_tests']}")
    if parsed["skipped"] > spec["max_skipped"]:
        named = ", ".join(skipped[:SKIPPED_NAMED]) + (f" and {len(skipped) - SKIPPED_NAMED} more"
                                                      if len(skipped) > SKIPPED_NAMED else "")
        problems.append(f"{parsed['skipped']} tests skipped, contract allows {spec['max_skipped']}"
                        + (f": {named}" if named else ""))
    for t, st in must.items():
        if st != "ok":
            problems.append(f"required test {t} {'did not run' if st is None else 'is ' + repr(st)}")
    return problems


def judge_result(spec, r, nonce=None):
    """Criterion verdict for one validation run: ok only when every condition in the contract holds. nonce: the one
    a vitest run was given (its record is read only behind it)."""
    if kind(spec) == "vitest":
        return judge_vitest(spec, r, nonce)
    pytest = kind(spec) == "pytest"
    runner = "pytest" if pytest else "unittest"
    if pytest:
        parsed = parse_pytest(r.get("stdout") or "")           # pytest reports on stdout, unittest on stderr
    else:
        parsed = parse_unittest((r.get("stderr") or "") + "\n" + (r.get("stdout") or ""))
    must = {t: parsed["tests"].get(t) for t in spec.get("must_pass", [])}
    evidence = {"argv": argv(spec), "exit_code": r.get("exit_code"), "timed_out": r.get("timed_out"),
                "killed": r.get("killed"), "cleanup_failed": r.get("cleanup_failed"),
                "output_limit_exceeded": r.get("output_limit_exceeded"), "truncated": r.get("truncated"),
                "tests_run": parsed["tests_run"], "outcome": parsed["outcome"], "skipped": parsed["skipped"],
                "failures": parsed["failures"], "errors": parsed["errors"], "must_pass": must,
                "output_tail": ((r.get("stdout") or "") if pytest else (r.get("stderr") or ""))[-2000:]}
    if pytest and parsed["tests_run"] is None and (r.get("stderr") or "").strip():
        # No pytest summary: the reason (e.g. an ImportError while loading a conftest, pytest exit code 4) is on stderr,
        # which the agent and the drafter otherwise never see (sympy-24562 dev run: two attempts on a broken import)
        evidence["output_tail"] = ((r.get("stdout") or "").rstrip() + "\n--- stderr ---\n" + r["stderr"])[-2000:]
    if pytest:
        # failed_nodes (W2b): every node that failed or errored, required or not, so a check can name the unexpected ones
        evidence.update(runner="pytest", consistent=parsed["consistent"], collected=parsed["collected"],
                        deselected=parsed["deselected"], stderr_tail=(r.get("stderr") or "")[-500:],
                        failed_nodes=sorted(n for n, s in parsed["tests"].items() if s in ("FAIL", "ERROR"))[:MAX_NODES])
        if spec.get("no_skip"):
            evidence["skip_violations"] = skip_violations(spec["no_skip"], parsed["tests"])[:MAX_NODES]
    if spec.get("environment"):
        evidence["environment"] = spec["environment"]
    skipped = sorted(n for n, s in parsed["tests"].items() if s in NOT_RUN)
    if skipped:                     # which ones, so a draft (or the agent) can leave them out without guessing
        evidence["skipped_nodes"] = skipped[:MAX_NODES]
    problems = []
    if r.get("timed_out"):
        problems.append(f"timed out after {spec['timeout_s']}s (container killed"
                        + (", cleanup not confirmed)" if r.get("cleanup_failed") else ")"))
    elif r.get("output_limit_exceeded"):
        problems.append("output limit exceeded (container killed)")
    else:
        if pytest and r.get("truncated"):
            problems.append("output truncated: the per-test results are incomplete")
        if parsed["tests_run"] is None or parsed["outcome"] is None:
            problems.append(f"no {runner} summary in the output")
        elif pytest and not parsed["consistent"]:
            problems.append("pytest output inconsistent: the per-test lines do not account for the summary")
        if r.get("exit_code") != 0:
            problems.append(f"exit code {r.get('exit_code')}")
        if parsed["outcome"] not in (None, "OK"):
            problems.append(f"{runner} outcome {parsed['outcome']}")
        problems += criteria_problems(spec, parsed, must, skipped)
        if evidence.get("skip_violations"):
            problems.append("skipped or xfail in a changed test file, and not marked so before the change: "
                            + ", ".join(evidence["skip_violations"]))
    return {"id": f"validation:{spec['id']}", "layer": "C", "status": "fail" if problems else "pass",
            "reason": "; ".join(problems), "evidence": evidence}


def judge_vitest(spec, r, nonce):
    files = spec["args"][1:]
    parsed = parse_vitest(r.get("stdout") or "", nonce, files) if nonce else parse_vitest("", "-", files)
    must = {t: parsed["tests"].get(t) for t in spec.get("must_pass", [])}
    evidence = {"argv": argv(spec), "exit_code": r.get("exit_code"), "timed_out": r.get("timed_out"),
                "killed": r.get("killed"), "cleanup_failed": r.get("cleanup_failed"),
                "output_limit_exceeded": r.get("output_limit_exceeded"), "truncated": r.get("truncated"),
                "tests_run": parsed["tests_run"], "outcome": parsed["outcome"], "skipped": parsed["skipped"],
                "failures": parsed["failures"], "errors": parsed["errors"], "must_pass": must, "runner": "vitest",
                "consistent": parsed["consistent"], "output_tail": vitest_tail(parsed),
                "stderr_tail": (r.get("stderr") or "")[-500:],
                "failed_nodes": sorted(n for n, s in parsed["tests"].items() if s == "FAIL")[:MAX_NODES]}
    if parsed["record"] is None and (r.get("stderr") or "").strip():
        evidence["output_tail"] = ("no vitest record; stderr:\n" + r["stderr"])[-TAIL:]
    if spec.get("environment"):
        evidence["environment"] = spec["environment"]
    skipped = sorted(n for n, s in parsed["tests"].items() if s == "skipped")
    if skipped:
        evidence["skipped_nodes"] = skipped[:MAX_NODES]
    problems = []
    if r.get("timed_out"):
        problems.append(f"timed out after {spec['timeout_s']}s (container killed"
                        + (", cleanup not confirmed)" if r.get("cleanup_failed") else ")"))
    elif r.get("output_limit_exceeded"):
        problems.append("output limit exceeded (container killed)")
    elif r.get("truncated"):
        problems.append("output truncated: the vitest record is incomplete")
    else:
        problems += parsed["distrust"]
        if r.get("exit_code") != 0:
            problems.append(f"exit code {r.get('exit_code')}")
        if parsed["record"] is not None:
            if parsed["outcome"] != "OK":
                problems.append(f"vitest outcome {parsed['outcome']}")
            problems += criteria_problems(spec, parsed, must, skipped)
    return {"id": f"validation:{spec['id']}", "layer": "C", "status": "fail" if problems else "pass",
            "reason": "; ".join(problems), "evidence": evidence}


COLLECT_SUMMARY = re.compile(r"^(?:\d+ tests? collected|no tests collected)")


def collect_argv(path):
    """The harness's own collection of one test file (W2a-ext K1); never a contract command."""
    return ["python3", "-I", "-B", *PYTEST_PREFIX, "-p", "no:cacheprovider", "-o", "addopts=", "--rootdir", "/workspace",
            "--color=no", "--collect-only", "-q", path]


def collect_nodes(path, workdir, sandbox_cfg, *, timeout_s, environment=None, log=None):
    """({node ids pytest collects from `path`}, None), or (None, why) when the collection did not succeed. Runs in the
    sandbox like a validation (read-only workspace); no sandbox means no collection, never a fallback."""
    cfg = {**(sandbox_cfg or {}), "timeout_s": timeout_s}
    if environment:
        cfg["environment"] = environment
    try:
        r = sb.run_command(collect_argv(path), workdir=workdir, cfg=cfg, log=log, meta={"collect": path})
    except sb.SandboxUnavailable as e:
        return None, f"sandbox unavailable: {e}"
    out = r.get("stdout") or ""
    if r.get("timed_out") or r.get("output_limit_exceeded") or r.get("truncated"):
        return None, "the collection timed out or its output was cut"
    nodes = {line for line in out.splitlines() if line.startswith(path + "::")}
    summary = any(COLLECT_SUMMARY.match(line.strip()) for line in out.splitlines())
    if not summary or r.get("exit_code") not in (0, 5) or (r.get("exit_code") == 5) != (not nodes):
        return None, f"exit code {r.get('exit_code')}: " + out[-500:]
    return nodes, None


# W2a red by assertion (docs/reviews/SPEC_W2A_RED_BY_ASSERTION.md, section 6): a small pytest plugin, run by the harness,
# records per node the outcome, the exception's real type and the path of the last traceback frame inside the
# repository (frames of pytest, the stdlib and site-packages are passed over). No traceback text is parsed. The JSON
# is printed after a nonce line once pytest is done. SPEC_RED_TESTS_PER_NODE 2.1: also the exception's message (cut at
# RED_LIMITS), the exception names other than AssertionError that the test's own words name (read from the whole message,
# before it is cut; not pytest's explanation of a rewritten assert, nor "DID NOT RAISE"), and the repository files (real
# files only) of every frame of it and of its chain (__cause__, __context__ unless suppressed by `from None`; each file
# once, the deepest kept), for the review and the swallowed-traceback gate. pytest prints no traceback,
# short summary or warning summary (only the display: the repository's filterwarnings still apply), so the JSON fits the
# sandbox's output; output that is cut is refused, never read. Like any validation it is read from the process that runs the code
# under test: a deliberate forgery from inside is contained by the sandbox, not detected.
RED_LIMITS = {"message": 500, "paths": 20, "chain": 20, "names": 20}
RED_CHECK = r"""
import json, os, re, sys, traceback
import pytest
nonce, limits, nodes = sys.argv[1], json.loads(sys.argv[2]), sys.argv[3:]
root = os.path.realpath("/workspace")
out = {}
_real = {}


def real(p):
    p = str(p)
    if p not in _real:
        _real[p] = os.path.realpath(p) if os.path.isfile(p) else None   # "<frozen ...>", "<string>": no file
    return _real[p]


def inside(p):
    r = real(p)
    return r is not None and r.startswith(root + os.sep) and "site-packages" not in r.split(os.sep)


def rel(p):
    return os.path.relpath(real(p), root).replace(os.sep, "/")


def text(exc):
    try:
        return str(exc)
    except Exception:
        return "<the message could not be read>"


def message(exc):
    m = text(exc)
    return m if len(m) <= limits["message"] else m[:limits["message"] - 3] + "..."


def own(exc):
    # The test's own words: not pytest's explanation of a rewritten assert (it starts at the first "assert " line),
    # nor pytest.raises' "DID NOT RAISE <class ...>" (nothing was raised, so nothing was kept).
    m = text(exc)
    if isinstance(exc, pytest.fail.Exception) and m.startswith("DID NOT RAISE"):
        return ""
    lines = m.split("\n")
    cut = next((i for i, line in enumerate(lines) if line.startswith("assert ")), len(lines))
    return "\n".join(lines[:cut])


def names(exc):
    found = set(re.findall(r"\b([A-Z]\w*(?:Error|Exception))\b", own(exc))) - {"AssertionError"}
    return sorted(found)[:limits["names"]]


def repo_paths(exc):
    paths, kept, seen = [], set(), set()
    for _ in range(limits["chain"]):
        if exc is None or id(exc) in seen:
            break
        seen.add(id(exc))
        for f in traceback.extract_tb(exc.__traceback__):
            if inside(f.filename):
                r = rel(f.filename)
                if r not in kept:
                    kept.add(r)
                    paths.append(r)
        exc = exc.__cause__ or (None if exc.__suppress_context__ else exc.__context__)
    return paths[-limits["paths"]:]


class Record:
    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item, call):
        rep = (yield).get_result()
        if call.when != "call":
            # an error in setup, or in teardown after a call that did not fail (a failed call keeps its record)
            if rep.failed and (call.when == "setup" or out.get(item.nodeid, {}).get("outcome") != "failed"):
                out[item.nodeid] = {"outcome": "error", "type": None, "assertion": False, "path": None}
            return
        e = call.excinfo
        if e is None:
            out.setdefault(item.nodeid, {"outcome": rep.outcome, "type": None, "assertion": False, "path": None})
            return
        path = next((rel(x.path) for x in reversed(e.traceback) if inside(x.path)), None)
        out[item.nodeid] = {"outcome": rep.outcome, "type": e.type.__module__ + "." + e.type.__qualname__,
                            "assertion": issubclass(e.type, (AssertionError, pytest.fail.Exception)), "path": path,
                            "message": message(e.value), "message_names": names(e.value),
                            "repo_paths": repo_paths(e.value)}


pytest.main(["-p", "no:cacheprovider", "-o", "addopts=", "--rootdir", "/workspace", "-q", "--color=no", "--tb=no",
             "-rN", "--disable-warnings", *nodes], plugins=[Record()])
sys.stdout.write("\n" + nonce + json.dumps(out, sort_keys=True) + "\n")
sys.stdout.flush()
"""


def red_argv(nonce, nodes):
    """The harness's own run of the red check; never a contract command. Its limits go as an argument, so the plugin's
    source is never a format template."""
    return ["python3", "-I", "-B", "-c", RED_CHECK, nonce, json.dumps(RED_LIMITS, sort_keys=True), *nodes]


def red_check(nodes, workdir, sandbox_cfg, *, timeout_s, environment=None, log=None, runner="pytest"):
    """({node id: {outcome, type, assertion, path}}, None) for the given pytest (or vitest) node ids, or (None, why)
    when the run or its JSON could not be read."""
    vitest = runner == "vitest"
    nonce = vitest_nonce() if vitest else "ARGUS-RED-" + secrets.token_hex(16) + ":"
    cfg = {**(sandbox_cfg or {}), "timeout_s": timeout_s}
    if environment:
        cfg["environment"] = environment
    if vitest and vitest_workspace_problems(workdir):
        return None, "; ".join(vitest_workspace_problems(workdir))
    command = vitest_argv(nonce, vitest_files(nodes)) if vitest else red_argv(nonce, nodes)
    try:
        r = sb.run_command(command, workdir=workdir, cfg=cfg, log=log, meta={"red_check": len(nodes)})
    except sb.SandboxUnavailable as e:
        return None, f"sandbox unavailable: {e}"
    if r.get("timed_out") or r.get("output_limit_exceeded") or r.get("truncated"):
        return None, "the run timed out or its output was cut"
    if vitest:
        got, why = red_records(r.get("stdout"), nonce, nodes)
        return (got, None) if got is not None else (None, f"{why} (exit code {r.get('exit_code')})")
    lines = [line[len(nonce):] for line in (r.get("stdout") or "").splitlines() if line.startswith(nonce)]
    try:
        got = json.loads(lines[-1]) if len(lines) == 1 else None
    except ValueError:
        got = None
    if not isinstance(got, dict):
        return None, "no record of the run (exit code " + str(r.get("exit_code")) + ")"
    return got, None


# Vitest (docs/reviews/SPEC_PWA_VIEWER.md V, section 9): one script of the harness, for validations and the red check
# alike. It starts vitest from the environment's read-only /node_modules with exactly the requested files (`include`:
# vitest's own file filter matches substrings), the runner config loader (vite's default writes into node_modules),
# no cache, and a recorder of its own instead of any reporter of the repository. Per test: the state and, for a
# failure, its first error: type, message (cut at RED_LIMITS), the names of other errors it mentions, and the
# repository files of its stack frames and of its `cause` chain (frame lines only, read after the message, which the
# code under test chooses; files under node_modules passed over), the deepest first, so `path` is where the error
# itself was raised, like the pytest plugin's last repository frame, and `frames` (path:line) show the agent the way. Per module: the errors that
# kept it from loading. `count` is every test seen, so two tests with one full name cannot hide each other. Printed
# once, after the nonce; the process always exits 0, the record says what happened. Like any validation it is read
# from the process that runs the code under test: a deliberate forgery from inside is contained by the sandbox, not
# detected.
VITEST_FILE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_./-]{0,199}\.test\.(?:js|jsx|ts|tsx)$")
#: A file vitest's default `include` takes for a test (`**/*.{test,spec}.?(c|m)[jt]s?(x)`) and the directories its
#: default `exclude` leaves out; a test-like file VITEST_FILE does not match cannot be named in a validation
#: (SPEC_VITEST_FULL_REGRESSION F1b).
VITEST_LIKE = re.compile(r"\.(?:test|spec)\.(?:c|m)?[jt]sx?$")
VITEST_EXCLUDED_DIRS = frozenset({"node_modules", "dist", "cypress", ".idea", ".git", ".cache", ".output", ".temp"})
VITEST_NODE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_./-]{0,199}\.test\.(?:js|jsx|ts|tsx)::[^\x00-\x1f\x7f]{1,300}$")
VITEST_STATUS = {"passed": "ok", "failed": "FAIL", "skipped": "skipped", "pending": "skipped"}
RED_OUTCOME = {"ok": "passed", "FAIL": "failed", "skipped": "skipped"}      # the pytest red check's words
VITEST_RECORDER = r"""
process.env.HOME = '/tmp'
process.env.NO_COLOR = '1'
const [nonce, limitsText, ...files] = process.argv.slice(1)
const limits = JSON.parse(limitsText)
const root = '/workspace/'
const out = { tests: {}, modules: {}, count: 0, unhandled: [], fatal: null }
const cut = (s, n) => { s = String(s); return s.length <= n ? s : s.slice(0, n - 3) + '...' }
const rel = p => String(p).startsWith(root) ? String(p).slice(root.length) : String(p)
const frames = e => {
  // the stack's frames only: its first lines repeat the message, which the code under test chooses
  let stack = String(e.stack || '')
  const msg = String(e.message || ''), at = msg ? stack.indexOf(msg) : -1
  stack = at < 0 ? stack : stack.slice(at + msg.length)
  const got = []
  for (const line of stack.split('\n')) {
    const m = line.match(/^ {4}at (?:.* \()?\/workspace\/([^\s():]+):(\d+):\d+\)?$/)
    if (m && !m[1].split('/').includes('node_modules')) got.push([m[1], m[2]])
  }
  return got
}
const chain = e => {
  const out = [], seen = new Set()
  for (let x = e; x && typeof x === 'object' && !seen.has(x) && out.length < limits.chain; x = x.cause) {
    seen.add(x)
    out.push(x)
  }
  return out
}
const names = msg => [...new Set(String(msg).match(/\b[A-Z]\w*(?:Error|Exception)\b/g) || [])]
  .filter(n => n !== 'AssertionError').sort().slice(0, limits.names)
const none = { type: null, message: null, message_names: [], path: null, where: null, repo_paths: [], frames: [] }
const record = e => {
  const f = frames(e), all = chain(e).flatMap(frames), paths = [], at = []
  for (const [p, n] of all) {
    if (!paths.includes(p)) paths.push(p)
    if (!at.includes(p + ':' + n)) at.push(p + ':' + n)
  }
  return { type: cut(e.name || 'Error', 100), message: cut(e.message, limits.message), message_names: names(e.message),
           path: f.length ? f[0][0] : null, where: f.length ? f[0][0] + ':' + f[0][1] : null,
           repo_paths: paths.slice(0, limits.paths), frames: at.slice(0, limits.paths) }
}
const recorder = {
  onTestRunEnd(modules, unhandled) {
    for (const m of modules) {
      const id = rel(m.moduleId)
      out.modules[id] = { errors: m.errors().map(e => ({ name: cut(e.name || 'Error', 100),
                                                         message: cut(e.message, limits.message) })) }
      for (const t of m.children.allTests()) {
        const r = t.result(), e = (r.errors || [])[0]
        out.count += 1
        out.tests[id + '::' + t.fullName] = { state: r.state, ...(e ? record(e) : none) }
      }
    }
    out.unhandled = unhandled.map(e => cut((e.name || 'Error') + ': ' + e.message, limits.message))
  },
}
try {
  const { startVitest } = await import('/node_modules/vitest/dist/node.js')
  const ctx = await startVitest('test', [], { run: true, watch: false, root: '/workspace', include: files,
                                              reporters: [recorder], configLoader: 'runner', cache: false },
                                { cacheDir: '/tmp/vite-cache', logLevel: 'silent' })
  await ctx?.close()
} catch (e) {
  out.fatal = cut((e && e.message) || e, limits.message)
}
process.stdout.write('\n' + nonce + JSON.stringify(out) + '\n')
process.exit(0)
"""
RECORDER_SHA = hashlib.sha256(VITEST_RECORDER.encode("utf-8")).hexdigest()[:16]
TAIL = 2000


def vitest_argv(nonce, files):
    """The harness's own vitest run; never a contract command. Its limits go as an argument (no format template)."""
    return ["node", "--input-type=module", "-e", VITEST_RECORDER, nonce, json.dumps(RED_LIMITS, sort_keys=True), *files]


def vitest_nonce():
    return "ARGUS-VITEST-" + secrets.token_hex(16) + ":"


def vitest_record(stdout, nonce):
    """The recorder's JSON: exactly one line after the nonce, of the expected shape; otherwise None."""
    lines = [line[len(nonce):] for line in (stdout or "").splitlines() if line.startswith(nonce)]
    if len(lines) != 1:
        return None
    try:
        got = json.loads(lines[0])
    except ValueError:
        return None
    if not (isinstance(got, dict) and isinstance(got.get("tests"), dict) and isinstance(got.get("modules"), dict)
            and all(isinstance(v, dict) and v.get("state") in VITEST_STATUS for v in got["tests"].values())
            and all(isinstance(v, dict) and isinstance(v.get("errors"), list) for v in got["modules"].values())
            and isinstance(got.get("unhandled"), list)):
        return None
    return got


def parse_vitest(stdout, nonce, files):
    """Per-node statuses (pytest's words: ok, FAIL, skipped) and the counts, from the recorder's record, and why it
    cannot be trusted (`distrust`, empty when it can)."""
    rec = vitest_record(stdout, nonce)
    if rec is None:
        return {"tests": {}, "tests_run": None, "outcome": None, "skipped": 0, "failures": 0, "errors": 0,
                "consistent": False, "distrust": ["no vitest record in the output"], "record": None}
    tests = {n: VITEST_STATUS[v["state"]] for n, v in rec["tests"].items()}
    load_errors = {m: v["errors"] for m, v in rec["modules"].items() if v["errors"]}
    distrust = []
    if rec.get("fatal"):
        distrust.append(f"vitest could not start: {rec['fatal']}")
    ran = set(rec["modules"])
    strays = sorted(n for n in tests if n.split("::", 1)[0] not in ran)
    if ran != set(files) or strays:
        distrust.append(f"vitest did not run exactly the requested files (asked {sorted(files)}, ran {sorted(ran)}"
                        + (f", tests outside them: {strays[:5]}" if strays else "") + ")")
    if rec.get("count") != len(tests):
        distrust.append(f"vitest record inconsistent: {rec.get('count')} tests seen, {len(tests)} named (two tests "
                        "with the same full name?)")
    if rec["unhandled"]:
        distrust.append("unhandled errors outside the tests: " + "; ".join(map(str, rec["unhandled"][:5])))
    failures = sum(1 for s in tests.values() if s == "FAIL")
    errors = len(load_errors) + len(rec["unhandled"])
    outcome = "NO TESTS RAN" if not tests else "FAILED" if failures or errors else "OK"
    return {"tests": tests, "tests_run": len(tests), "outcome": outcome, "failures": failures, "errors": errors,
            "skipped": sum(1 for s in tests.values() if s == "skipped"), "consistent": not distrust,
            "distrust": distrust, "record": rec, "load_errors": load_errors}


def vitest_tail(parsed):
    """What the agent and the drafter read of a vitest run: each failure with its error and where it was raised, the
    files that did not load, and why the run is not trusted; then the counts."""
    rec, out = parsed["record"] or {}, []
    for n, v in (rec.get("tests") or {}).items():
        if v["state"] == "failed":
            out.append(f"FAIL {n}\n  {v.get('type')}: {v.get('message')}"
                       + "".join(f"\n  at {f}" for f in v.get("frames") or ([v["where"]] if v.get("where") else [])))
    for m, errs in (parsed.get("load_errors") or {}).items():
        out += [f"ERROR {m} (the file did not load)"] + [f"  {e.get('name')}: {e.get('message')}" for e in errs]
    out += parsed["distrust"]
    if parsed["tests_run"] is not None:
        out.append(f"{parsed['tests_run'] - parsed['failures'] - parsed['skipped']} passed, {parsed['failures']} "
                   f"failed, {parsed['skipped']} skipped, {parsed['errors']} errors")
    return "\n".join(out)[-TAIL:]


def red_records(stdout, nonce, nodes):
    """({node: record in the pytest red check's shape} for the requested nodes, None), or (None, why) when there is
    no record or it cannot be trusted (parse_vitest). assertion: the error is an AssertionError (expect and assert);
    anything else is not a red by assertion."""
    parsed = parse_vitest(stdout, nonce, vitest_files(nodes))
    if parsed["distrust"]:
        return None, "; ".join(parsed["distrust"])
    rec = parsed["record"]
    return {n: {"outcome": RED_OUTCOME[VITEST_STATUS[v["state"]]], "type": v.get("type"), "assertion": v.get("type") == "AssertionError",
                "path": v.get("path"), "message": v.get("message"), "message_names": v.get("message_names") or [],
                "repo_paths": v.get("repo_paths") or []}
            for n, v in rec["tests"].items() if n in nodes}, None


def vitest_workspace_problems(workdir):
    """What vitest would load from the workspace besides the repository's own code (SPEC_PWA_VIEWER, review of PR 1): a
    node_modules anywhere, or a package.json or .npmrc below the root, would shadow the environment's packages. Read
    on the host before every vitest run, without following links; any of them refuses the run."""
    found = []
    for here, dirs, files in os.walk(workdir):
        rel = os.path.relpath(here, workdir)
        for d in dirs:
            if d == "node_modules":
                found.append(os.path.normpath(os.path.join(rel, d)))
        if rel != ".":
            found += [os.path.join(rel, f) for f in files if f in ("package.json", ".npmrc")]
        dirs[:] = [d for d in dirs if d != "node_modules"]
    return [f"the workspace has {p}: vitest would load packages from it instead of the environment's"
            for p in sorted(found)[:5]]


def vitest_files(nodes):
    return list(dict.fromkeys(n.split("::", 1)[0] for n in nodes))


def run_validation(spec, workdir, sandbox_cfg, log=None):
    """Run one validation command in the sandbox. No sandbox means blocked, never a pass and never a fallback."""
    cfg = {**(sandbox_cfg or {}), "timeout_s": spec["timeout_s"]}
    if spec.get("environment"):
        cfg["environment"] = spec["environment"]      # its own image, never the default one (tools/sandbox.settings)
    nonce = vitest_nonce() if kind(spec) == "vitest" else None
    shadow = vitest_workspace_problems(workdir) if nonce else []
    if shadow:
        return {"id": f"validation:{spec['id']}", "layer": "C", "status": "fail", "reason": "; ".join(shadow),
                "evidence": {"argv": argv(spec), "runner": "vitest", "consistent": False, "output_tail": "; ".join(shadow)}}
    try:
        r = sb.run_command(argv(spec, nonce), workdir=workdir, cfg=cfg, log=log, meta={"validation": spec["id"]})
    except sb.SandboxUnavailable as e:
        return {"id": f"validation:{spec['id']}", "layer": "C", "status": "blocked",
                "reason": f"sandbox unavailable: {e}", "evidence": {"argv": argv(spec)}}
    return judge_result(spec, r, nonce)
