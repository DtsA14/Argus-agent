"""FIX-C leaks found by Fable's reading of e892d5a (docs/reviews/SPEC_FIX_C.md, 'FIX-C2'): a registered key value must not reach
runner.py's result.json, a verdict file, the terminal of any entry script that can hold a key, or hide inside the base64 of
`user:key` (HTTP Basic)."""
import ast
import base64
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_drafter as td  # noqa: E402
from harness import redact  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CANARY = "sk-CANARY-NOT-A-KEY-1234567890"


@pytest.fixture(autouse=True)
def forget():
    redact.clear()
    yield
    redact.clear()


def test_the_result_file_of_the_graph_runner_never_holds_a_registered_key(tmp_path):
    import copy
    from runner import load_config, run_task
    redact.register(CANARY)
    cfg = copy.deepcopy(load_config())
    r = run_task(goal="x", scenario="pass", run_id=f"r-{CANARY}", runs_dir=tmp_path, cfg=cfg)
    assert r["run_id"].endswith(CANARY)                               # the run itself carries the value (memory is not cleaned)
    assert CANARY not in (tmp_path / f"r-{CANARY}" / "result.json").read_text(encoding="utf-8")


def test_a_verdict_file_never_holds_a_registered_key(tmp_path):
    from test_router import Env
    redact.register(CANARY)

    def leaky(spec, workspace, sandbox_cfg, log=None):
        r = td.fake_validate(spec, workspace, sandbox_cfg, log=log)
        r["tail"] = [*r.get("tail", []), f"E   the provider said {CANARY}"] if isinstance(r.get("tail"), list) else f"provider said {CANARY}"
        r["detail"] = f"provider said {CANARY}"
        return r
    env = Env(tmp_path)
    env.deps.validate = leaky
    env.code()
    job, r = env.approve()
    files = sorted((job.runs / "jtest-a1").glob("verdict_*.json"))
    assert files, "no verdict file was written"
    assert all(CANARY not in f.read_text(encoding="utf-8") for f in files)
    assert any(redact.MARK in f.read_text(encoding="utf-8") for f in files)       # it was there, and was cleaned


@pytest.mark.parametrize("klen", [8, 9, 10, 12, 16, 30, 51])
def test_the_base64_of_user_and_key_is_hidden_at_every_alignment(klen):
    key = "sk-" + "K" * (klen - 4) + "7"
    redact.register(key)
    for ulen in range(0, 12):                                          # Basic auth: base64("user:key"), any user, any tail
        for tail in ("", ":x", "\n"):
            token = base64.b64encode(("u" * ulen + ":" + key + tail).encode()).decode()
            assert token not in redact.scrub(f"Authorization: Basic {token}"), (ulen, tail)


def test_the_base64_forms_do_not_hide_ordinary_text():
    redact.register("sk-ordinary-key-1234567890")
    text = "The quick brown fox jumps over the lazy dog; 0123456789 ABCDEFGHIJKLMNOP"
    assert redact.scrub(text) == text


# ---- every entry script that can hold a key installs the terminal filter ---------------------------------------------

def _entry_scripts_that_can_hold_a_key():
    out = []
    for path in [ROOT / "main.py", *sorted((ROOT / "scripts").glob("*.py"))]:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        roots = {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module} | \
                {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        has_main = any(isinstance(n, ast.If) and "__main__" in ast.dump(n.test) for n in tree.body)
        if has_main and roots & {"models", "runner", "codetask", "router"} and path.name not in DISPLAY_ONLY:
            out.append(path)
    return out


# read job files and print them; they never build a client, so no key is ever registered in their process
DISPLAY_ONLY = {"pin_status.py", "scoreboard.py", "swe_grade.py", "build_review.py"}


def test_every_entry_script_that_can_hold_a_key_installs_the_terminal_filter():
    scripts = _entry_scripts_that_can_hold_a_key()
    assert {p.name for p in scripts} >= {"main.py", "argus.py", "run_code_task.py", "draft_task.py"}
    bad = [p.name for p in scripts if "redact" not in p.read_text(encoding="utf-8") or ".install()" not in p.read_text(encoding="utf-8")]
    assert bad == [], f"these scripts can hold a key and do not install the filter: {bad}"
