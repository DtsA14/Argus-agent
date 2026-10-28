"""Validation commands: structured (executable + args), checked against an allowlist, run in the sandbox without a
shell, and judged from their own output. Never a shell string, never chosen by the agent.

Two shapes are allowed:
  python -m unittest discover [-s DIR] [-t DIR] [-p PATTERN] [-k NAME ...]
      run as  python3 -I -m unittest discover ... -v
  python -m pytest TARGET [TARGET ...] [-k NAME ...]      (M6 W1; TARGET: a relative path or a pytest node id)
      run as  python3 -I -B -m pytest <fixed harness options> TARGET ... ; the harness alone chooses the options
      (no plugins, ini overrides or rootdir from the contract) and pins the rootdir to /workspace, so node ids are
      relative to the workspace root.
Both run with the workspace mounted read-only, so the check cannot change what it checks, and are judged from the
runner's verbose per-test lines and its summary. A pytest run is trusted only when the per-test lines account for
the summary exactly (same count per outcome, every collected test seen); otherwise the result fails closed.
Node ids may contain spaces (parametrize ids often do): a line is the node id, one space, and the status word at the
end (with pytest's reason in parentheses for skips and xfails). A line read wrongly cannot make a run pass: the counts
would no longer match the summary. Required tests (must_pass) are written without spaces.

Limits (stated, not hidden): the result is read from the test runner's own output, and the code under test runs in
the same process. Code that deliberately forges unittest output from inside the process is not detected here; it
is contained by the sandbox, and the protected test files (scope) keep the tests themselves honest.
"""
import json
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
    """"pytest" or "unittest", from the command's own prefix (validate_command decides whether it is allowed)."""
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


def validate_command(executable, args):
    """Problems with a validation command, or []."""
    if executable != "python":
        return [f"executable {executable!r} is not allowed (allowlist: python)"]
    if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
        return ["args must be a list of strings"]
    if len(args) > MAX_ARGS:
        return [f"at most {MAX_ARGS} args"]
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


def argv(spec):
    """The exact argv run in the container (no shell). Verbose output is always on: it names each test."""
    errors = validate_command(spec["executable"], spec["args"])
    if errors:
        raise ValueError("; ".join(errors))
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


def judge_result(spec, r):
    """Criterion verdict for one validation run: ok only when every condition in the contract holds."""
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
        if evidence.get("skip_violations"):
            problems.append("skipped or xfail in a changed test file, and not marked so before the change: "
                            + ", ".join(evidence["skip_violations"]))
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
# is printed after a nonce line once pytest is done. Like any validation it is read from the process that runs the code
# under test: a deliberate forgery from inside is contained by the sandbox, not detected.
RED_CHECK = r"""
import json, os, sys
import pytest
nonce, nodes = sys.argv[1], sys.argv[2:]
root = os.path.realpath("/workspace")
out = {}


def inside(p):
    p = os.path.realpath(str(p))
    return p.startswith(root + os.sep) and "site-packages" not in p.split(os.sep)


class Record:
    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item, call):
        rep = (yield).get_result()
        if call.when != "call":
            if rep.failed:
                out[item.nodeid] = {"outcome": "error", "type": None, "assertion": False, "path": None}
            return
        e = call.excinfo
        if e is None:
            out.setdefault(item.nodeid, {"outcome": rep.outcome, "type": None, "assertion": False, "path": None})
            return
        path = next((os.path.relpath(os.path.realpath(str(x.path)), root).replace(os.sep, "/")
                     for x in reversed(e.traceback) if inside(x.path)), None)
        out[item.nodeid] = {"outcome": rep.outcome, "type": e.type.__module__ + "." + e.type.__qualname__,
                            "assertion": issubclass(e.type, (AssertionError, pytest.fail.Exception)), "path": path}


pytest.main(["-p", "no:cacheprovider", "-o", "addopts=", "--rootdir", "/workspace", "-q", "--color=no", *nodes],
            plugins=[Record()])
sys.stdout.write("\n" + nonce + json.dumps(out, sort_keys=True) + "\n")
sys.stdout.flush()
"""


def red_argv(nonce, nodes):
    """The harness's own run of the red check; never a contract command."""
    return ["python3", "-I", "-B", "-c", RED_CHECK, nonce, *nodes]


def red_check(nodes, workdir, sandbox_cfg, *, timeout_s, environment=None, log=None):
    """({node id: {outcome, type, assertion, path}}, None) for the given pytest node ids, or (None, why) when the run or
    its JSON could not be read."""
    nonce = "ARGUS-RED-" + secrets.token_hex(16) + ":"
    cfg = {**(sandbox_cfg or {}), "timeout_s": timeout_s}
    if environment:
        cfg["environment"] = environment
    try:
        r = sb.run_command(red_argv(nonce, nodes), workdir=workdir, cfg=cfg, log=log, meta={"red_check": len(nodes)})
    except sb.SandboxUnavailable as e:
        return None, f"sandbox unavailable: {e}"
    if r.get("timed_out") or r.get("output_limit_exceeded") or r.get("truncated"):
        return None, "the run timed out or its output was cut"
    lines = [line[len(nonce):] for line in (r.get("stdout") or "").splitlines() if line.startswith(nonce)]
    try:
        got = json.loads(lines[-1]) if len(lines) == 1 else None
    except ValueError:
        got = None
    if not isinstance(got, dict):
        return None, "no record of the run (exit code " + str(r.get("exit_code")) + ")"
    return got, None


def run_validation(spec, workdir, sandbox_cfg, log=None):
    """Run one validation command in the sandbox. No sandbox means blocked, never a pass and never a fallback."""
    cfg = {**(sandbox_cfg or {}), "timeout_s": spec["timeout_s"]}
    if spec.get("environment"):
        cfg["environment"] = spec["environment"]      # its own image, never the default one (tools/sandbox.settings)
    try:
        r = sb.run_command(argv(spec), workdir=workdir, cfg=cfg, log=log, meta={"validation": spec["id"]})
    except sb.SandboxUnavailable as e:
        return {"id": f"validation:{spec['id']}", "layer": "C", "status": "blocked",
                "reason": f"sandbox unavailable: {e}", "evidence": {"argv": argv(spec)}}
    return judge_result(spec, r)
