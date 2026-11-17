"""SPEC_EXAMPLE_GATE PR 3, the issue writer: the `examples` and `no_examples` fields, the RunExample tool, the gate that runs every example
on the frozen commit (one rejection for static and example problems), the tier moves, the block the harness writes into the issue,
the pinned image and the confirmation screen. The model is a fake, the runner is a local process on the frozen snapshot; the container
itself is in tests/test_examples_sandbox.py."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_drafter as td  # noqa: E402
from test_issue_writer import call, text, tool_answers  # noqa: E402

from codetask import examples as ex  # noqa: E402
from codetask import issue_writer as iw  # noqa: E402
from models.fake import StrictScriptedChatModel  # noqa: E402
from router import example_gate as eg  # noqa: E402
from router import issue as ri  # noqa: E402
from router import job as rj  # noqa: E402
from runner import load_config  # noqa: E402
from tools.sandbox import SandboxUnavailable  # noqa: E402

ENV = "pyenv"
IMAGE = "sha256:" + "ab" * 32
SAME = {"id": "e1", "tier": "same", "says": "Two prices and a discount of 1 give 4", "setup": "from src.shop import total",
        "run": "total([2, 3], 1)", "expect": 4}
AFTER = {"id": "e2", "tier": "after", "says": "A discount larger than the sum floors at 0", "setup": "from src.shop import total",
         "run": "total([1], 5)", "expect": 0}
ISSUE = "\n".join(["total() never goes below zero", "", "A discount larger than the sum gives 0.",
                   "1. `total([1], 5)` is `0`.", "", "Nothing else changes: the other totals.", "",
                   "Tests: the example above.", f"Environment: {ENV}"])
REPLY = "total() tidak akan pernah di bawah nol."


def args(examples=(SAME, AFTER), issue=ISSUE, **kw):
    return {"reply": REPLY, "issue": issue, "clashes": [], "questions": [], "touches": ["def total"],
            "examples": list(examples), **kw}


def submit(id="s", **kw):
    return call("SubmitIssue", args(**kw), id)


def try_it(run, id="t", **kw):
    return call("RunExample", {"setup": "from src.shop import total", "run": run, **kw}, id)


class Runs:
    def __init__(self, fail=None):
        self.calls, self.fail = 0, fail

    def __call__(self, tree, scfg):
        def run(argv):
            self.calls += 1
            if self.fail:
                raise self.fail
            r = subprocess.run([sys.executable, *argv[1:]], capture_output=True, text=True, timeout=120, cwd=str(tree))
            return {"stdout": r.stdout, "stderr": r.stderr, "exit_code": r.returncode}
        return run, str(tree)


def make_repo(tmp_path):
    repo = tmp_path / "demo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "shop.py").write_text(td.BUGGY)
    td.git(tmp_path, "init", "-q", str(repo))
    td.git(repo, "add", "-A")
    td.git(repo, "commit", "-qm", "base")
    return repo


def cfg(repo, runner="pytest", tools=("list_files", "search_files", "read_file", "run_example"), **turn):
    c = load_config()
    c["roles"]["issue_writer"]["model"] = "fake:scripted"
    c["issue_writer"]["repos"] = {"demo": {"path": str(repo), "environment": ENV}}
    c["issue_writer"]["turn"].update(turn)
    c["sandbox"] = {"environments": {ENV: {"image": None, **({"runner": runner} if runner != "pytest" else {})}}}
    c["tools"]["issue_writer"] = list(tools)
    return c


class Env:
    def __init__(self, tmp_path, script, *, runs=None, runner="pytest", **kw):
        self.repo, self.jobs = make_repo(tmp_path), tmp_path / "jobs"
        self.model = StrictScriptedChatModel(script=list(script))
        self.cfg, self.confirms, self.said = cfg(self.repo, runner, **kw), [], []
        self.runs = runs or Runs()

        def yes(t):
            self.confirms.append(t)
            return True
        self.deps = rj.Deps(confirm=yes, get_key=lambda: "unused", isatty=lambda: True, models={"issue_writer": self.model},
                            clock=lambda: "2026-11-17T12:00:00Z", echo=self.said.append, example_runner=self.runs)

    def new(self, message="total tidak boleh negatif"):
        return ri.new(repo="demo", message=message, cfg=self.cfg, deps=self.deps, jobs_dir=self.jobs, job_id="ji")

    def reply(self, message="oke"):
        return ri.reply("ji", message, cfg=self.cfg, deps=self.deps, jobs_dir=self.jobs)

    def job(self):
        return rj.open_job("ji", self.jobs)


@pytest.fixture(autouse=True)
def pinned(monkeypatch):
    monkeypatch.setattr(rj, "environment_pin", lambda cfg, name, root=None: (IMAGE, None))
    monkeypatch.setattr(rj, "environment_changed", lambda job, cfg: None)


# ---- RunExample --------------------------------------------------------------------------------------------------------

def test_run_example_gives_the_real_value_labelled_as_data(tmp_path):
    env = Env(tmp_path, [try_it("total([1], 5)"), submit()])
    env.new()
    answer = tool_answers(env.model.calls[1])[0]
    assert answer == f"RunExample result {ex.RUN_LABEL}: value -4"


def test_run_example_shows_a_raise_a_non_json_value_and_a_form_error(tmp_path):
    env = Env(tmp_path, [call("RunExample", {"setup": "from src.shop import total", "run": "total([1, 'x'], 1)"}, "a"),
                         call("RunExample", {"setup": "from src.shop import total", "run": "{total}"}, "b"),
                         call("RunExample", {"setup": "x = 1", "run": "x" * 500}, "c"), submit()])
    env.new()
    a, b, c = tool_answers(env.model.calls[3])[:3]
    assert "raised TypeError" in a and "not JSON (a set)" in b and a.startswith("RunExample result") and c.startswith("Rejected")


def test_run_example_with_overrides_is_tried_as_a_whatif(tmp_path):
    (tmp_path / "x").mkdir()
    env = Env(tmp_path, [call("RunExample", {"setup": "from src.shop import total", "run": "total([1], 1)",
                                             "overrides": {"src.shop.NOPE": 1}}, "a"), submit()])
    env.new()
    assert "raised AttributeError" in tool_answers(env.model.calls[1])[0]


def test_at_most_sixteen_tries_in_a_turn_and_the_count_comes_from_the_memo(tmp_path):
    tries = [try_it(f"total([{i}], 0)", id=f"t{i}") for i in range(17)]
    env = Env(tmp_path, [*tries, submit()], max_steps=24)
    env.new()
    answers = tool_answers(env.model.calls[-1])
    assert answers[15].startswith("RunExample result") and answers[16].startswith("Refused: at most 16")
    assert env.runs.calls == 16 + 2                    # 16 tries (the 17th is refused before it runs), then the gate's two passes


def test_run_example_is_not_offered_or_run_without_its_permission_or_without_a_runner(tmp_path):
    env = Env(tmp_path, [try_it("total([1], 5)"), submit()], tools=("list_files", "search_files", "read_file"))
    env.new()
    assert "RunExample" not in {t.__name__ for t in env.model.bound_tools}
    assert tool_answers(env.model.calls[1])[0].startswith("Refused: RunExample is not offered") and env.runs.calls == 2
    env = Env(tmp_path / "n", [submit(examples=())], runner="vitest")
    env.new()
    assert "RunExample" not in {t.__name__ for t in env.model.bound_tools} and env.runs.calls == 0


def test_run_example_is_offered_where_the_environment_runs_examples(tmp_path):
    env = Env(tmp_path, [submit()])
    env.new()
    assert {t.__name__ for t in env.model.bound_tools} == {"ListFiles", "SearchFiles", "ReadFile", "RunExample", "SubmitIssue"}


def test_an_unavailable_sandbox_at_a_try_is_said_and_the_submit_then_blocks_the_job(tmp_path):
    env = Env(tmp_path, [try_it("total([1], 5)"), submit()], runs=Runs(fail=SandboxUnavailable("docker is down")))
    job = env.new()
    assert "the sandbox is not available" in tool_answers(env.model.calls[1])[0]
    assert job.data["state"] == ri.BLOCKED and job.data["log"][-1]["reason"].startswith("sandbox_unavailable")


# ---- the gate ----------------------------------------------------------------------------------------------------------

def test_examples_that_hold_are_written_into_the_issue_and_kept_as_the_cards_data(tmp_path):
    env = Env(tmp_path, [submit()])
    job = env.new()
    stored = (job.dir / ri.ISSUE).read_text()
    present, examples, problems = eg.extract(stored)
    assert present and problems == [] and examples == [SAME, AFTER] and stored.rstrip().endswith(f"Environment: {ENV}")
    card = [m for m in job.data["conversation"] if m["from"] == "writer"][0]["examples"]
    assert [(r["id"], r["status"]) for r in card["results"]] == [("e1", "pass"), ("e2", "unchecked")]
    text_ = rj.status("ji", jobs_dir=env.jobs)
    assert "examples at base: e1 same: pass; e2 after: gives -4 now" in text_ and ex.RUN_LABEL in text_


def test_a_wrong_number_is_one_rejection_with_the_real_value_and_the_static_problem_too(tmp_path):
    bad = "\n".join(["total() never goes below zero", "Nothing else changes: x", f"Environment: {ENV}"])    # no Tests paragraph
    env = Env(tmp_path, [submit(examples=({**SAME, "expect": 5}, AFTER), issue=bad), submit(id="s2")])
    job = env.new()
    first = tool_answers(env.model.calls[1])[0]
    assert first.count("Rejected (") == 1 and "starts with `Tests:`" in first
    assert "example e1 (same) fail: expects 5; the code gave 4" in first
    assert job.data["state"] == ri.AWAITING_HUMAN


def test_an_after_that_already_passes_is_refused_and_a_tier_move_is_shown_on_the_card(tmp_path):
    moved = {**AFTER, "id": "e1", "tier": "after", "run": "total([2, 3], 1)", "expect": 4}      # the same example, as `after`
    no_tests = "\n".join(["total() never goes below zero", "Nothing else changes: x", f"Environment: {ENV}"])
    env = Env(tmp_path, [submit(examples=(SAME,), issue=no_tests), submit(id="s2", examples=(moved,)),
                         submit(id="s3", examples=(SAME, AFTER))])
    job = env.new()
    assert "already passes on the base: it is a `same`" in tool_answers(env.model.calls[2])[-1]
    card = [m for m in job.data["conversation"] if m["from"] == "writer"][0]["examples"]
    assert card["tier_moves"] == [{"id": "e1", "from": "same", "to": "after"}, {"id": "e1", "from": "after", "to": "same"}]
    text_ = rj.status("ji", jobs_dir=env.jobs)
    assert "example e1: written as same, sent again as after" in text_ and "example e1: written as after, sent again as same" in text_


def test_no_examples_needs_a_reason_and_is_kept_on_the_card(tmp_path):
    env = Env(tmp_path, [submit(examples=()), submit(id="s2", examples=(), no_examples="a copy change, no behaviour")])
    job = env.new()
    assert "needs examples, or no_examples with the reason" in tool_answers(env.model.calls[1])[0]
    assert "no examples: a copy change, no behaviour" in rj.status("ji", jobs_dir=env.jobs)
    assert eg.extract((job.dir / ri.ISSUE).read_text())[0] is False and env.runs.calls == 0


def test_examples_and_no_examples_together_and_a_long_reason_are_refused(tmp_path):
    env = Env(tmp_path, [submit(no_examples="both"), submit(id="s2", examples=(), no_examples="x" * 161), submit(id="s3")])
    env.new()
    assert "not both" in tool_answers(env.model.calls[1])[0] and "no_examples has 161 characters" in tool_answers(env.model.calls[2])[-1]


def test_an_example_of_the_wrong_form_or_that_calls_nothing_is_refused_before_running(tmp_path):
    env = Env(tmp_path, [submit(examples=({**SAME, "wat": 1},)), submit(id="s2", examples=({**SAME, "setup": "r = 4", "run": "r"},)),
                         submit(id="s3")])
    env.new()
    assert "unknown key" in tool_answers(env.model.calls[1])[0]
    assert "imports no module of the repository" in tool_answers(env.model.calls[2])[-1]


def test_a_block_the_writer_wrote_is_replaced_by_the_harnesss_and_a_malformed_fence_is_refused(tmp_path):
    own = ISSUE.replace("Tests:", "```argus-examples\n[]\n```\n\nTests:")
    env = Env(tmp_path, [submit(issue=own)])
    job = env.new()
    stored = (job.dir / ri.ISSUE).read_text()
    assert stored.count("```argus-examples") == 1 and eg.extract(stored)[1] == [SAME, AFTER]       # the fields, never the writer's own
    again = Env(tmp_path / "again", [submit(issue=stored.strip())]).new()                            # a stored issue given back
    assert (again.dir / ri.ISSUE).read_text().count("```argus-examples") == 1
    broken = ISSUE.replace("Tests:", "```argus-examples json\n[]\n```\n\nTests:")
    env3 = Env(tmp_path / "three", [submit(issue=broken), submit(id="s2")])
    env3.new()
    assert "must not hold an argus-examples fence" in tool_answers(env3.model.calls[1])[0]


def test_an_environment_without_an_example_runner_asks_for_none_and_refuses_some(tmp_path):
    env = Env(tmp_path, [submit(), submit(id="s2", examples=())], runner="vitest")
    job = env.new()
    assert "no example runner" in tool_answers(env.model.calls[1])[0] and env.runs.calls == 0
    assert "examples: not run (environment without an example runner)" in rj.status("ji", jobs_dir=env.jobs)
    assert eg.extract((job.dir / ri.ISSUE).read_text())[0] is False


def test_a_reply_without_an_issue_needs_no_examples(tmp_path):
    env = Env(tmp_path, [call("SubmitIssue", {"reply": "Jawaban saja.", "issue": ""}, "s")])
    assert env.new().data["state"] == ri.AWAITING_HUMAN and env.runs.calls == 0


def test_an_unavailable_sandbox_at_the_gate_blocks_the_turn_as_sandbox_unavailable(tmp_path):
    env = Env(tmp_path, [submit()], runs=Runs(fail=SandboxUnavailable("docker is down")))
    job = env.new()
    st = job.data["stages"]["w1"]
    assert job.data["state"] == ri.BLOCKED and st["status"] == iw.BLOCKED
    assert job.data["log"][-1]["reason"].startswith("sandbox_unavailable: docker is down") and not (job.dir / ri.ISSUE).exists()


def test_a_pass_that_prints_nothing_is_a_rejection_for_the_writer_not_the_end_of_its_job(tmp_path):
    class Silent(Runs):
        def __call__(self, tree, scfg):
            return (lambda argv: {"stdout": "", "stderr": "", "exit_code": 1}), str(tree)      # an example that ends its own process
    env = Env(tmp_path, [submit(), submit(id="s2")], runs=Silent())
    job = env.new()
    assert "no example printed a result: the pass was cut off" in tool_answers(env.model.calls[1])[0]
    assert job.data["state"] == ri.WRITE_FAILED and job.data["stages"]["w1"]["status"] == iw.FAILED       # replyable, never BLOCKED


def test_what_the_code_printed_is_labelled_as_data_in_a_rejection(tmp_path):
    env = Env(tmp_path, [submit(examples=({**SAME, "expect": 5},)), submit(id="s2")])
    env.new()
    first = tool_answers(env.model.calls[1])[0]
    assert "the code gave 4" in first and ex.RUN_LABEL in first


# ---- the screen, the pinned image, the versions -----------------------------------------------------------------------------

def test_the_screen_says_the_models_code_runs_in_the_sandbox_and_names_the_image(tmp_path):
    env = Env(tmp_path, [submit()])
    job = env.new()
    assert "example code written by the model RUNS in the sandbox" in env.confirms[0] and "no longer read-only" in env.confirms[0]
    assert job.data["environment_image"] == IMAGE and IMAGE[:19] in env.confirms[0]
    node = Env(tmp_path / "n", [submit(examples=())], runner="vitest")
    node.new()
    assert "RUNS in the sandbox" not in node.confirms[0] and "environment_image" not in node.job().data


def test_a_changed_image_refuses_the_next_turn_and_a_job_from_before_the_gate_is_pinned_then(tmp_path, monkeypatch):
    env = Env(tmp_path, [submit(), submit(id="s2")])
    env.new()
    monkeypatch.setattr(rj, "environment_changed", lambda job, cfg: "the image changed")
    with pytest.raises(rj.Refused, match="the image changed"):
        env.reply()
    assert env.job().data["state"] == ri.AWAITING_HUMAN and len(env.model.calls) == 1
    old = env.job()
    del old.data["environment_image"]
    old.save()
    monkeypatch.setattr(rj, "environment_changed", lambda job, cfg: None)
    env.reply()
    assert env.job().data["environment_image"] == IMAGE


def test_the_versions_of_the_gate_and_the_tool_carry_the_image(monkeypatch):
    monkeypatch.setattr("tools.sandbox.tool_version", lambda cfg, envs=(): f"1:img;{envs[0]}=ID1")
    assert iw._tool_version({}, "pyenv") == "1:img;pyenv=ID1"
    assert iw.VERSIONS["SubmitIssue"] == "6" and iw.VERSIONS["RunExample"] == "1"


# ---- the review of PR 3 (Opus) -----------------------------------------------------------------------------------------------

def system_text(env):
    return text(env.model.calls[0]["messages"][0])


def test_the_prompt_asks_for_examples_and_names_run_example_only_where_they_apply(tmp_path):
    py = Env(tmp_path, [submit()])
    py.new()
    assert "Give `examples` (this environment runs them)" in system_text(py) and "Try each one with RunExample" in system_text(py)
    nope = Env(tmp_path / "np", [submit()], tools=("list_files", "search_files", "read_file"))
    nope.new()
    assert "Give `examples`" in system_text(nope) and "RunExample" not in system_text(nope)
    node = Env(tmp_path / "node", [submit(examples=())], runner="vitest")
    node.new()
    assert "no example runner: leave `examples` and `no_examples` empty" in system_text(node) and "Give `examples`" not in system_text(node)


def test_an_example_renamed_after_a_rejection_is_still_a_tier_move(tmp_path):
    wrong = {**SAME, "id": "e2", "expect": 47}
    dodge = {**SAME, "id": "e3", "tier": "after", "expect": 47}               # the same call, another id, another tier
    env = Env(tmp_path, [submit(examples=(SAME, wrong)), submit(id="s2", examples=(SAME, dodge))])
    job = env.new()
    card = [m for m in job.data["conversation"] if m["from"] == "writer"][0]["examples"]
    assert {"id": "e3", "from": "same", "to": "after"} in card["tier_moves"]


def test_a_half_stripped_block_leaves_no_example_lines_in_the_issue(tmp_path):
    env = Env(tmp_path, [submit(), submit(id="s2")])
    stored = (env.new().dir / ri.ISSUE).read_text()
    broken = stored.replace("[\n", "[\n```\n", 1)                              # a stray fence inside the stored block
    env2 = Env(tmp_path / "two", [submit(issue=broken.strip()), submit(id="s2")])
    env2.new()
    assert "must not hold an argus-examples fence or example lines" in tool_answers(env2.model.calls[1])[0]


def test_the_length_message_names_the_examples_block(tmp_path):
    big = [{**SAME, "id": f"e{i}", "says": "x" * 150, "setup": "from src.shop import total\n" + "# " + "y" * 500} for i in range(1, 6)]
    long_issue = ISSUE.replace("A discount larger", "z" * 6500 + " A discount larger")
    env = Env(tmp_path, [submit(issue=long_issue, examples=big), submit(id="s2")])
    env.new()
    assert "examples block the harness adds" in tool_answers(env.model.calls[1])[0]


def test_a_pin_that_cannot_be_made_abandons_the_new_job_with_its_own_reason(tmp_path, monkeypatch):
    monkeypatch.setattr(rj, "environment_pin", lambda cfg, name, root=None: (None, "sandbox environment 'pyenv' has no image"))
    env = Env(tmp_path, [submit()])
    with pytest.raises(rj.Refused, match="has no image"):
        env.new()
    assert env.job().data["state"] == ri.ABANDONED and "has no image" in env.job().data["log"][-1]["reason"]


def test_the_memo_versions_carry_the_image_into_the_loop_and_the_permission_is_checked_in_the_tool(tmp_path, monkeypatch):
    seen = {}
    real = iw.tool_loop
    monkeypatch.setattr(iw, "tool_loop", lambda *a, **k: (seen.update(k["versions"]), real(*a, **k))[1])
    monkeypatch.setattr("tools.sandbox.tool_version", lambda cfg, envs=(): "1:img;pyenv=ID1")
    env = Env(tmp_path, [submit()])
    env.new()
    assert seen["SubmitIssue"] == "6:1:img;pyenv=ID1" and seen["RunExample"] == "1:1:img;pyenv=ID1"
    sup = iw.ExampleSupport(env.cfg, "issue_writer", ENV, env.repo, "r", type("L", (), {"emit": lambda *a, **k: None})(),
                            type("M", (), {"get": lambda s, k: None, "put": lambda s, k, v: None})())
    assert sup.versions["SubmitPRD"] == "2:1:img;pyenv=ID1"
    sup.allowed = []
    assert sup.run_example({"setup": "x", "run": "1"}).startswith("Denied")


def test_the_count_of_tries_continues_in_a_new_support_object_on_the_same_memo(tmp_path):
    store = {}

    class Memo:
        def get(self, k):
            return store.get(k)

        def put(self, k, v):
            store[k] = v
    log = type("L", (), {"emit": lambda *a, **k: None})()
    repo = make_repo(tmp_path)
    c = cfg(repo)
    first = iw.ExampleSupport(c, "issue_writer", ENV, repo, "r1", log, Memo(), Runs())
    for i in range(16):
        assert first.run_example({"setup": "from src.shop import total", "run": f"total([{i}], 0)"}).startswith("RunExample result")
    resumed = iw.ExampleSupport(c, "issue_writer", ENV, repo, "r1", log, Memo(), Runs())            # a resume: a new object, the same memo
    assert resumed.run_example({"setup": "from src.shop import total", "run": "total([1], 0)"}).startswith("Refused: at most 16")


def test_the_block_counts_toward_the_issue_limit_and_the_chat_card_says_the_code_runs(tmp_path):
    from router import chat_actions as ca
    c = cfg(make_repo(tmp_path))
    assert "kode contoh buatan model dijalankan di sandbox" in ca.Actions.runs_code(c, ENV)["runs_code"]
    c["sandbox"]["environments"][ENV]["runner"] = "vitest"
    assert ca.Actions.runs_code(c, ENV) == {} and ca.Actions.runs_code(c, "unknown") == {}
