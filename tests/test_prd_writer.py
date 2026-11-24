"""SPEC_PRD_WRITER PR 2: the PRD writer's turn (codetask/prd_writer.py), the job (router/prd_job.py) and `argus prd new|reply`.
The model is a fake; the money goes through the real LLMCaller ledgers; the repository is a real git repository; the folder
check is the real router.prd.check."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import test_drafter as td  # noqa: E402
import test_issue_writer as tiw  # noqa: E402

from codetask import issue_writer as iw  # noqa: E402
from codetask import prd_writer as pw  # noqa: E402
from models.fake import FakeHTTPError, StrictScriptedChatModel  # noqa: E402
from router import issue as ri  # noqa: E402
from router import job as rj  # noqa: E402
from router import prd as rp  # noqa: E402
from router import prd_job as pj  # noqa: E402
from router import queue as rq  # noqa: E402
from router import stage_data as sd  # noqa: E402
from runner import load_config  # noqa: E402

ENV = tiw.ENV
TOUCH = tiw.TOUCH                       # "export const": in the code of the demo repository, in no test
FIRST = "Bikin dua perubahan: tanggal di kartu, lalu jam"
REPLY = "PRD-nya dua issue: pertama tanggal di kartu, kedua jam di sebelahnya."
PRD = "Goal: the date, then the time, on each card.\n\nThe contract: issue 1 makes `show_date`; issue 2 uses it.\n"


def issue_text(title="Show the date on the card", env=ENV, extra="", clashes=False):
    keep = "" if clashes else " The existing tests keep passing unchanged."
    return "\n".join([title, "", "Each job card shows the date it was made.", "1. `9 Nov` for `2026-11-09`." + extra, "",
                      "Nothing else changes: the list page otherwise." + keep, "",
                      "Tests: the date of each example.", f"Environment: {env}"])


def item(title="Show the date on the card", touches=(TOUCH,), creates=(), paths=(), fields=(), clashes=(),
         clash_check="", text=None):
    return {"issue": text or issue_text(title, clashes=bool(clashes) or bool(clash_check)), "paths": list(paths), "fields": list(fields), "touches": list(touches),
            "creates": list(creates), "clashes": list(clashes), "clash_check": clash_check}


def prd_args(items=None, reply=REPLY, prd_md=PRD, questions=(), notes=None, **extra):
    items = [item("Show the date on the card", creates=["show_date"]),
             item("Show the time next to the date", touches=["show_date"], creates=["show_time"])] if items is None else items
    a = {"reply": reply, "prd_md": prd_md if items else "", "items": items, "questions": list(questions), **extra}
    if notes is not None:
        a["notes"] = notes
    return a


def submit(args=None, id="s"):
    return td.call("SubmitPRD", prd_args() if args is None else args, id)


def cfg_for(repo, **turn):
    c = load_config()
    c["roles"]["issue_writer"]["model"] = "fake:scripted"
    c["issue_writer"]["repos"] = {"demo": {"path": str(repo), "environment": ENV}}
    c["prd_writer"]["turn"].update(turn)
    return c


class Env:
    def __init__(self, tmp_path, script, **turn):
        self.repo, self.jobs, self.queues = tiw.make_repo(tmp_path), tmp_path / "jobs", tmp_path / "queues"
        self.model = StrictScriptedChatModel(script=list(script))
        self.cfg, self.said = cfg_for(self.repo, **turn), []
        self.deps = rj.Deps(confirm=lambda t: True, get_key=lambda: "unused", isatty=lambda: True,
                            models={"issue_writer": self.model}, clock=lambda: "2026-11-16T12:00:00Z",
                            echo=self.said.append)

    def new(self, message=FIRST, **kw):
        return pj.new(repo="demo", message=message, cfg=self.cfg, deps=self.deps, jobs_dir=self.jobs,
                      queues_dir=self.queues, job_id="jp", **kw)

    def reply(self, message="Tambah satu lagi", **kw):
        return pj.reply("jp", message, cfg=self.cfg, deps=self.deps, jobs_dir=self.jobs, queues_dir=self.queues, **kw)

    def job(self):
        return rj.open_job("jp", self.jobs)

    def head(self):
        return subprocess.run(["git", "-C", str(self.repo), "rev-parse", "HEAD"], check=True, capture_output=True,
                              text=True).stdout.strip()

    def move_head(self, name="more.js"):
        (self.repo / "src" / name).write_text("export const MORE = 1\n")
        td.git(self.repo, "add", "-A")
        td.git(self.repo, "commit", "-qm", f"add {name}")

    def prompts(self):
        return ["\n".join(tiw.text(m) for m in c["messages"] if type(m).__name__ == "HumanMessage")
                for c in self.model.calls]

    def rejections(self):
        return list(dict.fromkeys(a for c in self.model.calls for a in tiw.tool_answers(c) if a.startswith("Rejected")))


def folder(job, sid="w1"):
    return pj.folder_of(job, sid)


# ---- the folder a good turn writes ------------------------------------------------------------------------------

def test_a_good_turn_writes_a_folder_that_prd_check_passes(tmp_path):
    env = Env(tmp_path, [submit()])
    job = env.new()
    assert job.data["state"] == pj.AWAITING_HUMAN
    d = folder(job)
    files = rp.read_folder(d)
    assert sorted(files) == ["PRD.md", "issue-1.md", "issue-2.md", "issues.json"]
    found, parsed = rp.check(files, cfg=env.cfg, queues_dir=env.queues, jobs_dir=env.jobs)
    assert [t for lvl, t in found if lvl == rp.BLOCK] == [] and parsed["valid"] is not None
    spec = json.loads(files["issues.json"])
    assert spec["repo"] == "demo" and spec["commit"] == env.job().data["inputs"]["commit"] and spec["max_usd"] == 2.0
    assert [it["n"] for it in spec["items"]] == [1, 2] and set(spec) == {"repo", "commit", "max_usd", "items"}
    assert {k for it in spec["items"] for k in it} <= {"n", "paths", "fields"}      # touches/creates/clashes stay out
    assert b"show_date" in files["PRD.md"] and files["issue-1.md"].decode().startswith("Show the date on the card")
    turn = job.data["prd_turns"][0]
    assert turn["folder_sha"] == rp.folder_sha(files) and turn["items"] == 2 and turn["creates"] == [["show_date"], ["show_time"]]
    assert turn["touches"] == [[TOUCH], ["show_date"]] and turn["submits"] == 1


def test_approving_the_writers_folder_makes_the_queue_the_gate_checked(tmp_path):
    env = Env(tmp_path, [submit()])
    job = env.new()
    d = folder(job)
    sha = rp.folder_sha(rp.read_folder(d))
    q = rp.approve(str(d), sha[:12], cfg=env.cfg, deps=env.deps, queues_dir=env.queues, jobs_dir=env.jobs)
    assert q["prd"]["sha"] == sha == job.data["prd_turns"][0]["folder_sha"]
    assert rq.derive(q)[0] == rq.PENDING and len(q["items"]) == 2
    for n in (1, 2):                                    # the queue's issue files are the gate-checked texts, stripped
        assert (env.queues / q["id"] / f"issue-{n}.md").read_text() == (d / f"issue-{n}.md").read_text().strip()


def test_no_folder_byte_is_reserialised_between_the_gate_and_the_disk(tmp_path):
    env = Env(tmp_path, [submit()])
    seen = {}
    real = rp.check

    def spy(files, **kw):
        seen.setdefault("files", dict(files))
        return real(files, **kw)
    import router.prd as module
    module.check = spy
    try:
        job = env.new()
    finally:
        module.check = real
    assert {k: v for k, v in rp.read_folder(folder(job)).items()} == seen["files"]


# ---- the model's arguments --------------------------------------------------------------------------------------

@pytest.mark.parametrize("extra", [{"max_usd": 9}, {"commit": "a" * 40}, {"repo": "x"}])
def test_money_commit_and_repo_are_never_the_models_to_set(tmp_path, extra):
    env = Env(tmp_path, [submit(prd_args(**extra)), submit(prd_args())])
    job = env.new()
    assert job.data["state"] == pj.AWAITING_HUMAN and len(env.rejections()) == 1 and "unknown key" in env.rejections()[0]
    assert json.loads((folder(job) / "issues.json").read_text())["max_usd"] == 2.0


def test_an_unknown_key_in_an_item_or_a_path_is_refused(tmp_path):
    bad_item = prd_args([{**item(), "max_usd": 3}])
    bad_path = prd_args([item(paths=[{"side": "viewer-api", "path": "/api/summary", "extra": 1}])])
    for n, args in enumerate((bad_item, bad_path)):
        env = Env(tmp_path / str(n), [submit(args), submit()])
        env.new()
        assert len(env.rejections()) == 1


def test_more_items_than_the_configured_maximum_are_refused(tmp_path):
    items = [item(f"Item {n}", creates=[f"name_{n}"]) for n in range(1, 7)]
    env = Env(tmp_path, [submit(prd_args(items)), submit()])
    env.new()
    assert "at most 5 issues" in env.rejections()[0]


def test_a_reply_only_writes_no_folder_and_keeps_the_last_one(tmp_path):
    env = Env(tmp_path, [submit(), submit(prd_args([], reply="Sebaiknya satu issue dulu.", questions=["Pakai jam?"]))])
    job = env.new()
    env.reply("Menurut lu gimana?")
    job = env.job()
    assert job.data["state"] == pj.AWAITING_HUMAN and [t["turn"] for t in job.data["prd_turns"]] == ["w1"]
    assert not (folder(job, "w2")).exists() and not (folder(job) / pj.MARK).exists()
    assert job.data["conversation"][-1]["questions"] == ["Pakai jam?"]


def test_a_reply_without_items_may_not_carry_a_prd(tmp_path):
    env = Env(tmp_path, [submit({**prd_args([]), "prd_md": "A PRD with no items"}), submit(prd_args([]))])
    job = env.new()
    assert "carries no prd_md" in env.rejections()[0] and job.data["prd_turns"] == []


# ---- touches and creates, in order ------------------------------------------------------------------------------

def test_a_touch_an_earlier_item_creates_passes_and_the_same_touch_in_the_wrong_order_does_not(tmp_path):
    reversed_ = prd_args([item("Use it", touches=["show_date"]), item("Make it", creates=["show_date"])])
    env = Env(tmp_path, [submit(reversed_), submit()])
    env.new()
    bounce = env.rejections()[0]
    assert "item 1" in bounce and "occurs in no file" in bounce and "only a LATER item creates it" in bounce


def test_an_item_cannot_excuse_its_own_touch_by_creating_it(tmp_path):
    own = prd_args([item(touches=["show_date"], creates=["show_date"])])
    env = Env(tmp_path, [submit(own), submit()])
    env.new()
    assert "touch 'show_date' occurs in no file" in env.rejections()[0]


def test_creates_match_exactly_never_as_a_substring(tmp_path):
    near = prd_args([item(creates=["show_date_widget"]), item("Two", touches=["show_date"])])
    env = Env(tmp_path, [submit(near), submit()])
    env.new()
    assert "item 2" in env.rejections()[0] and "'show_date'" in env.rejections()[0]


def test_creates_are_stripped(tmp_path):
    ok = prd_args([item(creates=["  show_date  "]), item("Two", touches=["show_date"])])
    env = Env(tmp_path, [submit(ok)])
    job = env.new()
    assert job.data["state"] == pj.AWAITING_HUMAN and env.rejections() == []
    assert job.data["prd_turns"][0]["creates"] == [["show_date"], []]


def test_a_missing_touch_is_refused_even_when_a_file_went_unread(tmp_path, monkeypatch):
    env = Env(tmp_path, [submit(prd_args([item(touches=["no_such_text"])])), submit()])
    monkeypatch.setattr(iw, "SEARCH_MAX_FILE", 30)             # list.js (22 bytes) read, list.test.js (53) unread
    env.new()
    assert "went unread" in env.rejections()[0] and "item 1" in env.rejections()[0]


# ---- the clash check, per item ----------------------------------------------------------------------------------

def code_for(env, *terms):
    found, hits, unread, per = iw.scan(env.repo, list(terms))
    return iw.hits_code(hits)


def test_the_clash_round_trip_per_item(tmp_path):
    env = Env(tmp_path, [])
    a = item("One", touches=["test('id'"], creates=["a_name"], text=issue_text("One", clashes=True))
    b = item("Two", touches=["expect(cell)"], creates=["b_name"], text=issue_text("Two", clashes=True))
    ca, cb = code_for(env, "test('id'"), code_for(env, "expect(cell)")
    assert ca != cb
    clash = [{"file": "src/list.test.js", "line": 2, "why": "reads the cell"}]
    first = prd_args([a, b])
    swapped = prd_args([{**a, "clash_check": cb, "clashes": clash}, {**b, "clash_check": ca, "clashes": clash}])
    good = prd_args([{**a, "clash_check": ca, "clashes": clash}, {**b, "clash_check": cb, "clashes": clash}])
    env.model = StrictScriptedChatModel(script=[submit(first, "s1"), submit(swapped, "s2"), submit(good, "s3")])
    env.deps.models = {"issue_writer": env.model}
    job = env.new()
    r = env.rejections()
    assert len(r) == 2 and job.data["state"] == pj.AWAITING_HUMAN and job.data["prd_turns"][0]["submits"] == 3
    assert "item 1" in r[0] and "item 2" in r[0] and ca in r[0] and cb in r[0]          # one message, every item
    assert "item 1" in r[1] and "item 2" in r[1]                                          # a code of another item is refused
    text = (folder(job) / "issue-1.md").read_text()
    assert iw.LOOSEN in text and "src/list.test.js line 2: reads the cell" in text         # the clash list is in the stored text


def test_the_issue_with_its_clash_list_may_not_pass_the_per_issue_limit(tmp_path):
    clash = [{"file": "src/list.test.js", "line": 2, "why": "w" * 290}] * 2
    long_issue = issue_text(extra=" " + "x" * (3990 - len(issue_text())), clashes=True)
    a = item(text=long_issue, touches=["expect(cell)"], clashes=clash, clash_check=code_for(Env(tmp_path / "q", []), "expect(cell)"))
    env = Env(tmp_path, [submit(prd_args([a])), submit(prd_args([item()]))])
    env.new()
    assert "item 1: the issue with the clash list the harness adds" in env.rejections()[0]


def test_the_issue_style_is_checked_for_every_item(tmp_path):
    bad = prd_args([item(), item("Two", text=issue_text("Two").replace(f"Environment: {ENV}", "Environment: other"))])
    env = Env(tmp_path, [submit(bad), submit()])
    env.new()
    assert "item 2" in env.rejections()[0] and "Environment: pwa_node22" in env.rejections()[0]


# ---- the folder gate is B1's check, on the running code ---------------------------------------------------------

def test_the_gate_is_the_prd_check_that_runs(tmp_path, monkeypatch):
    env = Env(tmp_path, [submit(), submit()])
    calls = []
    real = rp.check

    def blocking(files, **kw):
        calls.append(sorted(files))
        return ([(rp.BLOCK, "a finding of the check")], real(files, **kw)[1]) if len(calls) == 1 else real(files, **kw)
    monkeypatch.setattr(rp, "check", blocking)
    job = env.new()
    assert "a finding of the check" in env.rejections()[0] and job.data["state"] == pj.AWAITING_HUMAN
    assert calls[0] == ["PRD.md", "issue-1.md", "issue-2.md", "issues.json"]


def test_an_undeclared_path_in_an_issue_text_bounces_to_the_model(tmp_path):
    text = issue_text(extra=" Add `GET /scoreboard/models` to the ledger.")
    declared = [{"side": "ledger", "path": "/scoreboard/models", "via_proxy": False}]
    env = Env(tmp_path, [submit(prd_args([item(text=text)])), submit(prd_args([item(text=text, paths=declared)]))])
    job = env.new()
    assert "it is not in this item's paths" in env.rejections()[0] and job.data["state"] == pj.AWAITING_HUMAN
    assert json.loads((folder(job) / "issues.json").read_text())["items"][0]["paths"] == declared


def test_a_field_the_snapshot_does_not_publish_bounces(tmp_path):
    env = Env(tmp_path, [submit(prd_args([item(fields=["JOB_FIELDS.repo"])])), submit()])
    env.new()
    assert "is not published by the snapshot" in env.rejections()[0]


def test_the_submit_limit_ends_the_turn_and_the_job_can_be_replied_to(tmp_path):
    bad = prd_args([item(touches=["no_such_text"])])
    env = Env(tmp_path, [submit(bad, "s1"), submit(bad, "s2"), submit(prd_args(), "s3")], max_submits=2)
    job = env.new()
    assert job.data["state"] == pj.WRITE_FAILED and job.data["prd_turns"] == []
    r = env.rejections()
    assert len(r) == 1 and r[0].startswith("Rejected (1 problem(s)); 1 submit(s) left:")
    env.reply("coba lagi")
    assert env.job().data["state"] == pj.AWAITING_HUMAN


def test_a_repository_state_refusal_inside_the_turn_blocks_it_without_a_rejection(tmp_path, monkeypatch):
    env = Env(tmp_path, [submit()])
    real = pj._repo_state
    calls = []

    def moving(*a, **k):
        calls.append(1)
        if len(calls) > 1:
            raise rj.Refused("--commit is aaaaaaaaaaaa but the repository's HEAD is bbbbbbbbbbbb")
        return real(*a, **k)
    monkeypatch.setattr(pj, "_repo_state", moving)
    monkeypatch.setattr(rp, "check", lambda files, **kw: ([(rp.BLOCK, "x")], {"valid": None}))
    job = env.new()
    assert job.data["state"] == pj.BLOCKED and env.rejections() == [] and len(env.model.calls) == 1
    assert "HEAD is bbbbbbbbbbbb" in json.dumps(job.data["log"])


# ---- before any model call --------------------------------------------------------------------------------------

def test_new_refuses_a_moved_head_or_a_waiting_queue_without_a_job_or_a_model_call(tmp_path):
    env = Env(tmp_path, [submit()])
    q = rq.new(repo="demo", commit=env.head(), max_usd=1.0, issues=["An issue that is long enough to be one."],
               cfg=env.cfg, deps=env.deps, queues_dir=env.queues, jobs_dir=env.jobs)
    with pytest.raises(rj.Refused, match="not finished"):
        env.new()
    assert not (env.jobs / "jp").exists() and env.model.calls == [] and q["id"]


def test_reply_refuses_when_head_moved_unless_rebased(tmp_path):
    env = Env(tmp_path, [submit(prd_args(notes="old notes")), submit()])
    env.new()
    old = env.job().data["inputs"]["commit"]
    env.move_head()
    with pytest.raises(rj.Refused, match="HEAD is"):
        env.reply("update")
    assert len(env.model.calls) == 1 and env.job().data["state"] == pj.AWAITING_HUMAN
    env.reply("update", rebase=True)
    job = env.job()
    new_head = env.head()
    assert new_head != old and job.data["inputs"]["commit"] == new_head and job.data["state"] == pj.AWAITING_HUMAN
    assert json.loads((folder(job, "w2") / "issues.json").read_text())["commit"] == new_head
    assert "old notes" not in env.prompts()[-1]


def test_a_reply_is_refused_while_a_queue_waits_on_the_repository(tmp_path):
    env = Env(tmp_path, [submit(), submit()])
    job = env.new()
    d = folder(job)
    rp.approve(str(d), rp.folder_sha(rp.read_folder(d)), cfg=env.cfg, deps=env.deps, queues_dir=env.queues, jobs_dir=env.jobs)
    with pytest.raises(rj.Refused, match="not finished"):
        env.reply("one more thing")
    assert len(env.model.calls) == 1


def test_a_turn_does_not_start_without_a_whole_turn_left(tmp_path, monkeypatch):
    env = Env(tmp_path, [submit(), submit()])
    env.new()
    monkeypatch.setattr(rj, "left_usd", lambda job: 0.05)
    with pytest.raises(rj.Refused, match="less than one turn"):
        env.reply("more")
    assert len(env.model.calls) == 1


# ---- old folders ------------------------------------------------------------------------------------------------

def test_a_new_turn_marks_the_old_folder_and_approve_refuses_it(tmp_path):
    env = Env(tmp_path, [submit(), submit(prd_args([item("Only one", creates=["only_one"])]))])
    env.new()
    env.reply("Satu aja")
    job = env.job()
    assert (folder(job, "w1") / pj.MARK).exists() and not (folder(job, "w2") / pj.MARK).exists()
    with pytest.raises(rp.Folder):
        rp.read_folder(folder(job, "w1"))
    with pytest.raises(Exception):
        rp.approve(str(folder(job, "w1")), "0" * 12, cfg=env.cfg, deps=env.deps, queues_dir=env.queues, jobs_dir=env.jobs)
    assert rp.read_folder(folder(job, "w2"))["issues.json"]


def test_abandon_marks_every_folder(tmp_path):
    env = Env(tmp_path, [submit()])
    env.new()
    rj.abandon("jp", "no longer wanted", deps=env.deps, jobs_dir=env.jobs)
    job = env.job()
    assert job.data["state"] == pj.ABANDONED and (folder(job) / pj.MARK).exists()
    with pytest.raises(rp.Folder):
        rp.read_folder(folder(job))


def test_a_hand_edited_folder_no_longer_has_the_recorded_sha(tmp_path):
    env = Env(tmp_path, [submit()])
    job = env.new()
    (folder(job) / "issue-1.md").write_text("an issue written by hand\n")
    assert rp.folder_sha(rp.read_folder(folder(job))) != job.data["prd_turns"][0]["folder_sha"]


def test_a_crash_between_the_folder_and_the_move_leaves_one_valid_folder(tmp_path, monkeypatch):
    env = Env(tmp_path, [submit()])
    real = pj.mark_superseded

    def crash(job, keep=None):
        raise KeyboardInterrupt("cut off after the folder was written")
    monkeypatch.setattr(pj, "mark_superseded", crash)
    with pytest.raises(KeyboardInterrupt):
        env.new()
    monkeypatch.setattr(pj, "mark_superseded", real)
    assert env.job().data["state"] == pj.WRITING and folder(env.job()).is_dir()
    rj.resume("jp", cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs)
    job = env.job()
    assert job.data["state"] == pj.AWAITING_HUMAN and len(env.model.calls) == 1             # no second turn was bought
    assert sorted(p.name for p in job.dir.glob("prd-*")) == ["prd-w1"]
    assert len(job.data["prd_turns"]) == 1 and rp.folder_sha(rp.read_folder(folder(job))) == job.data["prd_turns"][0]["folder_sha"]


# ---- kinds, status, snapshot ------------------------------------------------------------------------------------

def test_the_issue_and_prd_commands_refuse_each_others_jobs(tmp_path):
    env = Env(tmp_path, [submit()])
    env.new()
    with pytest.raises(rj.Refused, match="not an issue job"):
        ri.reply("jp", "x", cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs)
    with pytest.raises(rj.Refused):
        ri.start("jp", sha="0" * 12, cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs)
    other = tiw.Env(tmp_path / "other", [tiw.SUBMIT])
    other.new()
    with pytest.raises(rj.Refused, match="not a PRD job"):
        pj.reply("ji", "x", cfg=other.cfg, deps=other.deps, jobs_dir=other.jobs, queues_dir=tmp_path / "q")


def test_status_names_the_check_line_the_touches_and_the_creates(tmp_path):
    env = Env(tmp_path, [submit()])
    job = env.new()
    text = rj.status("jp", jobs_dir=env.jobs)
    assert f"argus prd check {folder(job)}" in text and "(prd)" in text
    assert "issue 1 'Show the date on the card': touches ['export const']; creates ['show_date']; 0 clash(es)" in text
    assert "issue 2 'Show the time next to the date': touches ['show_date']; creates ['show_time']" in text and REPLY in text
    assert "proposed queue money $2.00" in text and f"read: {folder(job).resolve()}/PRD.md" in text


def test_the_public_snapshot_publishes_state_and_money_never_the_texts(tmp_path):
    env = Env(tmp_path, [submit(prd_args(notes="private notes about the repository"))])
    job = env.new()
    raw = json.loads(job.file.read_text())
    assert {e["what"] for e in raw["log"]} <= sd.LOG_WHAT
    published = json.dumps(sd.project_job(raw, "jp"))
    for secret in (FIRST, REPLY, "private notes", "show_date", "Show the date on the card", "prd_turns", "contract"):
        assert secret not in published
    assert json.loads(published)["kind"] == "prd" and json.loads(published).get("title") is None


def test_the_tool_set_is_the_read_only_one_plus_the_submit(tmp_path):
    env = Env(tmp_path, [submit()])
    env.new()
    assert {t.__name__ for t in env.model.bound_tools} == {"ListFiles", "SearchFiles", "ReadFile", "SubmitPRD"}


def test_the_second_turn_carries_the_previous_folder_and_the_notes(tmp_path):
    env = Env(tmp_path, [submit(prd_args(notes="where things live")), submit()])
    env.new()
    env.reply("Ubah urutannya")
    p = env.prompts()[-1]
    assert "where things live" in p and "Show the time next to the date" in p and "PRD.md:" in p and "At most 5 issues" in p


# ---- the CLI ----------------------------------------------------------------------------------------------------

def test_the_prd_subcommands_dispatch_each_their_own_way():
    import argus
    ap = argus.build_parser() if hasattr(argus, "build_parser") else None
    src = Path(argus.__file__).read_text()
    assert 'o.prd_cmd in ("new", "reply")' in src and 'if o.prd_cmd != "approve"' in src
    if ap is not None:
        for argv in (["prd", "new", "--repo", "demo", "--message", "m"], ["prd", "reply", "jp", "--message", "m", "--rebase"],
                     ["prd", "check", "d"], ["prd", "approve", "d", "--sha", "a" * 12]):
            assert ap.parse_args(argv).cmd == "prd"


def test_a_reply_is_refused_from_a_state_that_does_not_wait_for_the_human(tmp_path):
    env = Env(tmp_path, [submit()])
    env.new()
    rj.abandon("jp", "no longer wanted", deps=env.deps, jobs_dir=env.jobs)
    with pytest.raises(rj.Refused, match="is ABANDONED"):
        env.reply("one more")
    assert len(env.model.calls) == 1


def test_the_first_turn_is_blocked_without_a_model_call_when_less_than_a_turn_is_left(tmp_path, monkeypatch):
    env = Env(tmp_path, [submit()])
    monkeypatch.setattr(rj, "left_usd", lambda job: 0.05)
    job = env.new()
    assert job.data["state"] == pj.BLOCKED and env.model.calls == [] and "budget" in json.dumps(job.data["log"])


def test_the_chat_names_a_prd_job_and_shows_nothing_of_it(tmp_path):
    from router import chat_actions as ca
    env = Env(tmp_path, [submit()])
    job = env.new()
    ids = "j20261116_120000_abcd"
    raw = json.loads(job.file.read_text())
    (env.jobs / ids).mkdir()
    (env.jobs / ids / "job.json").write_text(json.dumps({**raw, "job": ids}))
    acts = ca.Actions(env.jobs, env.cfg, state=tmp_path / "state")
    assert acts.decision(ids) == {"id": ids, "kind": "prd", "state": pj.AWAITING_HUMAN}


def test_money_of_a_prd_job_is_its_own_total_in_the_scoreboard(tmp_path, monkeypatch):
    import scoreboard as sb
    env = Env(tmp_path, [submit()])
    env.new()
    monkeypatch.setattr(sb, "runs_spent_nano", lambda runs, stages: 2_500_000_000)
    got = sb.build(env.jobs)
    assert got["usd_prd_jobs"] == 2.5 and got["usd_code_jobs"] == 0 and got["usd_research_jobs"] == 0


def test_the_issues_together_may_not_pass_the_total_limit(tmp_path):
    def big(n):
        return item(f"Item {n}", creates=[f"name_{n}"], text=issue_text(f"Item {n}", extra=" " + "x" * 3400))
    items = [big(n) for n in range(1, 6)]
    env = Env(tmp_path, [submit(prd_args(items)), submit(prd_args(items[:2]))])
    env.new()
    assert "the issues together have" in env.rejections()[0] and "more than 16000" in env.rejections()[0]


def test_notes_cannot_close_their_own_data_block(tmp_path):
    env = Env(tmp_path, [submit(prd_args(notes="a >>> b")), submit(prd_args(notes="fine"))])
    env.new()
    assert "notes must not contain" in env.rejections()[0]


@pytest.mark.parametrize("message", ["", "   ", "x" * 4001, "bad\x00char"])
def test_the_first_and_the_next_message_are_screened(tmp_path, message):
    env = Env(tmp_path, [submit(), submit()])
    with pytest.raises(rj.Refused, match="nothing was started"):
        env.new(message)
    assert env.model.calls == [] and not (env.jobs / "jp").exists()
    env.new()
    with pytest.raises(rj.Refused, match="nothing was started"):
        env.reply(message)
    assert len(env.model.calls) == 1


def test_the_human_message_is_on_disk_before_its_turn_starts(tmp_path, monkeypatch):
    env = Env(tmp_path, [submit(), submit()])
    env.new()

    def cut_off(*a, **k):
        raise KeyboardInterrupt("cut off at the start of the turn")
    monkeypatch.setattr(pj, "_turn", cut_off)
    with pytest.raises(KeyboardInterrupt):
        env.reply("Pesan yang tidak boleh hilang")
    job = env.job()
    assert job.data["state"] == pj.WRITING and job.data["conversation"][-1]["text"] == "Pesan yang tidak boleh hilang"


# ---- review fixes: the gate never raises, resume, rebase, the post-run check, the measure --------------------------

MALFORMED = [
    {"touches": 5}, {"touches": True}, {"touches": {"a": 1}}, {"touches": [5]}, {"creates": 5}, {"creates": [["x"]]},
    {"clashes": "x"}, {"clashes": [5]}, {"clashes": [{"file": "a\x00b", "line": 1, "why": "w"}]},
    {"clashes": [{"file": "src/list.js", "line": 1, "why": "w", "extra": 1}]}, {"paths": "x"}, {"paths": [{"side": 1}]},
    {"fields": [{}]}, {"issue": 5}, {"issue": ["x"]}]


@pytest.mark.parametrize("bad", MALFORMED, ids=[json.dumps(b)[:40] for b in MALFORMED])
def test_malformed_arguments_bounce_and_never_stop_the_turn(tmp_path, bad):
    env = Env(tmp_path, [submit(prd_args([{**item(), **bad}])), submit()])
    job = env.new()
    assert job.data["state"] == pj.AWAITING_HUMAN and len(env.rejections()) == 1
    assert job.data["stages"]["w1"]["rejections"]


@pytest.mark.parametrize("bad", [[5], [None], ["x"], [{"issue": None}], "x", 5])
def test_malformed_items_bounce_too(tmp_path, bad):
    env = Env(tmp_path, [submit(prd_args(bad)), submit()])
    assert env.new().data["state"] == pj.AWAITING_HUMAN and len(env.rejections()) == 1


def test_an_exception_inside_the_gate_comes_back_as_a_rejection(tmp_path, monkeypatch):
    env = Env(tmp_path, [submit(), submit()])
    real = pw.items_gate
    calls = []

    def boom(*a, **k):
        calls.append(1)
        if len(calls) == 1:
            raise RecursionError("deep")
        return real(*a, **k)
    monkeypatch.setattr(pw, "items_gate", boom)
    assert env.new().data["state"] == pj.AWAITING_HUMAN and "malformed (RecursionError)" in env.rejections()[0]


def test_via_proxy_null_is_the_same_as_absent(tmp_path):
    path = {"side": "viewer-api", "path": "/api/summary", "via_proxy": None}
    text = issue_text(extra=" It reads `GET /api/summary`.")
    env = Env(tmp_path, [submit(prd_args([item(text=text, paths=[path])]))])
    job = env.new()
    assert env.rejections() == [] and json.loads((folder(job) / "issues.json").read_text())["items"][0]["paths"] == [
        {"side": "viewer-api", "path": "/api/summary"}]


def test_a_very_long_path_is_refused(tmp_path):
    env = Env(tmp_path, [submit(prd_args([item(paths=[{"side": "viewer-api", "path": "/api/" + "a" * 300}])])), submit()])
    env.new()
    assert "at most 200 characters" in env.rejections()[0]


def test_the_issue_limit_counts_the_newline_the_queue_counts(tmp_path):
    for length, ok in ((3999, True), (4000, False)):
        text = issue_text(extra=" " + "x" * (length - len(issue_text()) - 1))
        assert len(text) == length
        env = Env(tmp_path / str(length), [submit(prd_args([item(text=text)])), submit()])
        env.new()
        assert (env.rejections() == []) is ok
        if not ok:
            assert "item 1: the issue with the clash list the harness adds has 4001 characters" in env.rejections()[0]


def test_the_gate_checks_with_the_queues_and_jobs_directories_it_was_given(tmp_path, monkeypatch):
    env = Env(tmp_path, [submit()])
    seen = []
    real = rp.check
    monkeypatch.setattr(rp, "check", lambda files, **kw: seen.append(kw) or real(files, **kw))
    env.new()
    assert seen and all(kw["queues_dir"] == env.queues and kw["jobs_dir"] == env.jobs for kw in seen)


def test_resume_uses_the_queues_directory_the_job_was_made_with_and_asks_the_repository_first(tmp_path, monkeypatch):
    env = Env(tmp_path, [submit()])
    monkeypatch.setattr(pj, "mark_superseded", lambda job, keep=None: (_ for _ in ()).throw(KeyboardInterrupt("cut off")))
    with pytest.raises(KeyboardInterrupt):
        env.new()
    monkeypatch.undo()
    assert env.job().data["queues_dir"] == str(env.queues)
    seen = []
    real = rp.check
    monkeypatch.setattr(rp, "check", lambda files, **kw: seen.append(kw["queues_dir"]) or real(files, **kw))
    env.move_head("moved.js")
    with pytest.raises(rj.Refused, match="HEAD is"):                      # the preflight, before any key or money
        rj.resume("jp", cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs)
    assert env.job().data["state"] == pj.WRITING and len(env.model.calls) == 1


def test_resume_replays_with_the_stored_queues_directory(tmp_path, monkeypatch):
    env = Env(tmp_path, [submit()])
    monkeypatch.setattr(pj, "mark_superseded", lambda job, keep=None: (_ for _ in ()).throw(KeyboardInterrupt("cut off")))
    with pytest.raises(KeyboardInterrupt):
        env.new()
    monkeypatch.undo()
    seen = []
    real = rp.check
    monkeypatch.setattr(rp, "check", lambda files, **kw: seen.append(kw["queues_dir"]) or real(files, **kw))
    rj.resume("jp", cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs)
    assert seen and set(seen) == {env.queues}


def test_a_rebased_job_without_a_new_folder_says_so_and_marks_the_old_one(tmp_path):
    env = Env(tmp_path, [submit(), submit(prd_args([], reply="Belum jelas."))])
    env.new()
    env.move_head()
    env.reply("update", rebase=True)
    job = env.job()
    assert (folder(job) / pj.MARK).exists()
    text = rj.status("jp", jobs_dir=env.jobs)
    assert "no folder for this commit yet" in text and "argus prd check" not in text
    assert "OLDER commit" in env.prompts()[-1]


def test_a_folder_that_no_longer_passes_the_check_is_never_written(tmp_path, monkeypatch):
    env = Env(tmp_path, [submit()])
    real = rp.check
    calls = []

    def later_blocks(files, **kw):
        calls.append(1)
        found, parsed = real(files, **kw)
        return (found + [(rp.BLOCK, "the world moved")], parsed) if len(calls) > 1 else (found, parsed)
    monkeypatch.setattr(rp, "check", later_blocks)
    job = env.new()
    assert job.data["state"] == pj.WRITE_FAILED and not folder(job).exists() and "the world moved" in json.dumps(job.data["log"])
    assert job.data["prd_turns"] == []


def test_abandon_marks_the_folders_before_it_moves(tmp_path, monkeypatch):
    env = Env(tmp_path, [submit()])
    job = env.new()
    real = rj.Job.move

    def cut(self, new, deps, **why):
        if new == pj.ABANDONED:
            raise KeyboardInterrupt("cut off at the move")
        return real(self, new, deps, **why)
    monkeypatch.setattr(rj.Job, "move", cut)
    with pytest.raises(KeyboardInterrupt):
        rj.abandon("jp", "no longer wanted", deps=env.deps, jobs_dir=env.jobs)
    assert (folder(job) / pj.MARK).exists() and env.job().data["state"] == pj.AWAITING_HUMAN


def test_the_stage_records_what_the_gate_refused_by_kind(tmp_path):
    env = Env(tmp_path, [])
    a = item("One", touches=["expect(cell)"], creates=["a_name"], text=issue_text("One", clashes=True))
    code = code_for(env, "expect(cell)")
    clash = [{"file": "src/list.test.js", "line": 2, "why": "reads the cell"}]
    blocked = {**item("Two", fields=["JOB_FIELDS.repo"])}
    env.model = StrictScriptedChatModel(script=[
        submit(prd_args([a]), "s1"), submit(prd_args([{**a, "clash_check": code, "clashes": clash}, blocked]), "s2"),
        submit(prd_args([{**a, "clash_check": code, "clashes": clash}]), "s3")])
    env.deps.models = {"issue_writer": env.model}
    job = env.new()
    assert job.data["stages"]["w1"]["rejections"] == {"clash_check": 1, "folder_check": 1}
    assert job.data["prd_turns"][0]["rejections"] == {"clash_check": 1, "folder_check": 1}


def test_a_reply_only_and_a_failed_turn_record_their_rejections_too(tmp_path):
    bad = prd_args([item(touches=["no_such_text"])])
    env = Env(tmp_path, [submit(bad, "s1"), submit(bad, "s2")], max_submits=2)
    job = env.new()
    assert job.data["state"] == pj.WRITE_FAILED and job.data["stages"]["w1"]["rejections"] == {"other": 2}


def test_a_cut_off_or_overfull_reply_ends_the_turn_and_the_job_stays_replyable(tmp_path):
    from models.fake import reply as fake_reply
    cut = fake_reply("", tool_calls=[{"name": "SubmitPRD", "args": prd_args(), "id": "s"}], stop_reason="max_tokens")
    env = Env(tmp_path, [cut, submit()])
    job = env.new()
    assert job.data["state"] == pj.WRITE_FAILED and "output_truncated" in json.dumps(job.data["log"])
    env.reply("coba lagi")
    assert env.job().data["state"] == pj.AWAITING_HUMAN
    env2 = Env(tmp_path / "ctx", [submit(), submit()], max_input_tokens=50)
    job2 = env2.new()
    assert job2.data["state"] == pj.WRITE_FAILED and "context_limit" in json.dumps(job2.data["log"])


@pytest.mark.parametrize("state", [pj.WRITING, pj.BLOCKED])
def test_a_reply_is_refused_while_writing_or_blocked(tmp_path, state):
    env = Env(tmp_path, [submit()])
    env.new()
    job = env.job()
    job.data["state"] = state
    job.save()
    with pytest.raises(rj.Refused, match=f"is {state}"):
        env.reply("more")


def test_an_unpriced_model_is_refused_before_a_job_exists(tmp_path):
    env = Env(tmp_path, [submit()])
    env.cfg["roles"]["prd_role"] = {**env.cfg["roles"]["issue_writer"], "model": "openrouter:anthropic/model-nobody-priced"}
    env.cfg["prd_writer"]["role"] = "prd_role"
    with pytest.raises(rj.Refused, match="prd writer"):
        env.new()
    assert not (env.jobs / "jp").exists() and env.model.calls == []


def test_a_damaged_job_json_is_refused_not_half_read(tmp_path):
    env = Env(tmp_path, [submit(), submit()])
    env.new()
    job = env.job()
    job.data["prd_turns"] = [{"turn": 5}]
    job.save()
    with pytest.raises(rj.Refused, match="not a PRD job's"):
        env.reply("more")
    job.data["prd_turns"], job.data["inputs"], job.data["state"] = [], {"repo": 1}, pj.WRITING
    job.save()
    with pytest.raises(rj.Refused, match="not a PRD job's"):
        rj.resume("jp", cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs)


def test_the_proposed_money_never_falls_below_one_jobs_cap(tmp_path):
    env = Env(tmp_path, [submit()])
    env.cfg["issue_writer"]["code_max_usd"] = 0.125
    assert pj.max_usd_for(env.cfg, 1) == 0.125 and pj.max_usd_for(env.cfg, 40) == rq.QUEUE_MAX_USD


def test_the_chat_lists_a_prd_job_neither_as_an_issue_nor_in_the_public_log(tmp_path):
    from router import chat_actions as ca
    env = Env(tmp_path, [submit()])
    job = env.new()
    ids = "j20261116_120001_abcd"
    (env.jobs / ids).mkdir()
    (env.jobs / ids / "job.json").write_text(json.dumps({**json.loads(job.file.read_text()), "job": ids}))
    assert ca.Actions(env.jobs, env.cfg, state=tmp_path / "state").read_issue(ids) is None
    published = sd.project_job(json.loads(job.file.read_text()), "jp")
    assert all(set(e) <= set(sd.LOG_FIELDS) for e in published["log"])


def test_a_clash_with_an_unknown_key_or_a_nul_in_its_file_is_refused_for_what_it_is(tmp_path):
    base = {"file": "src/list.test.js", "line": 2, "why": "reads the cell"}
    env = Env(tmp_path / "a", [submit(prd_args([item(clashes=[{**base, "extra": 1}])])), submit()])
    env.new()
    assert "clash 1: unknown key(s) 'extra'" in env.rejections()[0]
    env = Env(tmp_path / "b", [submit(prd_args([item(clashes=[{**base, "file": "src/a\x00b"}])])), submit()])
    env.new()
    assert "is not a file of the repository" in env.rejections()[0] and "malformed" not in env.rejections()[0]


# ---- the writer is told the rules the gate enforces (pilot 2 wasted two submits on an unwritten 80-character limit) ----

def test_the_prompt_and_the_schema_state_the_touch_and_creates_rules():
    fields = pw.Item.model_fields
    span = f"{iw.TOUCH_MIN} to {iw.TOUCH_MAX} characters"
    assert span in fields["touches"].description and span in fields["creates"].description
    assert pw.SYSTEM.count(span) == 2                                    # once for touches, once for creates
    assert f"1 to {iw.TOUCHES_MAX} texts" in pw.SYSTEM and f"1 to {iw.TOUCHES_MAX} texts" in fields["touches"].description
    assert f"at most {pw.CREATES_MAX}" in pw.SYSTEM and f"At most {pw.CREATES_MAX}" in fields["creates"].description
    assert "EXACTLY" in pw.SYSTEM and "character for character" in fields["touches"].description
    assert "not by substring" in pw.SYSTEM
    assert "never a signature" in pw.SYSTEM and "never a whole function signature" in pw.SYSTEM
    assert "never a whole" in fields["touches"].description and "never a signature" in fields["creates"].description
    assert "ONE line" in pw.SYSTEM and "one line" in fields["creates"].description and "ONE line" in fields["touches"].description
    assert "a longer text is refused" in pw.SYSTEM


HINT = "that an earlier item creates"


def test_a_touch_that_contains_a_created_name_is_told_which_string_to_write(tmp_path):
    wrong = prd_args([item(creates=["show_date"]), item("Two", touches=["def show_date(entries, week=None):"])])
    env = Env(tmp_path, [submit(wrong), submit()])
    env.new()
    bounce = env.rejections()[0]
    assert "item 2" in bounce and f"the 'show_date' {HINT}" in bounce and "exactly as that string" in bounce


def test_the_longest_created_name_inside_the_touch_is_the_one_named(tmp_path):
    # both names stand in the touch as whole words; the shortest is not the first alphabetically either
    wrong = prd_args([item(creates=["abc", "xyz_long"]), item("Two", touches=["foo(abc, xyz_long)"])])
    env = Env(tmp_path, [submit(wrong), submit()])
    env.new()
    assert f"the 'xyz_long' {HINT}" in env.rejections()[0]


def test_a_name_that_is_only_part_of_a_longer_word_is_not_inside(tmp_path):
    wrong = prd_args([item(creates=["show", "show_date"]), item("Two", touches=["def show_date(x):"])])
    env = Env(tmp_path, [submit(wrong), submit()])
    env.new()
    assert f"the 'show_date' {HINT}" in env.rejections()[0]


def test_a_name_only_a_later_item_creates_is_not_offered_as_the_near_one(tmp_path):
    wrong = prd_args([item("One", creates=["other_name"]), item("Two", touches=["def show_date(x):"]),
                      item("Three", creates=["show_date"])])
    env = Env(tmp_path, [submit(wrong), submit()])
    env.new()
    assert HINT not in env.rejections()[0]


def test_a_touch_inside_a_created_name_is_told_too_with_the_shortest_such_name(tmp_path):
    wrong = prd_args([item(creates=["show_date_widget", "show_date_widget_extra"]), item("Two", touches=["show_date"])])
    env = Env(tmp_path, [submit(wrong), submit()])
    env.new()
    assert f"the 'show_date_widget' {HINT}" in env.rejections()[0]


def test_a_padded_touch_gets_the_hint(tmp_path):
    wrong = prd_args([item(creates=["show_date"]), item("Two", touches=["  def show_date(x):  "])])
    env = Env(tmp_path, [submit(wrong), submit()])
    env.new()
    assert f"the 'show_date' {HINT}" in env.rejections()[0]


def test_a_padded_abbreviation_gets_the_hint_too(tmp_path):
    wrong = prd_args([item(creates=["show_date_widget"]), item("Two", touches=["  show_date  "])])
    env = Env(tmp_path, [submit(wrong), submit()])
    env.new()
    assert f"the 'show_date_widget' {HINT}" in env.rejections()[0]


def test_a_short_created_name_does_not_claim_an_unrelated_typo(tmp_path):
    wrong = prd_args([item(creates=["id"]), item("Two", touches=["grid_widht"])])
    env = Env(tmp_path, [submit(wrong), submit()])
    env.new()
    bounce = env.rejections()[0]
    assert "touch 'grid_widht' occurs in no file" in bounce and HINT not in bounce


def test_a_very_short_touch_does_not_match_inside_a_longer_name(tmp_path):
    wrong = prd_args([item(creates=["show_date_widget"]), item("Two", touches=["how"])])
    env = Env(tmp_path, [submit(wrong), submit()])
    env.new()
    assert HINT not in env.rejections()[0]


def test_the_hint_is_worded_as_a_condition_not_an_order(tmp_path):
    wrong = prd_args([item(creates=["show_date"]), item("Two", touches=["def show_date(x):"])])
    env = Env(tmp_path, [submit(wrong), submit()])
    env.new()
    assert "(if you mean the 'show_date' that an earlier item creates, write the touch exactly as that string" in env.rejections()[0]


def test_a_name_that_only_a_later_item_creates_still_gets_the_later_hint_not_the_near_one(tmp_path):
    wrong = prd_args([item("One", creates=["show_date_widget"]), item("Two", touches=["show_date"]),
                      item("Three", creates=["show_date"])])
    env = Env(tmp_path, [submit(wrong), submit()])
    env.new()
    bounce = env.rejections()[0]
    assert "only a LATER item creates it" in bounce and HINT not in bounce


def test_no_creates_hint_when_nothing_resembles_the_touch(tmp_path):
    wrong = prd_args([item(creates=["show_date"]), item("Two", touches=["no_such_text"])])
    env = Env(tmp_path, [submit(wrong), submit()])
    env.new()
    assert HINT not in env.rejections()[0]


def test_the_hint_names_only_earlier_creates_not_the_items_own(tmp_path):
    wrong = prd_args([item(touches=["def own_name(x):"], creates=["own_name"])])
    env = Env(tmp_path, [submit(wrong), submit()])
    env.new()
    assert HINT not in env.rejections()[0]


def test_a_too_long_touch_gets_the_length_message_and_no_hint(tmp_path):
    long_touch = "show_date" + " " + "x" * 71                          # 81 characters, the pilot's first failure
    assert len(long_touch) == 81
    wrong = prd_args([item(creates=["show_date"]), item("Two", touches=[long_touch])])
    env = Env(tmp_path, [submit(wrong), submit()])
    env.new()
    bounce = env.rejections()[0]
    assert "has 81 characters, more than 80" in bounce and HINT not in bounce


def test_a_touch_found_in_todays_code_gets_no_rejection_and_no_hint(tmp_path):
    ok = prd_args([item(creates=["export"]), item("Two", touches=["export const"])])
    env = Env(tmp_path, [submit(ok)])
    env.new()
    assert env.rejections() == []


def test_the_hint_also_comes_with_the_unread_files_message(tmp_path, monkeypatch):
    wrong = prd_args([item(creates=["show_date"]), item("Two", touches=["def show_date(x):"])])
    env = Env(tmp_path, [submit(wrong), submit()])
    monkeypatch.setattr(iw, "SEARCH_MAX_FILE", 30)
    env.new()
    bounce = env.rejections()[0]
    assert "went unread" in bounce and f"the 'show_date' {HINT}" in bounce


# ---- a provider failure is WRITE_FAILED, not BLOCKED (2026-11-24, SPEC_RETRY_AGENT_FAILED_AND_PRD_PROVIDER) -----------------------------------------

def test_a_provider_failure_in_a_turn_leaves_a_job_that_a_reply_can_continue(tmp_path):
    env = Env(tmp_path, [FakeHTTPError(402, "payment required"), submit()])
    job = env.new()
    assert job.data["state"] == pj.WRITE_FAILED and job.data["state"] != pj.BLOCKED
    assert "402" in json.dumps(job.data["log"])                                                      # the reason says what the provider said
    job = env.reply("coba lagi")
    assert job.data["state"] == pj.AWAITING_HUMAN and job.data["stages"]["w1"]["status"] == pw.FAILED


def test_a_failed_provider_call_ends_the_stage_failed_with_the_providers_reason_and_not_blocked(tmp_path):
    env = Env(tmp_path, [FakeHTTPError(402, "payment required")])
    job = env.new()
    st = job.data["stages"]["w1"]
    assert st["status"] == pw.FAILED and st["status"] != pw.BLOCKED and "402" in str(st.get("stop_reason") or json.dumps(job.data["log"]))


def test_a_turn_that_cannot_be_funded_is_still_blocked_not_write_failed(tmp_path, monkeypatch):
    env = Env(tmp_path, [submit()])
    monkeypatch.setattr(rj, "left_usd", lambda job: 0.05)
    assert env.new().data["state"] == pj.BLOCKED
