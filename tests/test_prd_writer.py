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
from models.fake import StrictScriptedChatModel  # noqa: E402
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
    assert env.new().data["state"] == pj.AWAITING_HUMAN and env.rejections() == []


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
    assert "issue 1: touches ['export const']; creates ['show_date']; 0 clash(es)" in text
    assert "issue 2: touches ['show_date']; creates ['show_time']" in text and REPLY in text


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
