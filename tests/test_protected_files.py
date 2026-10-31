"""SPEC_PROTECTED_FILES: a repository's own .argus/protected, read from the job's commit, frozen in the intake record,
and enforced by the harness at the draft check, at every write of the agent's tools, and in the review package; an
environment may require it (pwa_node22). One test (or group) per guarantee of section 3, numbered as there."""
import inspect
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_drafter as td  # noqa: E402
import test_router as tr  # noqa: E402
from acceptance import draft as dr  # noqa: E402
from acceptance import intake  # noqa: E402
from codetask import drafter as cdr  # noqa: E402
from codetask import run as ctrun  # noqa: E402
from codetask import tools as ctools  # noqa: E402
from codetask.tools import Toolbox  # noqa: E402
from harness.events import EventLog  # noqa: E402
from models.fake import reply  # noqa: E402
from router import job as rj  # noqa: E402

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="the path jail and git need posix; the VM runs these")

LIST = "# the agent never changes these\nsrc/**/package.json\nsrc/shop_config.py\n"
CONFIG = "RATE = 1\n"


def commit(repo, files, message="more"):
    for path, text in files.items():
        p = repo / path
        if text is None:
            p.unlink()
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    td.git(repo, "add", "-A")
    td.git(repo, "commit", "-qm", message)


def with_list(env, text=LIST):
    commit(env.repo, {".argus/protected": text, "src/shop_config.py": CONFIG})
    return env


def write(path, content, id="w9"):
    return reply(tool_calls=[{"name": "WriteFile", "args": {"path": path, "content": content}, "id": id}],
                 input_tokens=500, output_tokens=60)


def wide_submit():
    """The drafter's draft with a wide writable glob (src/*.py and src/**/*.json), as a draft that passes the check
    when the listed files are not writable."""
    a = td.args_with()
    a["scope"] = {"writable": ["src/shop.py", "src/**/*.json"], "protected": ["tests/**", "conftest.py"]}
    return td.call("SubmitDraft", a, "s1")


def tool_results(env, job_id="jtest", stage="a1"):
    d = env.job(job_id).runs / f"{job_id}-{stage}"
    return [json.loads(line) for line in (d / "tool_journal.jsonl").read_text().splitlines()] \
        if (d / "tool_journal.jsonl").exists() else []


def agent_saw(env):
    """Every tool result the agent was sent, from the coder model's requests."""
    return "\n".join(m.content if isinstance(m.content, str) else json.dumps(m.content)
                     for call in env.coder.calls for m in call["messages"])


# ---- 1. read from the commit, never the working tree ---------------------------------------------------------------

def test_1_the_list_is_read_from_the_commit_not_the_working_tree(tmp_path):
    env = with_list(tr.Env(tmp_path))
    (env.repo / ".argus" / "protected").write_text("nothing/**\n")              # uncommitted: never read
    rec = intake.intake(env.repo, "HEAD", "base", root=tmp_path / "root")
    assert rec["protected"]["globs"] == ["src/**/package.json", "src/shop_config.py", ".argus/protected"]
    committed = subprocess.run(["git", "-C", str(env.repo), "show", "HEAD:.argus/protected"], capture_output=True)
    assert rec["protected"]["sha256"] == intake.parse_protected(committed.stdout)["sha256"]


def test_1_without_a_list_the_record_says_none(tmp_path):
    env = tr.Env(tmp_path)
    assert intake.intake(env.repo, "HEAD", "base", root=tmp_path / "root")["protected"] is None


# ---- 2. frozen when the job is created; 4. the agent never writes or creates a listed path -----------------------

def test_2_4_the_agent_cannot_create_a_listed_file_and_a_later_commit_changes_nothing(tmp_path):
    env = tr.Env(tmp_path, draft=[wide_submit()],
                 agent=[write("src/x/package.json", "{}\n"), tr.WRITE, tr.FINISH])
    with_list(env)
    job = env.code()
    assert job.data["protected_repo"]["globs"] == 3
    commit(env.repo, {".argus/protected": "nothing/**\n"})                    # the list is frozen in the job's intake
    env.approve()
    job = env.job()
    assert job.data["state"] == rj.REVIEW_READY
    assert "src/x/package.json is protected by the repository (.argus/protected)" in agent_saw(env)
    assert not (job.runs / "jtest-a1" / "workspace" / "src" / "x").exists()


@pytest.fixture
def box(tmp_path):
    ws = tmp_path / "ws"
    for path, text in {"src/shop.py": "x = 1\n", "src/shop_config.py": CONFIG, ".argus/protected": LIST,
                       "public/sw.js": "// sw\n"}.items():
        (ws / path).parent.mkdir(parents=True, exist_ok=True)
        (ws / path).write_text(text)
    contract = {"contract": "t", "scope": {"writable": ["**"], "protected": []}, "validation": []}
    globs = intake.parse_protected(LIST.encode() + b"public/**\n")["globs"]
    return Toolbox(str(ws), contract, {}, ("read_file", "write_file", "edit_file"), EventLog(tmp_path / "e.jsonl"),
                   journal=tmp_path / "j.jsonl", repo_protected=globs), ws


def run(box, name, **args):
    return box.run({"name": name, "args": args, "id": "c"}, step_key=f"k-{name}-{args.get('path')}")["content"]


@pytest.mark.parametrize("path", ["src/shop_config.py", "src/new/package.json", "public/sw.js", ".argus/protected"])
def test_4_7_write_edit_and_create_are_refused_for_listed_paths_whatever_the_scope(box, path):
    b, ws = box
    before = {p: p.read_bytes() for p in ws.rglob("*") if p.is_file()}
    assert "protected by the repository" in run(b, "WriteFile", path=path, content="changed\n")
    assert "protected by the repository" in run(b, "EditFile", path=path, old_text="1", new_text="2")
    assert {p: p.read_bytes() for p in ws.rglob("*") if p.is_file()} == before
    assert run(b, "WriteFile", path="src/shop.py", content="x = 2\n").startswith("src/shop.py now has")  # the rest is


# ---- 3 and 10. the draft check ----------------------------------------------------------------------------------------

def contract_with(writable):
    return {"scope": {"writable": writable, "protected": ["tests/**"]}}


def test_3_a_writable_glob_that_covers_a_listed_file_refuses_the_draft():
    files = {"src/shop.py": "", "src/shop_config.py": "", "tests/test_old.py": ""}
    protected = {"globs": ["src/shop_config.py", ".argus/protected"]}
    got = dr.repo_protected_problems({"new_tests": []}, contract_with(["src/*.py"]), files, protected)
    assert got == ["src/shop_config.py is protected by the repository (.argus/protected), but writable glob "
                   "'src/*.py' matches it"]
    # not writable, though the contract's protected globs do not name it: safe
    assert dr.repo_protected_problems({"new_tests": []}, contract_with(["src/shop.py"]), files, protected) == []
    assert dr.repo_protected_problems({}, contract_with(["**"]), files, None) == []                  # no list


def test_10_a_changed_test_that_the_repository_protects_refuses_the_draft():
    files = {"tests/test_old.py": ""}
    draft = {"changed_tests": [{"path": "tests/test_old.py", "content": ""}]}
    got = dr.repo_protected_problems(draft, contract_with(["src/shop.py"]), files, {"globs": ["tests/**"]})
    assert got and "changed test tests/test_old.py is protected by the repository" in got[0]


def test_3_the_drafter_is_told_the_list_and_its_draft_is_checked_against_it(tmp_path):
    a = td.args_with()
    a["scope"] = {"writable": ["src/*.py"], "protected": ["tests/**", "conftest.py"]}       # covers src/shop_config.py
    env = tr.Env(tmp_path, draft=[td.call("SubmitDraft", a, "s1")])
    with_list(env)
    assert env.code().data["state"] == rj.DRAFT_FAILED                      # the script has no second draft
    prompt = tr.first_request(env.drafter)
    assert "Protected by the repository (.argus/protected): src/**/package.json, src/shop_config.py" in prompt
    second = "\n".join(m.content if isinstance(m.content, str) else json.dumps(m.content)
                       for m in env.drafter.calls[1]["messages"])
    assert "writable glob 'src/*.py' matches it" in second


# ---- 5. the review package ---------------------------------------------------------------------------------------

def test_5_a_change_to_a_listed_path_makes_the_review_package_invalid(tmp_path, monkeypatch):
    class Blind(Toolbox):                                    # a tool that forgot the list: the package must catch it
        def __init__(self, *a, repo_protected=(), **kw):
            super().__init__(*a, **kw)
    monkeypatch.setattr(ctrun, "Toolbox", Blind)
    env = tr.Env(tmp_path, draft=[wide_submit()], agent=[write("src/x/package.json", "{}\n"), tr.WRITE, tr.FINISH])
    with_list(env)
    env.code()
    env.approve()
    job = env.job()
    assert job.data["state"] == rj.REVIEW_INVALID
    text = rj.status("jtest", jobs_dir=env.jobs)
    assert "src/x/package.json is protected by the repository (.argus/protected)" in \
        (job.runs / "jtest-a1" / "review" / "PR.md").read_text() + text


# ---- 6. a broken list creates no job; no list is the job as before ---------------------------------------------------

@pytest.mark.parametrize("text, why", [("src/../x\n", "line 1"), ("ok/**\n/abs\n", "line 2"), ("a b\n", "no spaces"),
                                       ("x\n" * 0 + "\n".join(f"f{i}" for i in range(201)), "more than 200")])
def test_6_a_list_that_is_not_one_creates_no_job(tmp_path, text, why):
    env = with_list(tr.Env(tmp_path), text)
    with pytest.raises(rj.Refused, match=why):
        env.code()
    assert not (env.jobs / "jtest").exists()


def test_6_a_list_that_is_not_utf8_or_not_a_regular_file_creates_no_job(tmp_path):
    env = tr.Env(tmp_path)
    (env.repo / ".argus").mkdir()
    (env.repo / ".argus" / "protected").write_bytes(b"\xff\xfe\n")
    commit(env.repo, {})
    with pytest.raises(rj.Refused, match="not UTF-8"):
        env.code()
    commit(env.repo, {".argus/protected": None})
    (env.repo / ".argus" / "real").write_text("x\n")
    os.symlink("real", env.repo / ".argus" / "protected")
    commit(env.repo, {})
    with pytest.raises(rj.Refused, match="not a regular file"):
        env.code()
    assert not (env.jobs / "jtest").exists()


def test_6_without_a_list_the_job_is_as_before_and_says_so(tmp_path):
    env = tr.Env(tmp_path)
    job = env.code()
    assert job.data["protected_repo"] is None and job.data["state"] == rj.AWAITING_APPROVAL
    assert "protected by the repository: none" in rj.status("jtest", jobs_dir=env.jobs)


def test_7_the_list_always_protects_itself():
    assert intake.parse_protected(b"a/**\n")["globs"] == ["a/**", ".argus/protected"]
    assert intake.parse_protected(b".argus/protected\n")["globs"] == [".argus/protected"]


# ---- 8. no other way to change a listed file: every writing tool goes through _writable; links are never followed ----

def test_8_every_tool_method_that_writes_the_workspace_asks_writable_first():
    writers = []
    for name, fn in inspect.getmembers(Toolbox, inspect.isfunction):
        src = inspect.getsource(fn)
        if any(call in src for call in ("self.jail.write", "os.remove(", "os.unlink(", "os.rename(", "os.replace(",
                                         "os.symlink(", "os.link(", "shutil.")):
            writers.append(name)
            assert "_writable(" in src or name == "finish", f"{name} writes without _writable"
    assert set(writers) == {"writefile", "editfile", "finish"}        # finish writes only SUMMARY, never a listed path
    assert not {"DeleteFile", "RenameFile", "MoveFile", "Symlink"} & set(ctools.GATED)


def test_8_a_link_in_the_commit_never_leads_a_write_to_a_listed_file(box):
    b, ws = box
    os.symlink("../public/sw.js", ws / "src" / "link.js")
    for args in ({"name": "WriteFile", "content": "evil\n"}, {"name": "EditFile", "old_text": "sw", "new_text": "x"}):
        name = args.pop("name")
        out = run(b, name, path="src/link.js", **args)
        assert "symlink" in out.lower() or "refus" in out.lower(), out
    assert (ws / "public" / "sw.js").read_text() == "// sw\n" and os.path.islink(ws / "src" / "link.js")


# ---- 9. an environment that requires the list ---------------------------------------------------------------------

def required_config():
    c = tr.cfg()
    c["sandbox"] = {**c["sandbox"], "environments": {**(c["sandbox"].get("environments") or {}),
                                                     "web_env": {"image": "sha256:" + "e" * 64, "protected_required": True}}}
    return c


def test_9_an_environment_that_requires_the_list_creates_no_job_without_it(tmp_path, monkeypatch):
    monkeypatch.setattr(rj, "check_problem", lambda name, image, root=None: None)
    env = tr.Env(tmp_path, config=required_config())
    with pytest.raises(rj.Refused, match="requires .argus/protected"):
        env.code(environment="web_env")
    assert not (env.jobs / "jtest").exists()
    with_list(env)
    job = env.code(environment="web_env")
    assert job.data["protected_repo"]["globs"] == 3
    assert "protected by the repository: 3 globs" in rj.status("jtest", jobs_dir=env.jobs)


def test_9_pwa_node22_requires_the_list():
    from runner import load_config
    assert load_config()["sandbox"]["environments"]["pwa_node22"].get("protected_required") is True
