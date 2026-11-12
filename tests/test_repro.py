"""SPEC_REPRO_V0 R1: the issue's python example is run at the base commit and shown before approve; display only."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_drafter as td  # noqa: E402
from acceptance import repro as rp  # noqa: E402
from router import job as rj  # noqa: E402
from test_router import Env  # noqa: E402

FENCE = "```python\n{}\n```"


def issue(*codes, lang="python"):
    return "Something is wrong.\n\n" + "\n\n".join(f"```{lang}\n{c}\n```" for c in codes) + "\n\nThanks."


class Box:
    """A stand-in for sandbox.run_python: records what it was given and answers from a list."""
    def __init__(self, *answers):
        self.answers, self.calls = list(answers), []

    def __call__(self, code, *, workdir, data_dir, cfg, **kw):
        self.calls.append({"code": code, "workdir": Path(workdir), "cfg": cfg})
        a = self.answers.pop(0)
        if isinstance(a, Exception):
            raise a
        return a


OK = {"exit_code": 0, "stdout": "0o600\n", "stderr": "", "timed_out": False}
BAD = {"exit_code": 1, "stdout": "", "stderr": "Traceback\n  File x\nValueError: nope\n", "timed_out": False}


# ---- which blocks -------------------------------------------------------------------------------------------------

def test_only_python_fences_are_taken_in_order_and_at_most_three():
    text = issue("a = 1", "b = 2", "c = 3", "d = 4") + "\n```js\nlet x\n```\n~~~py\ne = 5\n~~~"
    assert [c.strip() for _, c in rp.blocks(text)] == ["a = 1", "b = 2", "c = 3"]
    assert rp.blocks(issue("x", lang="js")) == [] and rp.blocks(None) == [] and rp.blocks(7) == []


@pytest.mark.parametrize("code,word", [(">>> a = 1\n>>> a", "interactive"), ("x = 1\n...\ny = 2", "bare"),
                                       ("$ pip install x\nimport x", "shell"), ("x = 1\n" * 3000, "bytes"),
                                       ("\n\n", "empty")])
def test_a_block_that_is_not_a_script_is_skipped_with_the_reason(code, word):
    assert word in rp.skip_reason(code)
    box = Box()
    (r,) = rp.run(Path("."), issue(code), {}, runner=box)
    assert r["status"] == "skipped" and word in r["reason"] and box.calls == []


# ---- the run ------------------------------------------------------------------------------------------------------

def test_a_block_that_runs_clean_or_raises_or_times_out_says_so(tmp_path):
    (tmp_path / "pkg.py").write_text("X = 1\n")
    box = Box(OK, BAD, {"exit_code": None, "stdout": "partial", "stderr": "", "timed_out": True})
    res = rp.run(tmp_path, issue("print(1)", "raise ValueError('nope')", "while True: pass"), {"image": "i"}, runner=box)
    assert [r["status"] for r in res] == ["ok", "raised", "timeout"]
    assert res[0]["stdout"] == "0o600\n" and res[1]["stderr_last_line"] == "ValueError: nope"
    assert res[2]["stdout"] == "partial" and "20 s" in res[2]["reason"]
    assert all(c["cfg"]["timeout_s"] == rp.TIMEOUT_S and c["cfg"]["image"] == "i" for c in box.calls)
    assert all(c["code"].startswith(rp.PRELUDE) for c in box.calls) and "/workspace" in rp.PRELUDE   # python -I: no cwd


def test_the_code_runs_on_a_copy_and_the_base_is_never_written(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    (base / "pkg.py").write_text("X = 1\n")

    class Writer(Box):
        def __call__(self, code, *, workdir, data_dir, cfg, **kw):
            (Path(workdir) / "pkg.py").write_text("X = 2\n")
            (Path(workdir) / "new.txt").write_text("hi")
            return super().__call__(code, workdir=workdir, data_dir=data_dir, cfg=cfg)
    box = Writer(OK)
    rp.run(base, issue("print(1)"), {}, runner=box)
    assert (base / "pkg.py").read_text() == "X = 1\n" and not (base / "new.txt").exists()
    assert box.calls[0]["workdir"] != base


def test_output_is_cut_and_the_last_line_of_the_error_is_kept():
    big = {"exit_code": 0, "stdout": "x" * 5000, "stderr": "", "timed_out": False}
    (r,) = rp.run(Path("."), issue("print(1)"), {}, runner=Box(big))
    assert len(r["stdout"]) == rp.MAX_OUT


def test_anything_that_goes_wrong_gives_no_result_not_an_error(tmp_path):
    assert rp.run(tmp_path, issue("x = 1"), {}, runner=Box(RuntimeError("docker is down"))) is None
    assert rp.run(tmp_path / "missing", issue("x = 1"), {}, runner=Box(OK)) is None
    assert rp.run(tmp_path, "no code here", {}, runner=Box()) == []
    assert rp.run(tmp_path, None, {}, runner=Box()) == []


# ---- stored, bound to the issue and the base, and the line ---------------------------------------------------------

def test_a_stored_result_is_read_back_only_for_the_same_issue_and_base(tmp_path):
    p = tmp_path / "repro.json"
    res = [{"index": 0, "status": "ok", "exit_code": 0, "stdout": "1", "stderr_last_line": "", "reason": ""}]
    rp.store(p, "the issue", "snap1", res)
    assert rp.load(p, "the issue", "snap1") == res
    assert rp.load(p, "another issue", "snap1") is None and rp.load(p, "the issue", "snap2") is None
    p.write_text("not json")
    assert rp.load(p, "the issue", "snap1") is None
    rp.store(p, "the issue", "snap1", None)                      # "not run" is stored as such
    assert rp.load(p, "the issue", "snap1") is None


def test_the_line_says_what_ran_and_warns_that_clean_is_not_proof():
    ok = {"status": "ok"}
    assert rp.line(None) == "issue example at base: not run"
    assert "no runnable example" in rp.line([])
    assert "not run (an interactive" in rp.line([{"status": "skipped", "reason": "an interactive session"}])
    assert rp.line([{"status": "raised", "stderr_last_line": "ValueError: nope"}]) == \
        "issue example at base: raised ValueError: nope"
    out = rp.line([ok, {"status": "timeout"}])
    assert "ran clean, timed out" in out and "does not prove the bug is gone" in out


# ---- in the job: shown, never decisive -----------------------------------------------------------------------------

def code_with(tmp_path, monkeypatch, runner, job_id="jtest", text=None):
    from tools import sandbox
    monkeypatch.setattr(sandbox, "run_python", runner)
    env = Env(tmp_path)
    job = rj.start_code(repo=env.repo, commit="HEAD", issue=text or td.ISSUE + "\n\n" + issue("print(total(1, 5))"),
                        cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs, job_id=job_id)
    return env, job


def test_the_approve_screen_and_status_show_the_example_run(tmp_path, monkeypatch):
    env, job = code_with(tmp_path, monkeypatch, Box(OK))
    assert job.data["state"] == rj.AWAITING_APPROVAL
    assert "issue example at base: ran clean" in rj.status("jtest", jobs_dir=env.jobs)
    env.approve()
    assert any("issue example at base: ran clean" in c for c in env.confirms)
    assert json.loads((job.dir / rj.REPRO).read_text())["results"][0]["stdout"] == "0o600\n"


def test_a_failing_sandbox_never_stops_the_job_and_the_line_says_not_run(tmp_path, monkeypatch):
    env, job = code_with(tmp_path, monkeypatch, Box(RuntimeError("docker is down")))
    assert job.data["state"] == rj.AWAITING_APPROVAL
    assert "issue example at base: not run" in rj.status("jtest", jobs_dir=env.jobs)


def test_what_the_example_does_never_changes_the_draft(tmp_path, monkeypatch):
    shas = []
    for i, box in enumerate([Box(OK), Box(BAD), Box(RuntimeError("down"))]):
        env, _ = code_with(tmp_path / f"t{i}", monkeypatch, box, text=td.ISSUE + "\n\n" + issue("print(1)"))
        shas.append(env.sha())
    assert len(set(shas)) == 1


def test_a_result_for_another_issue_is_not_shown_as_this_ones(tmp_path, monkeypatch):
    env, job = code_with(tmp_path, monkeypatch, Box(OK))
    job.data["inputs"]["issue"] = "an issue the example was not made for"
    assert rj.repro_lines(job) == ["issue example at base: not run"]


def test_a_job_made_before_this_has_no_file_and_no_line(tmp_path, monkeypatch):
    env, job = code_with(tmp_path, monkeypatch, Box(OK))
    (job.dir / rj.REPRO).unlink()
    assert rj.repro_lines(job) == []


# ---- review fixes -------------------------------------------------------------------------------------------------

def test_a_block_inside_a_list_item_is_dedented_so_it_does_not_raise_an_indentation_error():
    text = "1. Run this:\n   ```python\n   import x\n   print(x.f())\n   ```\n"
    ((_, code),) = rp.blocks(text)
    assert code == "import x\nprint(x.f())\n"


@pytest.mark.parametrize("info", ["python title=x", "{.python}", "python {1,2}", "Python3", "py"])
def test_a_fence_info_string_with_more_than_the_language_is_still_python(info):
    assert len(rp.blocks(f"```{info}\nx = 1\n```")) == 1
    assert rp.blocks("```pythonista\nx = 1\n```") == [] and rp.blocks("```json\n{}\n```") == []


def test_output_is_cut_in_bytes_not_characters_and_never_in_half_a_character():
    big = {"exit_code": 0, "stdout": "é" * 3000, "stderr": "", "timed_out": False}   # 6000 bytes
    (r,) = rp.run(Path("."), issue("print(1)"), {}, runner=Box(big))
    assert len(r["stdout"].encode("utf-8")) <= rp.MAX_OUT and r["stdout"] == "é" * (rp.MAX_OUT // 2)
    bad = {"exit_code": 1, "stdout": "", "stderr": "ValueError: " + "é" * 400, "timed_out": False}
    (r,) = rp.run(Path("."), issue("print(1)"), {}, runner=Box(bad))
    assert len(r["stderr_last_line"].encode("utf-8")) <= 300


def test_the_job_notes_what_was_run_or_that_it_could_not_run(tmp_path, monkeypatch):
    env, job = code_with(tmp_path / "a", monkeypatch, Box(OK, BAD), text=td.ISSUE + "\n\n" + issue("a = 1", "b = 2"))
    (n,) = [e for e in job.data["log"] if e["what"] == "repro"]
    assert n["blocks"] == 2 and n["statuses"] == ["ok", "raised"]
    env, job = code_with(tmp_path / "b", monkeypatch, Box(RuntimeError("down")))
    (n,) = [e for e in job.data["log"] if e["what"] == "repro"]
    assert n["blocks"] is None and n["statuses"] is None


def test_even_a_failure_inside_the_job_step_leaves_a_not_run_line_and_the_job_goes_on(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("anything")
    monkeypatch.setattr(rp, "run", boom)
    env, job = code_with(tmp_path, monkeypatch, Box())
    assert job.data["state"] == rj.AWAITING_APPROVAL
    assert "issue example at base: not run" in rj.status("jtest", jobs_dir=env.jobs)


def test_repro_lines_never_raise_on_a_broken_job():
    assert rj.repro_lines(object()) == [] and rj.repro_lines(None) == []
