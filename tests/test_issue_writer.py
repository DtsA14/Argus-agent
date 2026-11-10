"""SPEC_ISSUE_WRITER PR 1: the issue job (router/issue.py) and the writer's turn (codetask/issue_writer.py). The model is
a fake; the money goes through the real LLMCaller ledgers; the repository is a real git repository."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_drafter as td  # noqa: E402

from codetask import issue_writer as iw  # noqa: E402
from harness.llm import reconcile_ledger  # noqa: E402
from models.fake import StrictScriptedChatModel  # noqa: E402
from router import issue as ri  # noqa: E402
from router import job as rj  # noqa: E402
from router import stage_data as sd  # noqa: E402
from runner import load_config  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ENV = "pwa_node22"
FIRST = "Kartu job tambahin tanggal dibuat dong"
ISSUE = "\n".join(["The list page: the date under each job id", "", "Each job card shows the date it was made.",
                   "1. `9 Nov, 09:35 WIB` for `2026-11-09T02:35:12Z`.", "",
                   "Nothing else changes: the existing tests keep passing unchanged.", "",
                   "Tests: the date of each example.", f"Environment: {ENV}"])
REPLY = "Di kartu job akan muncul tanggal dibuat, misalnya 9 Nov, 09:35 WIB."


def submit_args(issue=ISSUE, reply=REPLY, clashes=(), questions=()):
    return {"reply": reply, "issue": issue, "clashes": list(clashes), "questions": list(questions)}


def call(name, args, id):
    return td.call(name, args, id)


def text(m):
    """A message's text, whether its content is a string or blocks (prompt caching marks the last one)."""
    c = m.content
    return c if isinstance(c, str) else "".join(b.get("text", "") for b in c if isinstance(b, dict))


def tool_answers(call_record):
    return [text(m) for m in call_record["messages"] if type(m).__name__ == "ToolMessage"]


READ = call("ReadFile", {"path": "src/list.test.js"}, "r")
SUBMIT = call("SubmitIssue", submit_args(clashes=[{"file": "src/list.test.js", "line": 2, "why": "reads the cell"}],
                                         questions=["Pakai jam juga?"]), "s")


def make_repo(tmp_path):
    repo = tmp_path / "demo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "list.js").write_text("export const ID = 'id'\n")
    (repo / "src" / "list.test.js").write_text("test('id', () => {\n  expect(cell).toBe('id')\n})\n")
    td.git(tmp_path, "init", "-q", str(repo))
    td.git(repo, "add", "-A")
    td.git(repo, "commit", "-qm", "base")
    return repo


def cfg(repo, **turn):
    c = load_config()
    c["roles"]["issue_writer"]["model"] = "fake:scripted"
    c["issue_writer"]["repos"] = {"demo": {"path": str(repo), "environment": ENV}}
    c["issue_writer"]["turn"].update(turn)
    return c


class Env:
    def __init__(self, tmp_path, script, *, confirm=True, **turn):
        self.repo, self.jobs = make_repo(tmp_path), tmp_path / "jobs"
        self.model = StrictScriptedChatModel(script=list(script))
        self.cfg, self.confirms, self.said = cfg(self.repo, **turn), [], []

        def yes(text):
            self.confirms.append(text)
            return confirm
        self.deps = rj.Deps(confirm=yes, get_key=lambda: "unused", isatty=lambda: True,
                            models={"issue_writer": self.model}, clock=lambda: "2026-11-09T12:00:00Z",
                            echo=self.said.append)

    def new(self, message=FIRST, **kw):
        return ri.new(repo="demo", message=message, cfg=self.cfg, deps=self.deps, jobs_dir=self.jobs, job_id="ji",
                      **kw)

    def reply(self, message="Pakai jam juga", **kw):
        return ri.reply("ji", message, cfg=self.cfg, deps=self.deps, jobs_dir=self.jobs, **kw)

    def job(self):
        return rj.open_job("ji", self.jobs)

    def prompts(self):
        return ["\n".join(text(m) for m in c["messages"] if type(m).__name__ == "HumanMessage")
                for c in self.model.calls]


# ---- the job ----------------------------------------------------------------------------------------------------

def test_a_first_message_becomes_an_issue_after_reading_the_frozen_repository(tmp_path):
    env = Env(tmp_path, [READ, SUBMIT])
    job = env.new()
    assert job.data["kind"] == "issue" and job.data["state"] == ri.AWAITING_HUMAN and len(env.confirms) == 1
    assert (job.dir / ri.ISSUE).read_text() == ISSUE + "\n"
    human, writer = job.data["conversation"]
    assert (human["from"], human["text"]) == ("human", FIRST)
    assert (writer["from"], writer["text"], writer["stage"]) == ("writer", REPLY, "w1")
    assert writer["clashes"] == [{"file": "src/list.test.js", "line": 2, "why": "reads the cell"}]
    assert writer["questions"] == ["Pakai jam juga?"] and job.data["issue_sha256"] == writer["issue_sha256"]
    answers = tool_answers(env.model.calls[1])
    assert "expect(cell)" in answers[0]                       # the read tool saw the commit's file
    assert FIRST in env.prompts()[0] and "environment: pwa_node22" in env.prompts()[0]
    assert job.data["inputs"]["commit"] == subprocess.run(["git", "-C", str(env.repo), "rev-parse", "HEAD"],
                                                          capture_output=True, text=True).stdout.strip()
    text = rj.status("ji", jobs_dir=env.jobs)
    assert "AWAITING_HUMAN (issue)" in text and "clash: src/list.test.js:2" in text and "argus issue reply ji" in text


def test_the_turn_reads_the_frozen_commit_never_the_live_repository(tmp_path):
    env = Env(tmp_path, [SUBMIT, call("ReadFile", {"path": "src/list.js"}, "r2"),
                         call("ReadFile", {"path": "secret.txt"}, "r3"), call("SubmitIssue", submit_args(), "s2")])
    env.new()
    (env.repo / "src" / "list.js").write_text("export const ID = 'changed'\n")
    td.git(env.repo, "commit", "-qam", "later")
    (env.repo / "secret.txt").write_text("untracked\n")
    env.reply()
    answers = tool_answers(env.model.calls[-1])
    assert "'id'" in answers[-2] and "changed" not in answers[-2]
    assert "No such file" in answers[-1]


def test_a_reply_is_recorded_before_its_turn_and_the_turn_sees_the_last_issue(tmp_path, monkeypatch):
    env = Env(tmp_path, [SUBMIT, call("SubmitIssue", submit_args(reply="Sekarang dengan jam."), "s2")])
    env.new()
    real = iw.run_writer

    def stop(**kw):
        raise KeyboardInterrupt
    monkeypatch.setattr(iw, "run_writer", stop)
    with pytest.raises(KeyboardInterrupt):
        env.reply("Pakai jam juga")
    job = env.job()
    assert job.data["state"] == ri.WRITING and job.data["conversation"][-1]["text"] == "Pakai jam juga"
    monkeypatch.setattr(iw, "run_writer", real)
    job, _ = rj.resume("ji", cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs)
    assert job.data["state"] == ri.AWAITING_HUMAN and [m["from"] for m in job.data["conversation"]] == \
        ["human", "writer", "human", "writer"]
    p = env.prompts()[-1]
    assert "Pakai jam juga" in p and ISSUE.splitlines()[0] in p.split("Your current issue")[1]
    assert sorted(job.data["stages"]) == ["w1", "w2"]


@pytest.mark.parametrize("state", [ri.WRITING, ri.BLOCKED, rj.ABANDONED, ri.NEW])
def test_a_reply_is_taken_only_when_the_writer_waits_or_failed(tmp_path, state):
    env = Env(tmp_path, [SUBMIT])
    job = env.new()
    job.data["state"] = state
    job.save()
    with pytest.raises(rj.Refused, match="a reply is taken when"):
        env.reply()
    assert len(env.job().data["conversation"]) == 2


def test_a_failed_turn_is_tried_again_by_the_next_reply(tmp_path):
    bad = call("SubmitIssue", submit_args(issue="no title rules"), "b")
    env = Env(tmp_path, [bad, bad, bad, SUBMIT], max_submits=3)
    job = env.new()
    assert job.data["state"] == ri.WRITE_FAILED and not (job.dir / ri.ISSUE).exists()
    job = env.reply("Coba lagi")
    assert job.data["state"] == ri.AWAITING_HUMAN and (job.dir / ri.ISSUE).exists()


def test_only_a_repository_of_the_config_is_read(tmp_path):
    env = Env(tmp_path, [SUBMIT])
    for name in ("other", str(env.repo), "../demo"):
        with pytest.raises(rj.Refused, match="is not one of issue_writer.repos"):
            ri.new(repo=name, message=FIRST, cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs, job_id="ji")
    assert not env.jobs.exists() and env.model.calls == []


@pytest.mark.parametrize("message, why", [("", "empty"), ("   ", "empty"), ("x" * 4001, "more than 4000"),
                                          ("a\x07b", "control"), ("a b", "control"), ("a‮b", "control"),
                                          ("a\rb", "control")])
def test_a_bad_message_starts_nothing(tmp_path, message, why):
    env = Env(tmp_path, [SUBMIT])
    with pytest.raises(rj.Refused, match=why):
        env.new(message)
    assert not env.jobs.exists() and env.model.calls == []


def test_a_message_of_several_lines_and_tabs_is_taken(tmp_path):
    env = Env(tmp_path, [SUBMIT])
    text = "baris satu\nbaris dua\n\tkode dengan tab"
    assert env.new(text).data["conversation"][0]["text"] == text


def test_a_reply_longer_than_the_reply_limit_is_refused_and_not_recorded(tmp_path):
    env = Env(tmp_path, [SUBMIT])
    env.new()
    with pytest.raises(rj.Refused, match="more than 2000"):
        env.reply("x" * 2001)
    assert len(env.job().data["conversation"]) == 2 and env.job().data["state"] == ri.AWAITING_HUMAN


def test_not_confirmed_writes_nothing_and_spends_nothing(tmp_path):
    env = Env(tmp_path, [SUBMIT], confirm=False)
    with pytest.raises(rj.Refused, match="not confirmed"):
        env.new()
    assert env.job().data["state"] == rj.ABANDONED and env.model.calls == [] and env.job().data["stages"] == {}


# ---- money ------------------------------------------------------------------------------------------------------

def test_a_job_cap_that_cannot_fund_one_turn_starts_nothing(tmp_path):
    env = Env(tmp_path, [SUBMIT])
    env.cfg["issue_writer"]["max_usd"] = 0.05
    with pytest.raises(rj.Refused, match="does not fund one turn"):
        env.new()
    assert not env.jobs.exists()


def test_a_reply_is_refused_when_the_job_cap_left_cannot_fund_a_turn(tmp_path, monkeypatch):
    env = Env(tmp_path, [SUBMIT])
    env.new()
    monkeypatch.setattr(rj, "left_usd", lambda job: 0.05)
    with pytest.raises(rj.Refused, match="less than one turn"):
        env.reply()
    job = env.job()
    assert job.data["state"] == ri.AWAITING_HUMAN and len(job.data["conversation"]) == 2 and len(env.model.calls) == 1


def test_an_unpriced_model_is_refused_before_anything(tmp_path):
    env = Env(tmp_path, [SUBMIT])
    env.cfg["roles"]["issue_writer"]["model"] = "deepseek:no-such-model"
    with pytest.raises(rj.Refused, match="issue writer"):
        env.new()
    assert not env.jobs.exists()


def test_the_turn_spends_through_its_ledger(tmp_path):
    env = Env(tmp_path, [READ, SUBMIT])
    job = env.new()
    st = job.data["stages"]["w1"]
    _, totals = reconcile_ledger([json.loads(x) for x in (job.runs / st["run_id"] / "events.jsonl").read_text()
                                  .splitlines()])
    assert totals["calls"] == 2 and st["usd"] == pytest.approx(totals["usd"]) and rj.spent_nano(job) > 0


# ---- the gate ---------------------------------------------------------------------------------------------------

@pytest.fixture
def source(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.test.js").write_text("x\n")
    (tmp_path.parent / "outside.js").write_text("x\n")
    return tmp_path


def gate(source, **kw):
    return iw.issue_gate(submit_args(**kw), source=source, environment=ENV)


def test_tabs_and_a_tests_paragraph_with_its_condition_pass_and_the_stored_issue_fits_a_code_job(source):
    body = "\n".join(["Title", "\tcode with a tab", "Nothing else changes.", "Tests (with a fixed time): t"])
    issue = body + "\n" + "x" * (iw.MAX_ISSUE - 2 - len(body) - len(f"\nEnvironment: {ENV}")) + f"\nEnvironment: {ENV}"
    problems, r = gate(source, issue=issue)
    assert problems == [] and len(r["issue"]) <= iw.MAX_ISSUE


def test_a_good_issue_passes_the_gate(source):
    problems, r = gate(source, clashes=[{"file": "src/a.test.js", "line": 1, "why": "w"}], questions=["q?"])
    assert problems == [] and r["issue"] == ISSUE + "\n" and r["clashes"][0]["file"] == "src/a.test.js"


@pytest.mark.parametrize("kw, why", [
    ({"issue": "\n".join(["x" * 121, "Tests: t", f"Environment: {ENV}"])}, "title"),
    ({"issue": "\n".join(["Title", "Nothing else changes.", f"Environment: {ENV}"])}, "starts with `Tests:`"),
    ({"issue": "\n".join(["Title", "Nothing else changes.", "Testsuite x is slow", f"Environment: {ENV}"])},
     "starts with `Tests:`"),
    ({"issue": "\n".join(["Title", "Tests: t", f"Environment: {ENV}"])}, "starts with `Nothing else changes:`"),
    ({"issue": "x" * iw.MAX_ISSUE}, "more than"),
    ({"issue": "\n".join(["Title", "Tests: t", "Environment: other"])}, f"exactly `Environment: {ENV}`"),
    ({"issue": "\n".join(["Title", "Tests: t", f"Environment: {ENV}", "after"])}, "last line"),
    ({"issue": "\n".join(["Title‮", "Tests: t", f"Environment: {ENV}"])}, "control or format"),
    ({"issue": "x" * (iw.MAX_ISSUE + 1)}, "more than"),
    ({"reply": ""}, "reply is empty"),
    ({"reply": "x" * (iw.REPLY_MAX + 1)}, "more than"),
    ({"clashes": [{"file": "src/none.test.js", "line": 1, "why": "w"}]}, "not a file of the repository"),
    ({"clashes": [{"file": "../outside.js", "line": 1, "why": "w"}]}, "not a file of the repository"),
    ({"clashes": [{"file": "/etc/passwd", "line": 1, "why": "w"}]}, "not a file of the repository"),
    ({"clashes": [{"file": "src", "line": 1, "why": "w"}]}, "not a file of the repository"),
    ({"clashes": [{"file": "src/a.test.js", "line": -1, "why": "w"}]}, "whole number"),
    ({"clashes": [{"file": "src/a.test.js", "line": True, "why": "w"}]}, "whole number"),
    ({"clashes": [{"file": "src/a.test.js", "line": 1, "why": "two\nlines"}]}, "one line"),
    ({"clashes": [{"file": "src/a.test.js", "line": 1, "why": "w"}] * 11}, "at most 10"),
    ({"questions": ["q"] * 6}, "at most 5"),
    ({"questions": ["two\nlines"]}, "one line"),
])
def test_the_gate_refuses_each_rule(source, kw, why):
    problems, r = gate(source, **kw)
    assert r is None and any(why in p for p in problems), problems


def test_a_rejected_submit_is_told_why_and_the_next_one_counts(tmp_path):
    bad = call("SubmitIssue", submit_args(issue="Title\nNothing else changes.\nTests: t\nEnvironment: other"), "b")
    env = Env(tmp_path, [bad, SUBMIT])
    job = env.new()
    assert job.data["state"] == ri.AWAITING_HUMAN
    told = tool_answers(env.model.calls[1])
    assert told[-1].startswith("Rejected (1 problem(s)); 2 submit(s) left") and "Environment: pwa_node22" in told[-1]


def test_no_tool_that_writes_runs_or_reaches_the_network_is_offered(tmp_path):
    env = Env(tmp_path, [call("WriteFile", {"path": "src/x.js", "content": "x"}, "w"), SUBMIT])
    env.new()
    assert {t.__name__ for t in env.model.bound_tools} == {"ListFiles", "SearchFiles", "ReadFile", "SubmitIssue"}
    answers = tool_answers(env.model.calls[1])
    assert answers[0].startswith("Refused: WriteFile is not offered") and not (env.repo / "src" / "x.js").exists()
    assert env.cfg["tools"]["issue_writer"] == ["list_files", "search_files", "read_file"]


# ---- what the job shows, and what it never publishes ------------------------------------------------------------

def test_the_public_snapshot_keeps_the_job_and_never_the_conversation(tmp_path):
    env = Env(tmp_path, [SUBMIT])
    job = env.new()
    raw = json.loads(job.file.read_text())
    assert {e["what"] for e in raw["log"]} <= sd.LOG_WHAT          # an unknown entry would exclude the whole job
    published = json.dumps(sd.project_job(raw, "ji"))
    assert "conversation" not in published and FIRST not in published and REPLY not in published
    assert "inputs" not in published and json.loads(published)["kind"] == "issue"


def test_other_commands_refuse_an_issue_job(tmp_path):
    env = Env(tmp_path, [SUBMIT])
    env.new()
    with pytest.raises(rj.Refused):
        rj.judge("ji", cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs)
    with pytest.raises(rj.Refused):
        rj.reject("ji", "x", deps=env.deps, jobs_dir=env.jobs)
    assert rj.abandon("ji", "not needed", deps=env.deps, jobs_dir=env.jobs).data["state"] == rj.ABANDONED


def test_a_reply_to_a_job_of_another_kind_is_refused(tmp_path):
    env = Env(tmp_path, [SUBMIT])
    job = env.new()
    job.data["kind"] = "code"
    job.save()
    with pytest.raises(rj.Refused, match="not an issue job"):
        env.reply()


# ---- crash-resume of a turn across processes --------------------------------------------------------------------

PROC = ("import sys; sys.path[:0] = [sys.argv[1], sys.argv[1] + '/tests']; import test_issue_writer as t; "
        "sys.exit(t._proc(*sys.argv[2:]))")


def _proc(runs, repo, crash_at, resume):
    def prepare(run_dir):
        source = Path(run_dir) / "source"
        if not source.is_dir():
            import shutil
            shutil.copytree(repo, source, ignore=shutil.ignore_patterns(".git"))
        return source
    inputs = {"repo": "demo", "commit": "0" * 40, "environment": ENV, "previous_issue": None, "max_usd": 0.1,
              "conversation": [{"from": "human", "text": FIRST}]}
    r = iw.run_writer(run_id="wc", runs_dir=runs, cfg=rj.stage_config(cfg(repo), 0.1), inputs=inputs,
                      resume=resume == "1", crash_at=None if crash_at == "-" else crash_at, prepare=prepare)
    return 0 if r["status"] == iw.WRITTEN else 1


def _script(name, args, id):
    return {"tool_calls": [{"name": name, "args": args, "id": id}], "usage": {"input_tokens": 500, "output_tokens": 60}}


@pytest.mark.parametrize("point", ["issue_writer@after_llm", "issue_writer@after_tool:ReadFile",
                                   "issue_writer@after_tool:SubmitIssue", "work@after_commit"])
def test_a_crashed_turn_resumes_without_buying_again(tmp_path, point):
    repo = make_repo(tmp_path)
    script = [_script("ReadFile", {"path": "src/list.js"}, "r"), _script("SubmitIssue", submit_args(), "s")]
    if point == "issue_writer@after_llm":
        script.insert(0, script[0])                  # step 0's reply was not committed: it is bought again
    (tmp_path / "script.json").write_text(json.dumps(script))
    env = {**os.environ, "ARGUS_FAKE_SCRIPT": str(tmp_path / "script.json")}

    def go(crash, resume):
        return subprocess.run([sys.executable, "-c", PROC, str(ROOT), str(tmp_path / "runs"), str(repo), crash, resume],
                              cwd=ROOT, capture_output=True, text=True, env=env, timeout=300)
    r1 = go(point, "0")
    assert r1.returncode == 42, (r1.stdout[-2000:], r1.stderr[-2000:])
    r2 = go("-", "1")
    assert r2.returncode == 0, (r2.stdout[-2000:], r2.stderr[-2000:])
    evs = [json.loads(line) for line in (tmp_path / "runs" / "wc" / "events.jsonl").read_text().splitlines()]
    i = next(n for n, e in enumerate(evs) if e["event"] == "crash_simulated")
    committed = {e["step"] for e in evs[:i] if e["event"] == "step_committed" and e["kind"] == "llm"}
    rebought = {e["step"] for e in evs[i:] if e["event"] == "llm_call" and e.get("status") == "ok"}
    assert not committed & rebought
    assert reconcile_ledger(evs)[1]["unknown_after_crash"] == 0


# ---- added for the mutants --------------------------------------------------------------------------------------

def test_a_turn_the_job_cannot_fund_blocks_the_job_without_a_model_call(tmp_path, monkeypatch):
    env = Env(tmp_path, [SUBMIT, SUBMIT])
    env.new()
    job = env.job()
    with job.lock():
        job.data["conversation"].append({"from": "human", "at": "t", "text": "lagi"})
        job.move(ri.WRITING, env.deps, stage="w2")
        monkeypatch.setattr(rj, "left_usd", lambda j: 0.05)
        ri._turn(job, env.cfg, env.deps)
    assert job.data["state"] == ri.BLOCKED and "w2" not in job.data["stages"] and len(env.model.calls) == 1


def test_a_turn_with_nothing_to_spend_asks_no_model(tmp_path):
    repo = make_repo(tmp_path)
    model = StrictScriptedChatModel(script=[SUBMIT])
    inputs = {"repo": "demo", "commit": "0" * 40, "environment": ENV, "previous_issue": None, "max_usd": 0,
              "conversation": [{"from": "human", "text": FIRST}]}
    r = iw.run_writer(run_id="w0", runs_dir=tmp_path / "runs", cfg=rj.stage_config(cfg(repo), 0), inputs=inputs,
                      models={"issue_writer": model}, prepare=lambda d: repo)
    assert r["status"] == iw.FAILED_BUDGET and model.calls == []


def test_a_crash_between_the_turn_and_its_record_resumes_without_a_new_turn(tmp_path, monkeypatch):
    """code review: the turn's end was saved before its issue and reply; a crash between made resume buy w2."""
    env = Env(tmp_path, [READ, SUBMIT])
    real = rj.Job.move

    def crash(self, new, deps, **why):
        if new == ri.AWAITING_HUMAN:
            raise KeyboardInterrupt
        return real(self, new, deps, **why)
    monkeypatch.setattr(rj.Job, "move", crash)
    with pytest.raises(KeyboardInterrupt):
        env.new()
    monkeypatch.setattr(rj.Job, "move", real)
    job = env.job()
    assert job.data["state"] == ri.WRITING and job.data["stages"]["w1"].get("status") is None
    calls = len(env.model.calls)
    job, _ = rj.resume("ji", cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs)
    assert job.data["state"] == ri.AWAITING_HUMAN and sorted(job.data["stages"]) == ["w1"]
    assert len(env.model.calls) == calls                      # the committed run is replayed, nothing bought again
    assert [m["from"] for m in job.data["conversation"]] == ["human", "writer"]


def test_a_commit_the_copy_refuses_blocks_the_job_before_any_model_call(tmp_path):
    env = Env(tmp_path, [SUBMIT])
    os.symlink("list.js", env.repo / "src" / "link.js")
    td.git(env.repo, "add", "-A")
    td.git(env.repo, "commit", "-qm", "a symlink")
    job = env.new()
    assert job.data["state"] == ri.BLOCKED and "cannot be copied" in rj._why(job)["reason"] and env.model.calls == []


def test_an_unfunded_reply_is_refused_before_the_limits_and_the_key(tmp_path, monkeypatch):
    env = Env(tmp_path, [SUBMIT])
    env.new()
    shown = len(env.confirms)
    monkeypatch.setattr(rj, "left_usd", lambda job: 0.05)
    with pytest.raises(rj.Refused, match="less than one turn"):
        env.reply()
    assert len(env.confirms) == shown
    assert [e["what"] for e in env.job().data["log"]].count("limits_shown") == 1


# ---- PR 2: start (the handoff to a code job) ---------------------------------------------------------------------

class FakeCode:
    """rj.start_code as the handoff sees it: records the call; `how` makes it refuse before the job exists, refuse after
    making it (not confirmed: ABANDONED with no stage; intake: BLOCKED), or crash while the drafter runs."""

    def __init__(self, how="ok"):
        self.how, self.calls = how, []

    def __call__(self, **kw):
        self.calls.append(kw)
        if self.how == "refuse_before":
            raise rj.Refused("not priced; no job was created")
        job = rj.Job(Path(kw["jobs_dir"]) / kw["job_id"])
        state = {"ok": rj.AWAITING_APPROVAL, "not_confirmed": rj.ABANDONED, "blocked": rj.BLOCKED,
                 "crash": rj.DRAFTING}[self.how]
        stages = {} if self.how in ("not_confirmed", "blocked") else {
            "d1": {"kind": "draft", "run_id": f"{kw['job_id']}-d1", "cap_usd": 0.75}}
        with job.lock():
            job.data = {"job": kw["job_id"], "kind": "code", "state": state, "created_at": "t", "max_usd": kw["max_usd"],
                        "inputs": {"repo": str(Path(kw["repo"]).resolve()), "commit": kw["commit"],   # as start_code
                                   "issue": kw["issue"].strip()}, "stages": stages,
                        "log": []}
            job.save()
        if self.how == "not_confirmed":
            raise rj.Refused("not confirmed; nothing was started")
        if self.how == "blocked":
            raise rj.Refused("intake failed: x")
        if self.how == "crash":
            raise KeyboardInterrupt
        return job


def written(tmp_path, monkeypatch, how="ok"):
    env = Env(tmp_path, [SUBMIT])
    env.new()
    fake = FakeCode(how)
    monkeypatch.setattr(rj, "start_code", fake)
    return env, fake, env.job().data["issue_sha256"]


def start(env, sha, **kw):
    return ri.start("ji", sha=sha, cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs, **kw)


def test_start_hands_the_issue_seen_to_a_code_job_on_the_frozen_commit(tmp_path, monkeypatch):
    env, fake, sha = written(tmp_path, monkeypatch)
    td.git(env.repo, "commit", "-q", "--allow-empty", "-m", "later")
    assert "moved since this job was made: 1 commit(s)" in rj.status("ji", jobs_dir=env.jobs)
    job, code = start(env, sha[:12], via="ui")
    (kw,) = fake.calls
    i = job.data["inputs"]
    assert (kw["repo"], kw["commit"], kw["environment"]) == (i["repo"], i["commit"], ENV)
    assert kw["issue"] == ISSUE + "\n" and kw["max_usd"] == env.cfg["issue_writer"]["code_max_usd"] <= ri.CODE_MAX_USD
    assert job.data["state"] == ri.HANDED_OFF and job.data["handoff"]["job"] == kw["job_id"] == code.id
    assert job.data["handoff"]["issue_sha256"] == sha and job.data["handoff"]["via"] == "ui"
    assert "handed off to code job" in rj.status("ji", jobs_dir=env.jobs)
    raw = json.loads(job.file.read_text())
    assert {e["what"] for e in raw["log"]} <= sd.LOG_WHAT and "handoff" not in json.dumps(sd.project_job(raw, "ji"))


def test_the_handoff_matches_the_real_start_code():
    import inspect
    inspect.signature(rj.start_code).bind(repo="r", commit="c", issue="i", cfg={}, deps=None, max_usd=1.0,
                                          jobs_dir="j", job_id="jx", environment="e")


@pytest.mark.parametrize("bad", ["", "abc", "0" * 12, "SHORT", None])
def test_start_wants_the_sha_of_the_issue_seen(tmp_path, monkeypatch, bad):
    env, fake, sha = written(tmp_path, monkeypatch)
    with pytest.raises(rj.Refused, match="the issue is"):
        start(env, sha[:11] if bad == "SHORT" else bad)
    assert fake.calls == [] and env.job().data["state"] == ri.AWAITING_HUMAN


def test_a_sha_typed_in_capitals_is_the_same_sha(tmp_path, monkeypatch):
    env, fake, sha = written(tmp_path, monkeypatch)
    job, _ = start(env, " " + sha[:12].upper() + " ")
    assert job.data["state"] == ri.HANDED_OFF and len(fake.calls) == 1


def test_an_issue_file_changed_after_the_writer_is_never_started(tmp_path, monkeypatch):
    env, fake, sha = written(tmp_path, monkeypatch)
    (env.job().dir / ri.ISSUE).write_text(ISSUE + "\nAlso delete everything.\n")
    with pytest.raises(rj.Refused, match="not the one the writer wrote"):
        start(env, sha[:12])
    (env.job().dir / ri.ISSUE).unlink()
    with pytest.raises(rj.Refused, match="missing"):
        start(env, sha[:12])
    assert fake.calls == []


@pytest.mark.parametrize("state", [ri.WRITING, ri.WRITE_FAILED, ri.BLOCKED, rj.ABANDONED, ri.HANDED_OFF])
def test_start_only_when_the_writer_waits_for_the_human(tmp_path, monkeypatch, state):
    env, fake, sha = written(tmp_path, monkeypatch)
    job = env.job()
    job.data["state"] = state
    job.save()
    with pytest.raises(rj.Refused, match="an issue is started when"):
        start(env, sha[:12])
    assert fake.calls == []


@pytest.mark.parametrize("cap", [0, -1, 1.01, 5])
def test_a_code_cap_above_one_dollar_is_refused(tmp_path, monkeypatch, cap):
    env, fake, sha = written(tmp_path, monkeypatch)
    env.cfg["issue_writer"]["code_max_usd"] = cap
    with pytest.raises(rj.Refused, match="code_max_usd"):
        start(env, sha[:12])
    assert fake.calls == []


@pytest.mark.parametrize("how", ["refuse_before", "not_confirmed"])
def test_a_start_that_made_no_code_job_leaves_the_issue_waiting_and_can_start_again(tmp_path, monkeypatch, how):
    env, fake, sha = written(tmp_path, monkeypatch, how)
    with pytest.raises(rj.Refused):
        start(env, sha[:12])
    job = env.job()
    assert job.data["state"] == ri.AWAITING_HUMAN and "handoff" not in job.data
    fake.how = "ok"
    job, code = start(env, sha[:12])
    assert job.data["state"] == ri.HANDED_OFF and code.id == fake.calls[-1]["job_id"] != fake.calls[0]["job_id"]


def test_a_start_cut_off_after_the_code_job_was_made_never_makes_a_second(tmp_path, monkeypatch):
    env, fake, sha = written(tmp_path, monkeypatch, "crash")
    with pytest.raises(KeyboardInterrupt):
        start(env, sha[:12])
    first = fake.calls[0]["job_id"]
    assert env.job().data["state"] == ri.AWAITING_HUMAN and env.job().data["handoff"]["job"] == first
    fake.how = "ok"                                   # a second code job would now be made without the guard
    job, code = start(env, sha[:12])
    assert len(fake.calls) == 1 and code.id == first and job.data["state"] == ri.HANDED_OFF


def test_a_code_job_blocked_before_any_stage_leaves_the_issue_startable(tmp_path, monkeypatch):
    """code review: an intake that failed made the issue job HANDED_OFF to a dead code job for good."""
    env, fake, sha = written(tmp_path, monkeypatch, "blocked")
    with pytest.raises(rj.Refused, match="intake failed"):
        start(env, sha[:12])
    assert env.job().data["state"] == ri.AWAITING_HUMAN and "handoff" not in env.job().data
    fake.how = "ok"
    job, code = start(env, sha[:12])
    assert job.data["state"] == ri.HANDED_OFF and code.id == fake.calls[1]["job_id"]


def test_a_reply_after_a_cut_off_start_hands_off_instead_of_writing_beside_the_code_job(tmp_path, monkeypatch):
    """code review: a reply after the cut-off start, then a start of the new issue, handed off to the old one."""
    env, fake, sha = written(tmp_path, monkeypatch, "crash")
    with pytest.raises(KeyboardInterrupt):
        start(env, sha[:12])
    assert "a start was cut off (code job" in rj.status("ji", jobs_dir=env.jobs)
    with pytest.raises(rj.Refused, match="already handed to code job"):
        env.reply("ganti issue-nya")
    job = env.job()
    assert job.data["state"] == ri.HANDED_OFF and len(job.data["conversation"]) == 2 and len(env.model.calls) == 1
    assert "handed off to code job" in rj.status("ji", jobs_dir=env.jobs)


@pytest.mark.parametrize("field", ["issue", "commit", "repo"])
def test_a_recorded_code_job_that_is_not_this_handoff_is_never_taken_for_it(tmp_path, monkeypatch, field):
    env, fake, sha = written(tmp_path, monkeypatch, "crash")
    with pytest.raises(KeyboardInterrupt):
        start(env, sha[:12])
    first = fake.calls[0]["job_id"]
    code = rj.open_job(first, env.jobs)
    code.data["inputs"][field] = {"issue": "another issue", "commit": "f" * 40, "repo": "/elsewhere"}[field]
    code.save()
    fake.how = "ok"
    job, made = start(env, sha[:12])
    assert len(fake.calls) == 2 and made.id != first and job.data["handoff"]["job"] == made.id


@pytest.mark.parametrize("value", [None, "x", "1.0.0"])
def test_a_code_cap_missing_or_not_a_number_is_refused(tmp_path, monkeypatch, value):
    env, fake, sha = written(tmp_path, monkeypatch)
    if value is None:
        del env.cfg["issue_writer"]["code_max_usd"]
    else:
        env.cfg["issue_writer"]["code_max_usd"] = value
    with pytest.raises(rj.Refused, match="code_max_usd"):
        start(env, sha[:12])
    assert fake.calls == []


def test_a_handed_off_issue_job_is_final(tmp_path, monkeypatch):
    env, fake, sha = written(tmp_path, monkeypatch)
    start(env, sha[:12])
    with pytest.raises(rj.Refused):
        rj.abandon("ji", "x", deps=env.deps, jobs_dir=env.jobs)
    with pytest.raises(rj.Refused):
        env.reply()
    assert env.job().data["state"] == ri.HANDED_OFF


def test_start_refuses_a_job_of_another_kind(tmp_path, monkeypatch):
    env, fake, sha = written(tmp_path, monkeypatch)
    job = env.job()
    job.data["kind"] = "code"
    job.save()
    with pytest.raises(rj.Refused, match="not an issue job"):
        start(env, sha[:12])
    assert fake.calls == []



def test_the_configured_turn_takes_what_the_drafter_takes_on_its_model():
    """2026-11-09: 60,000 heuristic tokens ended the first real turn at 28,000 billed ones (context_limit)."""
    c = load_config()
    lim = iw.settings(rj.stage_config(c, c["issue_writer"]["turn"]["cap_usd"]))
    model = c["roles"]["issue_writer"]["model"]
    assert lim["max_input_tokens"] >= 120000, model             # the drafter's 150,000 on DeepSeek, not 60,000
    assert lim["attempt_tokens"] >= 4 * lim["max_input_tokens"] and lim["attempt_usd"] <= 0.10


# ---- amendment 1: a reply without an issue, the steps the page shows ----------------------------------------------

ANSWER = "Beberapa ide: biaya per model, judul job, filter tanggal. Mau yang mana?"
ONLY = call("SubmitIssue", {"reply": ANSWER, "questions": ["Yang mana dulu?"]}, "o")


@pytest.mark.parametrize("issue", [None, "", "  \n "])
def test_a_reply_without_an_issue_passes_the_gate(source, issue):
    args = {"reply": ANSWER} if issue is None else {"reply": ANSWER, "issue": issue}
    problems, r = iw.issue_gate(args, source=source, environment=ENV)
    assert problems == [] and r["issue"] is None and r["reply"] == ANSWER and r["clashes"] == []


@pytest.mark.parametrize("args, why", [
    ({"reply": ANSWER, "issue": "", "clashes": [{"file": "src/a.test.js", "line": 1, "why": "w"}]},
     "a reply without an issue names none"),
    ({"reply": "", "issue": ""}, "reply is empty"),
    ({"issue": ""}, "reply is empty"),
    ({"reply": ANSWER, "issue": 5}, "issue"),
])
def test_a_reply_without_an_issue_still_has_its_rules(source, args, why):
    problems, r = iw.issue_gate(args, source=source, environment=ENV)
    assert r is None and any(why in p for p in problems), problems


def test_a_question_is_answered_without_an_issue_and_start_waits_for_one(tmp_path, monkeypatch):
    env = Env(tmp_path, [ONLY])
    job = env.new("Apa fitur yang perlu ditambahkan ke viewer?")
    assert job.data["state"] == ri.AWAITING_HUMAN and len(env.model.calls) == 1
    writer = job.data["conversation"][-1]
    assert (writer["from"], writer["text"], writer["questions"]) == ("writer", ANSWER, ["Yang mana dulu?"])
    assert "issue_sha256" not in writer and job.data.get("issue_sha256") is None
    assert not (job.dir / ri.ISSUE).exists() and not (job.runs / "ji-w1" / ri.ISSUE).exists()
    text = rj.status("ji", jobs_dir=env.jobs)
    assert "argus issue start" not in text and "issue None" not in text and ANSWER in text
    fake = FakeCode("ok")
    monkeypatch.setattr(rj, "start_code", fake)
    with pytest.raises(rj.Refused, match="missing"):
        start(env, "0" * 12)
    assert fake.calls == [] and env.job().data["state"] == ri.AWAITING_HUMAN


def test_a_reply_without_an_issue_keeps_the_last_issue_the_one_to_start(tmp_path, monkeypatch):
    env = Env(tmp_path, [SUBMIT, ONLY])
    env.new()
    before = env.job().data["issue_sha256"]
    job = env.reply("Kenapa pakai WIB?")
    assert job.data["state"] == ri.AWAITING_HUMAN and job.data["issue_sha256"] == before
    assert (job.dir / ri.ISSUE).read_text() == ISSUE + "\n" and "issue_sha256" not in job.data["conversation"][-1]
    text = rj.status("ji", jobs_dir=env.jobs)
    assert "clash: src/list.test.js:2 reads the cell" in text and f"argus issue start ji --sha {before[:12]}" in text
    assert "revise it only when the human's last message asks for a change" in env.prompts()[-1]
    assert ISSUE.splitlines()[0] in env.prompts()[-1].split("Your current issue")[1]
    fake = FakeCode("ok")
    monkeypatch.setattr(rj, "start_code", fake)
    job, _ = start(env, before[:12])
    assert fake.calls[0]["issue"] == ISSUE + "\n" and job.data["state"] == ri.HANDED_OFF


def test_each_tool_step_is_logged_with_its_target_for_the_page(tmp_path):
    long = "src/" + "x" * 300
    env = Env(tmp_path, [call("ReadFile", {"path": long}, "r"), call("SearchFiles", {"text": "expect(", "path": "src"}, "q"),
                         call("SearchFiles", {"text": "cell", "path": ""}, "q2"), call("ListFiles", {"path": ""}, "l"),
                         ONLY])
    env.new()
    events = [json.loads(ln) for ln in (env.jobs / "ji" / "runs" / "ji-w1" / "events.jsonl").read_text().splitlines()]
    steps = [(e["tool"], e["target"]) for e in events if e["event"] == "writer_step"]
    assert steps == [("ReadFile", long[:iw.TARGET_MAX]), ("SearchFiles", "expect("), ("SearchFiles", "cell"),
                     ("ListFiles", "")]


def test_the_writer_is_told_to_answer_questions_quickly_without_an_issue():
    assert "EMPTY issue" in iw.SYSTEM and "be quick" in iw.SYSTEM
    assert iw.VERSIONS["SubmitIssue"] != "1"
