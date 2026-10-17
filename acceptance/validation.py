"""Validation commands: structured (executable + args), checked against an allowlist, run in the sandbox without a
shell, and judged from their own output. Never a shell string, never chosen by the agent.

Slice 1 allows exactly one shape:  python -m unittest discover [-s DIR] [-t DIR] [-p PATTERN] [-k NAME ...]
The harness runs it as  python3 -I -m unittest discover ... -v  with the workspace mounted read-only, so the
check cannot change what it checks, and reads the verbose per-test lines and the summary from the output.

Limits (stated, not hidden): the result is read from the test runner's own output, and the code under test runs in
the same process. Code that deliberately forges unittest output from inside the process is not detected here; it
is contained by the sandbox, and the protected test files (scope) keep the tests themselves honest.
"""
import re

from tools import sandbox as sb

PREFIX = ["-m", "unittest", "discover"]
OPTIONS = {"-s": False, "-t": False, "-p": False, "-k": True}   # option -> may repeat
VALUE = re.compile(r"^[A-Za-z0-9_*?.][A-Za-z0-9_*?./-]{0,199}$")
MAX_ARGS = 16

TEST_LINE = re.compile(r"^(\w+) \(([\w.]+)\)(?: (.*))?$")
RAN = re.compile(r"^Ran (\d+) tests? in ")
FINAL = re.compile(r"^(OK|FAILED)(?: \((.*)\))?$")


def validate_command(executable, args):
    """Problems with a validation command, or []."""
    if executable != "python":
        return [f"executable {executable!r} is not allowed (allowlist: python)"]
    if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
        return ["args must be a list of strings"]
    if len(args) > MAX_ARGS:
        return [f"at most {MAX_ARGS} args"]
    if args[:3] != PREFIX:
        return [f"args must start with {PREFIX} (slice 1 allows unittest discovery only)"]
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


def judge_result(spec, r):
    """Criterion verdict for one validation run: ok only when every condition in the contract holds."""
    parsed = parse_unittest((r.get("stderr") or "") + "\n" + (r.get("stdout") or ""))
    must = {t: parsed["tests"].get(t) for t in spec.get("must_pass", [])}
    evidence = {"argv": argv(spec), "exit_code": r.get("exit_code"), "timed_out": r.get("timed_out"),
                "killed": r.get("killed"), "cleanup_failed": r.get("cleanup_failed"),
                "output_limit_exceeded": r.get("output_limit_exceeded"), "truncated": r.get("truncated"),
                "tests_run": parsed["tests_run"], "outcome": parsed["outcome"], "skipped": parsed["skipped"],
                "failures": parsed["failures"], "errors": parsed["errors"], "must_pass": must,
                "output_tail": (r.get("stderr") or "")[-2000:]}
    problems = []
    if r.get("timed_out"):
        problems.append(f"timed out after {spec['timeout_s']}s (container killed"
                        + (", cleanup not confirmed)" if r.get("cleanup_failed") else ")"))
    elif r.get("output_limit_exceeded"):
        problems.append("output limit exceeded (container killed)")
    else:
        if parsed["tests_run"] is None or parsed["outcome"] is None:
            problems.append("no unittest summary in the output")
        if r.get("exit_code") != 0:
            problems.append(f"exit code {r.get('exit_code')}")
        if parsed["outcome"] not in (None, "OK"):
            problems.append(f"unittest outcome {parsed['outcome']}")
        if parsed["tests_run"] is not None and parsed["tests_run"] < spec["min_tests"]:
            problems.append(f"{parsed['tests_run']} tests ran, contract requires at least {spec['min_tests']}")
        if parsed["skipped"] > spec["max_skipped"]:
            problems.append(f"{parsed['skipped']} tests skipped, contract allows {spec['max_skipped']}")
        for t, st in must.items():
            if st != "ok":
                problems.append(f"required test {t} {'did not run' if st is None else 'is ' + repr(st)}")
    return {"id": f"validation:{spec['id']}", "layer": "C", "status": "fail" if problems else "pass",
            "reason": "; ".join(problems), "evidence": evidence}


def run_validation(spec, workdir, sandbox_cfg, log=None):
    """Run one validation command in the sandbox. No sandbox means blocked, never a pass and never a fallback."""
    cfg = {**(sandbox_cfg or {}), "timeout_s": spec["timeout_s"]}
    try:
        r = sb.run_command(argv(spec), workdir=workdir, cfg=cfg, log=log, meta={"validation": spec["id"]})
    except sb.SandboxUnavailable as e:
        return {"id": f"validation:{spec['id']}", "layer": "C", "status": "blocked",
                "reason": f"sandbox unavailable: {e}", "evidence": {"argv": argv(spec)}}
    return judge_result(spec, r)
