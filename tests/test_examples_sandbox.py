"""SPEC_EXAMPLE_GATE PR 1: what only the container can show about running an example. The tree is mounted read-only at
/workspace, the network is off, and one container runs a whole pass. A sandbox module: without Docker and a pinned image it
skips with the phrase below, and scripts/verify.sh then FAILS unless ARGUS_SANDBOX_OPTIONAL=1."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from codetask import examples as ex  # noqa: E402
from tools import sandbox as sb  # noqa: E402

CFG = {"kind": "docker", "memory": "256m", "cpus": "1", "pids": 64, "timeout_s": 60, "max_output_bytes": 65536}


@pytest.fixture(scope="module")
def cfg():
    ok, reason = sb.status(CFG)
    if not ok:
        pytest.skip(f"SANDBOX NOT AVAILABLE: {reason}")
    return dict(CFG)


@pytest.fixture
def tree(tmp_path):
    root = tmp_path / "tree"
    (root / "shop").mkdir(parents=True)
    (root / "shop" / "__init__.py").write_text("")
    (root / "shop" / "rules.py").write_text("FLOOR = 50.0\ndef blocked(price):\n    return price <= FLOOR\n")
    return root


def good(**kw):
    return {"id": "e1", "tier": "same", "says": "A price at the floor is blocked",
            "setup": "from shop.rules import blocked", "run": "blocked(50.0)", "expect": True, **kw}


def evaluate(cfg, tree, examples, **kw):
    return ex.evaluate(examples, lambda argv: sb.run_command(argv, workdir=tree, cfg=cfg), root="/workspace", **kw)


def test_one_container_runs_a_pass_and_the_results_are_the_real_values(cfg, tree):
    out = evaluate(cfg, tree, [good(), good(id="e2", run="blocked(51.0)", expect=True)])
    assert [(r["id"], r["status"]) for r in out] == [("e1", "pass"), ("e2", "fail")] and out[1]["actual"] is False


def test_the_tree_is_read_only_inside_the_container(cfg, tree):
    write = good(setup="from shop.rules import blocked\nopen('/workspace/shop/NEW.txt', 'w').write('x')", run="blocked(1.0)",
                 expect=True)
    out = evaluate(cfg, tree, [write])
    assert out[0]["status"] == "error" and not (tree / "shop" / "NEW.txt").exists()
    assert "Read-only" in out[0]["actual"] or "Errno 30" in out[0]["actual"]            # the mount, not a user id


def test_the_network_is_off(cfg, tree):
    net = good(setup="import socket\nfrom shop.rules import blocked\nsocket.create_connection(('1.1.1.1', 53), timeout=3)",
               run="blocked(1.0)", expect=True)
    out = evaluate(cfg, tree, [net])
    assert out[0]["status"] == "error" and any(w in out[0]["actual"].lower() for w in ("unreachable", "errno 101"))
    nics = good(setup="import os\nfrom shop.rules import blocked", run="sorted(os.listdir('/sys/class/net'))", expect=["lo"])
    assert evaluate(cfg, tree, [nics])[0]["status"] == "pass"                           # only the loopback exists


def test_an_override_works_in_the_container_and_does_not_leak(cfg, tree):
    ov = good(tier="whatif", setup="from shop.rules import blocked", run="blocked(10.0)", expect=True,
              overrides={"shop.rules.FLOOR": 100.0})
    plain = good(id="e2", run="blocked(10.0)", expect=True)
    out = evaluate(cfg, tree, [ov, plain])
    assert [r["status"] for r in out] == ["pass", "pass"]               # e2 passes because FLOOR is 50.0 again in its own process


def test_a_child_timeout_is_a_result_not_a_hung_container(cfg, tree):
    (tree / "shop" / "slow.py").write_text("import time\ndef spin():\n    time.sleep(30)\n    return 1\n")
    argv, frame = ex.build_argv([good(setup="from shop.slow import spin", run="spin()", expect=1)], root="/workspace",
                                child_timeout=1)
    r = sb.run_command(argv, workdir=tree, cfg=cfg)
    got = ex.read_pass(r["stdout"], frame, [good()])
    assert got["e1"]["error"] == ex.E_TIMEOUT and not r["timed_out"]


def test_a_huge_value_costs_that_example_only_not_the_pass(cfg, tree):
    huge = good(setup="from shop.rules import blocked", run="'x' * 200000", expect="y")
    out = evaluate(cfg, tree, [huge, good(id="e2"), good(id="e3", run="blocked(10.0)", expect=True)])
    assert [r["status"] for r in out] == ["invalid", "pass", "pass"] and "too large" in out[0]["actual"]


def test_the_container_timeout_covers_every_child(cfg, tree):
    (tree / "shop" / "slow.py").write_text("import time\ndef spin():\n    time.sleep(30)\n    return 1\n")
    slow = [good(id=f"e{n}", setup="from shop.slow import spin", run="spin()", expect=1) for n in range(1, 4)]
    argv, frame = ex.build_argv(slow, root="/workspace", child_timeout=2)
    r = sb.run_command(argv, workdir=tree, cfg={**cfg, "timeout_s": 40})
    got = ex.read_pass(r["stdout"], frame, slow)
    assert all(v["error"] == ex.E_TIMEOUT for v in got.values()) and not r["timed_out"]     # each child timed out on its own
