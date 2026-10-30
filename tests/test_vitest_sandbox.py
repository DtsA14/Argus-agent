"""Vitest validations in the real sandbox (docs/reviews/SPEC_PWA_VIEWER.md V, section 9): the pwa_node22 environment
(scripts/build_env_node.sh; scripts/verify.sh builds it), fixtures/repos/vitest_demo. Same isolation as every sandbox
run: no network, read-only workspace and root, non-root, no capabilities. Needs Docker and that image; without them the
tests are skipped with "SANDBOX NOT AVAILABLE", which scripts/verify.sh does not count as passing."""
import shutil
from pathlib import Path

import pytest

from acceptance import validation as va
from runner import load_config
from tools import sandbox as sb

ROOT = Path(__file__).resolve().parent.parent
DEMO_REPO = ROOT / "fixtures" / "repos" / "vitest_demo"
DEMO = "src/demo.test.jsx::"
ISOLATION = [f"src/isolation.test.js::{n}" for n in ("no network", "workspace is read-only",
                                                      "node_modules is read-only", "runs as nobody")]
EXPECTED = {DEMO + "adds": "ok", DEMO + "group > nested name": "ok", DEMO + "renders": "ok",
            DEMO + "fails by assertion": "FAIL", DEMO + "fails in code": "FAIL", DEMO + "element not found": "FAIL",
            DEMO + "message names a path": "FAIL", DEMO + "skipped": "skipped"}


@pytest.fixture(scope="module")
def cfg():
    c = {**(load_config().get("sandbox") or {}), "kind": "docker", "memory": "512m"}
    ok, reason = sb.status({**c, "environment": "pwa_node22"})
    if not ok:
        pytest.skip(f"SANDBOX NOT AVAILABLE: {reason}")
    return c


@pytest.fixture
def demo(tmp_path):
    ws = tmp_path / "ws"
    shutil.copytree(DEMO_REPO, ws)
    return ws


def spec(*files, must=(), **extra):
    return {"id": "t", "executable": "vitest", "args": ["run", *files], "timeout_s": 120, "min_tests": 1,
            "max_skipped": 0, "must_pass": list(must), "environment": "pwa_node22", **extra}


def test_the_isolation_holds_inside_the_node_environment(cfg, demo):
    v = va.run_validation(spec("src/isolation.test.js", must=ISOLATION, min_tests=4), str(demo), cfg)
    assert v["status"] == "pass", v["reason"] + "\n" + v["evidence"]["output_tail"]
    assert v["evidence"]["must_pass"] == {n: "ok" for n in ISOLATION} and v["evidence"]["environment"] == "pwa_node22"
    assert not (demo / "written_by_a_test.txt").exists()


def test_every_test_is_classified_the_same_way_in_two_runs(cfg, demo):
    """Not only the same totals: the same status for every test, and the expected one; it fails as it should."""
    seen = []
    for _ in range(2):
        v = va.run_validation(spec("src/demo.test.jsx", max_skipped=1), str(demo), cfg)
        e = v["evidence"]
        seen.append({n: s for n, s in e["must_pass"].items()} or None)
        assert v["status"] == "fail" and e["consistent"] is True, v["reason"]
        assert (e["tests_run"], e["failures"], e["skipped"], e["errors"]) == (8, 4, 1, 0)
        assert e["failed_nodes"] == sorted(n for n, s in EXPECTED.items() if s == "FAIL")
    nonce = va.vitest_nonce()
    r = sb.run_command(va.vitest_argv(nonce, ["src/demo.test.jsx"]), workdir=str(demo),
                       cfg={**cfg, "environment": "pwa_node22", "timeout_s": 120})
    assert va.parse_vitest(r["stdout"], nonce, ["src/demo.test.jsx"])["tests"] == EXPECTED


def test_only_the_requested_file_runs_never_one_whose_name_contains_it(cfg, demo):
    """vitest's own filter matches substrings: src/sum.test.js would also run src/sum.test.jsx."""
    v = va.run_validation(spec("src/sum.test.js", must=["src/sum.test.js::js"]), str(demo), cfg)
    assert v["status"] == "pass", v["reason"]
    assert v["evidence"]["tests_run"] == 1


@pytest.mark.parametrize("files, must, why", [
    (["src/demo.test.jsx"], [DEMO + "fails by assertion"], f"required test {DEMO}fails by assertion is 'FAIL'"),
    (["src/demo.test.jsx"], [DEMO + "skipped"], "skipped"),
    (["src/sum.test.js", "src/broken.test.js"], ["src/sum.test.js::js"], "vitest outcome FAILED"),
    (["src/sum.test.js"], ["src/sum.test.js::nope"], "did not run"),
])
def test_nothing_that_did_not_really_pass_passes(cfg, demo, files, must, why):
    v = va.run_validation(spec(*files, must=must, max_skipped=1), str(demo), cfg)
    assert v["status"] == "fail" and why in v["reason"], v["reason"]


def test_a_file_that_does_not_load_is_named_for_the_agent(cfg, demo):
    v = va.run_validation(spec("src/broken.test.js"), str(demo), cfg)
    tail = v["evidence"]["output_tail"]
    assert v["status"] == "fail" and v["evidence"]["errors"] == 1
    assert "ERROR src/broken.test.js" in tail and "missing.js" in tail


def test_the_red_check_tells_an_assertion_from_any_other_failure(cfg, demo):
    nodes = [DEMO + "fails by assertion", DEMO + "fails in code", DEMO + "element not found", DEMO + "adds",
             DEMO + "message names a path"]
    got, why = va.red_check(nodes, str(demo), cfg, timeout_s=120, environment="pwa_node22", runner="vitest")
    assert why is None, why
    a, code, missing, ok, named = (got[n] for n in nodes)
    # where it was raised is read from the stack's "at" lines, never from a path the message happens to name
    assert (named["path"], named["repo_paths"]) == ("src/demo.test.jsx", ["src/demo.test.jsx"])
    assert (a["outcome"], a["assertion"], a["type"], a["path"]) == ("failed", True, "AssertionError",
                                                                    "src/demo.test.jsx")
    assert (code["assertion"], code["type"], code["path"]) == (False, "TypeError", "src/boom.js")
    assert code["repo_paths"][:2] == ["src/boom.js", "src/demo.test.jsx"]
    assert (missing["assertion"], missing["type"]) == (False, "TestingLibraryElementError")
    assert ok["outcome"] == "passed"


def test_a_vitest_command_is_never_run_in_a_python_environment(cfg, demo):
    v = va.run_validation(spec("src/sum.test.js", must=["src/sum.test.js::js"], environment="argus"), str(demo), cfg)
    assert v["status"] != "pass"
