"""SPEC_EXAMPLE_GATE PR 3, the PRD writer: `examples` and `no_examples` on every item, the first item's examples run on the frozen commit
(the later ones get the form check only: their base commit is the one the item before leaves, so their real gate is the code job's
intake), an example of a later item that uses a name an earlier item creates is `after`, the block in every issue file, RunExample, the
pinned image and the screen. The model is a fake; the runner is a local process on the frozen snapshot."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import test_example_writer as tew  # noqa: E402
import test_drafter as td  # noqa: E402
from test_example_writer import AFTER, ENV, IMAGE, SAME, Runs, pinned  # noqa: E402, F401
from test_issue_writer import call, tool_answers  # noqa: E402

from codetask import examples as ex  # noqa: E402
from codetask import prd_writer as pw  # noqa: E402
from models.fake import StrictScriptedChatModel  # noqa: E402
from router import example_gate as eg  # noqa: E402
from router import job as rj  # noqa: E402
from router import prd as rp  # noqa: E402
from router import prd_job as pj  # noqa: E402
from tools.sandbox import SandboxUnavailable  # noqa: E402

PRD = "Goal: the total never below zero, then a formatted total.\n\nThe contract: issue 1 makes `show_floor`; issue 2 uses it.\n"
LATER = {"id": "e1", "tier": "same", "says": "The floor helper keeps a plain total", "setup": "from src.shop import show_floor",
         "run": "show_floor([2, 3], 1)", "expect": 4}


def issue_text(title="total() never goes below zero"):
    return "\n".join([title, "", "A discount larger than the sum gives 0.", "1. `total([1], 5)` is `0`.", "",
                      "Nothing else changes: the other totals.", "", "Tests: the example above.", f"Environment: {ENV}"])


def item(title, touches, creates=(), examples=(), no_examples=""):
    return {"issue": issue_text(title), "paths": [], "fields": [], "touches": list(touches), "creates": list(creates),
            "clashes": [], "clash_check": "", "examples": list(examples), "no_examples": no_examples}


def args(items=None):
    items = [item("total() never goes below zero", ["def total"], ["show_floor"], [SAME, AFTER]),
             item("Show the floor", ["show_floor"], [], [], "a copy change")] if items is None else items
    return {"reply": "Dua issue: lantai nol, lalu tampilannya.", "prd_md": PRD, "items": items, "questions": []}


def submit(a=None, id="s"):
    return call("SubmitPRD", args() if a is None else a, id)


class Env:
    def __init__(self, tmp_path, script, runs=None):
        self.repo, self.jobs, self.queues = tew.make_repo(tmp_path), tmp_path / "jobs", tmp_path / "queues"
        self.model = StrictScriptedChatModel(script=list(script))
        self.cfg, self.said, self.screens = tew.cfg(self.repo), [], []
        self.cfg["prd_writer"]["turn"].update(max_steps=24)
        self.runs = runs or Runs()

        def yes(t):
            self.screens.append(t)
            return True
        self.deps = rj.Deps(confirm=yes, get_key=lambda: "unused", isatty=lambda: True, models={"issue_writer": self.model},
                            clock=lambda: "2026-11-17T12:00:00Z", echo=self.said.append, example_runner=self.runs)

    def new(self):
        return pj.new(repo="demo", message="dua perubahan", cfg=self.cfg, deps=self.deps, jobs_dir=self.jobs,
                      queues_dir=self.queues, job_id="jp")

    def job(self):
        return rj.open_job("jp", self.jobs)


def test_the_first_items_examples_run_and_every_issue_file_carries_its_block(tmp_path):
    env = Env(tmp_path, [submit()])
    job = env.new()
    assert job.data["state"] == pj.AWAITING_HUMAN
    d = pj.folder_of(job, "w1")
    one, two = (d / "issue-1.md").read_text(), (d / "issue-2.md").read_text()
    assert eg.extract(one)[1] == [SAME, AFTER] and eg.extract(two)[0] is False
    found, _ = rp.check(rp.read_folder(d), cfg=env.cfg, queues_dir=env.queues, jobs_dir=env.jobs)
    assert [t for lvl, t in found if lvl == rp.BLOCK] == []
    turn = job.data["prd_turns"][0]
    assert [r["status"] for r in turn["examples"][0]["results"]] == ["pass", "unchecked"] and turn["examples"][1]["no_examples"]
    text = "\n".join(pj.status_lines(job))
    assert "examples at base: e1 same: pass; e2 after: gives -4 now" in text and "no examples: a copy change" in text


def test_a_later_items_examples_are_checked_for_form_only_and_not_run(tmp_path):
    later = {**LATER, "setup": "from src.shop import total", "run": "total([2, 3], 99)", "expect": 12345}    # wrong on today's code
    env = Env(tmp_path, [submit(args([item("one", ["def total"], ["show_floor"], [SAME]),
                                      item("two", ["show_floor"], [], [later])]))])
    job = env.new()
    assert job.data["state"] == pj.AWAITING_HUMAN and env.runs.calls == 2        # item 1: two passes; item 2: none
    bad = {**later, "wat": 1}
    env2 = Env(tmp_path / "b", [submit(args([item("one", ["def total"], ["show_floor"], [SAME]), item("two", ["show_floor"], [], [bad])])),
                                submit(id="s2")])
    env2.new()
    assert "item 2: example 1: unknown key" in tool_answers(env2.model.calls[1])[0]


def test_a_later_example_that_uses_a_name_an_earlier_item_creates_must_be_after(tmp_path):
    env = Env(tmp_path, [submit(args([item("one", ["def total"], ["show_floor"], [SAME]),
                                      item("two", ["show_floor"], [], [LATER])])),
                         submit(args([item("one", ["def total"], ["show_floor"], [SAME]),
                                      item("two", ["show_floor"], [], [{**LATER, "tier": "after"}])]), id="s2")])
    job = env.new()
    assert "item 2: example e1 uses 'show_floor', which an earlier item creates: its tier is `after`" in tool_answers(env.model.calls[1])[0]
    assert job.data["state"] == pj.AWAITING_HUMAN


def test_a_wrong_first_item_example_is_refused_with_the_real_value(tmp_path):
    env = Env(tmp_path, [submit(args([item("one", ["def total"], [], [{**SAME, "expect": 5}]), item("two", ["def total"], [], [], "none")])),
                         submit(id="s2")])
    env.new()
    assert "item 1: example e1 (same) fail: expects 5; the code gave 4" in tool_answers(env.model.calls[1])[0]


def test_an_item_with_neither_examples_nor_a_reason_is_refused(tmp_path):
    env = Env(tmp_path, [submit(args([item("one", ["def total"], [], [SAME]), item("two", ["def total"], [], [])])), submit(id="s2")])
    env.new()
    assert "item 2: an issue needs examples, or no_examples with the reason" in tool_answers(env.model.calls[1])[0]


def test_run_example_is_offered_to_the_prd_writer_and_the_screen_and_the_pin_say_so(tmp_path):
    env = Env(tmp_path, [call("RunExample", {"setup": "from src.shop import total", "run": "total([1], 5)"}, "t"), submit()])
    job = env.new()
    assert "RunExample" in {t.__name__ for t in env.model.bound_tools}
    assert tool_answers(env.model.calls[1])[0] == f"RunExample result {ex.RUN_LABEL}: value -4"
    assert "example code written by the model RUNS in the sandbox" in env.screens[0] and IMAGE[:19] in env.screens[0]
    assert job.data["environment_image"] == IMAGE


def test_an_unavailable_sandbox_blocks_the_prd_turn_as_sandbox_unavailable(tmp_path):
    env = Env(tmp_path, [submit()], runs=Runs(fail=SandboxUnavailable("docker is down")))
    job = env.new()
    assert job.data["state"] == pj.BLOCKED and job.data["log"][-1]["reason"].startswith("sandbox_unavailable")


def test_an_environment_without_a_runner_needs_no_examples_in_a_prd(tmp_path):
    env = Env(tmp_path, [submit(args([item("one", ["def total"], [], []), item("two", ["def total"], [], [])]))])
    env.cfg["sandbox"]["environments"][ENV]["runner"] = "vitest"
    job = env.new()
    assert job.data["state"] == pj.AWAITING_HUMAN and env.runs.calls == 0 and "RUNS in the sandbox" not in env.screens[0]
