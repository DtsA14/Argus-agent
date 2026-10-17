"""M6 W1 in the real sandbox: pytest validations in the `argus` environment, whose image is built offline from the
verified venv (scripts/build_argus_sandbox_image.sh; scripts/verify.sh builds it). Same isolation as every sandbox
run: no network, read-only workspace and root, non-root, no capabilities. Needs Docker and that image; without them
the tests are skipped with "SANDBOX NOT AVAILABLE", which scripts/verify.sh does not count as passing."""
import shutil
from pathlib import Path

import pytest

from acceptance import validation as va
from runner import load_config
from tools import sandbox as sb

ROOT = Path(__file__).resolve().parent.parent
DEMO_REPO = ROOT / "fixtures" / "repos" / "pytest_demo"
DEMO = "tests/test_demo.py::"
ISOLATION = ["tests/test_isolation.py::test_no_network", "tests/test_isolation.py::test_workspace_is_read_only",
             "tests/test_isolation.py::test_runs_as_nobody"]
EXPECTED = {DEMO + "test_add": "ok", DEMO + "test_add_param[1-2-3]": "ok", DEMO + "test_add_param[2-2-4]": "ok",
            DEMO + "TestDiv::test_div": "ok", DEMO + "test_fails": "FAIL", DEMO + "test_skipped": "skipped",
            DEMO + "test_xfail": "expected failure", DEMO + "test_xpass": "unexpected success",
            DEMO + "test_setup_error": "ERROR", DEMO + "test_teardown_error": "ERROR",
            **{n: "ok" for n in ISOLATION}}


@pytest.fixture(scope="module")
def cfg():
    c = {**(load_config().get("sandbox") or {}), "kind": "docker", "memory": "512m"}
    ok, reason = sb.status({**c, "environment": "argus"})
    if not ok:
        pytest.skip(f"SANDBOX NOT AVAILABLE: {reason}")
    return c


@pytest.fixture
def demo(tmp_path):
    ws = tmp_path / "ws"
    shutil.copytree(DEMO_REPO, ws)
    return ws


def spec(*targets, must=(), environment="argus", **extra):
    s = {"id": "t", "executable": "python", "args": ["-m", "pytest", *targets], "timeout_s": 120, "min_tests": 1,
         "max_skipped": 0, "must_pass": list(must), **extra}
    if environment:
        s["environment"] = environment
    return s


def test_the_isolation_holds_inside_the_argus_environment(cfg, demo):
    v = va.run_validation(spec("tests/test_isolation.py", must=ISOLATION, min_tests=3), str(demo), cfg)
    assert v["status"] == "pass", v["reason"]
    assert v["evidence"]["must_pass"] == {n: "ok" for n in ISOLATION} and v["evidence"]["environment"] == "argus"
    assert not (demo / "written_by_a_test.txt").exists()


def test_every_node_is_classified_the_same_way_in_two_runs(cfg, demo):
    """Not only the same totals: the same status for every node, and the expected one."""
    run_cfg = {**cfg, "environment": "argus", "timeout_s": 120}
    s = spec("tests", max_skipped=5)
    runs = [sb.run_command(va.argv(s), workdir=str(demo), cfg=run_cfg) for _ in range(2)]
    parsed = [va.parse_pytest(r["stdout"]) for r in runs]
    assert parsed[0]["tests"] == parsed[1]["tests"] == EXPECTED
    for r, p in zip(runs, parsed):
        assert p["consistent"] and p["collected"] == 13
        e = va.judge_result(s, r)["evidence"]
        assert (e["tests_run"], e["failures"], e["errors"], e["skipped"]) == (13, 1, 2, 3)


@pytest.mark.parametrize("targets, must, why", [
    (["tests/test_isolation.py"], ["tests/test_isolation.py::test_never_written"], "did not run"),
    (["tests/test_isolation.py::test_never_written"], [], "exit code 4"),
    (["tests/test_nope.py"], [], "exit code 4"),
    (["tests_broken"], [], "exit code 2"),
    (["-k", "nomatch", "tests"], [], "exit code 5"),
])
def test_nothing_that_did_not_really_pass_passes(cfg, demo, targets, must, why):
    v = va.run_validation(spec(*targets, must=must), str(demo), cfg)
    assert v["status"] == "fail" and why in v["reason"], v["reason"]


def test_the_default_image_is_not_used_for_an_environment(cfg, demo):
    """The default sandbox image has no pytest: the same validation without the environment cannot pass, so the
    pass above came from the argus image."""
    if not sb.status(cfg)[0]:
        pytest.skip(f"SANDBOX NOT AVAILABLE: default image: {sb.status(cfg)[1]}")
    v = va.run_validation(spec("tests/test_isolation.py", must=ISOLATION, environment=None), str(demo), cfg)
    assert v["status"] == "fail" and "No module named pytest" in v["evidence"]["stderr_tail"]


def test_argus_tests_run_in_the_argus_environment(cfg, tmp_path):
    """Argus's own tests (not the ones that need Docker, git or bash) run there: the self-hosting pilot's case."""
    ws = tmp_path / "argus"
    shutil.copytree(ROOT, ws, ignore=shutil.ignore_patterns(".git", ".venv*", "runs", "verification", "__pycache__"))
    node = "tests/test_parse_subtests.py::test_an_erroring_message_subtest_wins_over_a_failing_one"
    v = va.run_validation(spec("tests/test_parse_subtests.py", "tests/test_pytest_validation.py", must=[node],
                               min_tests=50), str(ws), cfg)
    assert v["status"] == "pass", v["reason"]
    assert v["evidence"]["must_pass"] == {node: "ok"} and v["evidence"]["consistent"]
