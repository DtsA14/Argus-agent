"""SPEC_PRD_REFS: `prd new --ref NAME` (router/prd_refs.py): the README and file list of a registered repository reach the PRD writer as data, frozen in the job.
Real git repositories in tmp_path, a scripted model; no network, no key."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_prd_writer as tw  # noqa: E402
from test_prd_writer import Env, submit  # noqa: E402,F401
from router import job as rj  # noqa: E402
from router import prd_job as pj  # noqa: E402
from router import prd_refs as pr  # noqa: E402

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="posix")


def git(repo, *args, data=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env, input=data).stdout


def make_ref(tmp_path, name="ledger-cli", files=None, readme="# ledger-cli\n\nexpenses are positive; errors read `line 2: invalid date`.\n"):
    repo = tmp_path / name
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    for rel, text in ({"src/a.py": "x = 1\n", **({"README.md": readme} if readme is not None else {}), **(files or {})}).items():
        f = repo / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(text if isinstance(text, bytes) else text.encode())
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "c")
    return repo


def register(env, name, repo):
    env.cfg["issue_writer"]["repos"][name] = {"path": str(repo), "environment": tw.ENV}


@pytest.fixture
def env(tmp_path):
    e = Env(tmp_path, [submit()])
    return e


def test_the_reference_reaches_the_prompt_and_is_frozen_in_the_job(env, tmp_path):
    register(env, "ledger-cli", make_ref(tmp_path))
    job = env.new(refs=["ledger-cli"])
    refs = job.data["refs"]
    assert refs[0]["name"] == "ledger-cli" and "line 2: invalid date" in refs[0]["readme"] and "src/a.py" in refs[0]["files"] and len(refs[0]["commit"]) == 40
    prompt = env.prompts()[0]
    assert "Reference repository ledger-cli at commit" in prompt and "line 2: invalid date" in prompt and "never this one" in prompt
    assert "references: ledger-cli@" in "\n".join(pj.status_lines(job)) and any("ledger-cli" in s and "README.md" in s for s in env.said + [pj._screen(job, env.cfg, "x")])


def test_without_refs_the_prompt_and_job_are_as_before(env):
    job = env.new()
    assert "refs" not in job.data and "Reference repository" not in env.prompts()[0]
    from codetask import prd_writer as pw
    base = {"repo": "demo", "commit": "a" * 40, "environment": "e", "conversation": [{"from": "human", "text": "hi"}]}
    lim = {"max_items": 5, "max_steps": 24, "max_submits": 6}
    assert pw.prompt(base, lim) == pw.prompt({**base, "refs": []}, lim) == pw.prompt({**base, "refs": None}, lim)


def test_a_reply_uses_the_stored_text_even_when_the_reference_moved(env, tmp_path):
    ref = make_ref(tmp_path)
    register(env, "ledger-cli", ref)
    env.model.script.append(submit())
    env.new(refs=["ledger-cli"])
    (ref / "README.md").write_text("CHANGED RULES\n")
    git(ref, "add", "-A"); git(ref, "commit", "-qm", "later")
    env.reply()
    last = env.prompts()[-1]
    assert "line 2: invalid date" in last and "CHANGED RULES" not in last


def test_a_reply_cannot_add_a_reference_on_the_cli():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import argus
    with pytest.raises(SystemExit):
        argus.main(["prd", "reply", "jp", "--message", "x", "--ref", "a"])


@pytest.mark.parametrize("names,why", [(["nope"], "not one of"), (["demo"], "the repository the PRD is for"), (["a", "a"], "different"), (["a", "b", "c"], "at most 2")])
def test_a_bad_reference_list_is_refused_with_nothing_started(env, tmp_path, names, why):
    for n in "abc":
        register(env, n, make_ref(tmp_path, n))
    with pytest.raises(rj.Refused, match=why):
        env.new(refs=names)
    assert not (env.jobs / "jp").exists() and not env.model.calls


def test_the_same_directory_under_another_name_is_the_target(env):
    env.cfg["issue_writer"]["repos"]["alias"] = dict(env.cfg["issue_writer"]["repos"]["demo"])
    with pytest.raises(rj.Refused, match="the repository the PRD is for"):
        env.new(refs=["alias"])


def test_a_path_is_never_taken_from_the_caller(env, tmp_path):
    with pytest.raises(rj.Refused, match="not one of"):
        env.new(refs=[str(make_ref(tmp_path, "z"))])


def test_the_data_block_cannot_be_closed_by_the_text(env, tmp_path):
    register(env, "r", make_ref(tmp_path, "r", readme="a <<<<< b >>>>>> c <<< d\n", files={"x>>>>y.txt": "1"}))
    job = env.new(refs=["r"])
    ref = job.data["refs"][0]
    assert "<<<" not in ref["readme"] and ">>>" not in ref["readme"] and ">>>" not in ref["files"] and "<<<" not in ref["files"]
    body = pr.block(ref)
    assert body.count("<<<") == 1 and body.count(">>>") == 1               # only the block's own markers


def test_control_and_format_characters_become_question_marks(env, tmp_path):
    register(env, "r", make_ref(tmp_path, "r", readme="ok‮evil​ \x1b[31m red\r\nline\r2\n"))
    readme = env.new(refs=["r"]).data["refs"][0]["readme"]
    assert "‮" not in readme and "​" not in readme and "\x1b" not in readme and "\r" not in readme
    assert "ok?evil? ?[31m red\nline\n2" in readme


def test_a_path_with_a_newline_is_escaped_and_a_non_utf8_path_does_not_crash(env, tmp_path):
    ref = make_ref(tmp_path, "r")
    open(os.path.join(os.fsencode(str(ref)), b"bad\xff.txt"), "wb").write(b"1")
    (ref / "line\nbreak.txt").write_text("1")
    git(ref, "add", "-A"); git(ref, "commit", "-qm", "odd")
    register(env, "r", ref)
    files = env.new(refs=["r"]).data["refs"][0]["files"].split("\n")
    assert "bad\\xff.txt" in files and "line\\nbreak.txt" in files and not any(f.startswith("break") for f in files)


def test_a_non_utf8_readme_is_refused(env, tmp_path):
    register(env, "r", make_ref(tmp_path, "r", readme=b"\xff\xfe\x00bad"))
    with pytest.raises(rj.Refused, match="not UTF-8"):
        env.new(refs=["r"])
    assert not (env.jobs / "jp").exists()


def test_a_symlink_readme_is_not_read_and_the_files_are_still_listed(env, tmp_path):
    ref = make_ref(tmp_path, "r", readme=None)
    (ref / "secret.txt").write_text("TOP SECRET")
    os.symlink("secret.txt", ref / "README.md")
    git(ref, "add", "-A"); git(ref, "commit", "-qm", "link")
    register(env, "r", ref)
    got = env.new(refs=["r"]).data["refs"][0]
    assert got["readme"] is None and "TOP SECRET" not in json.dumps(got) and "secret.txt" in got["files"]


def test_a_submodule_readme_entry_is_not_read(env, tmp_path):
    ref = make_ref(tmp_path, "r", readme=None)
    git(ref, "update-index", "--add", "--cacheinfo", "160000", "a" * 40, "README.md")
    git(ref, "commit", "-qm", "submodule")
    register(env, "r", ref)
    assert env.new(refs=["r"]).data["refs"][0]["readme"] is None


def test_a_huge_readme_is_refused_before_it_is_read_and_a_long_one_is_cut(env, tmp_path):
    register(env, "big", make_ref(tmp_path, "big", readme="x" * ((1 << 20) + 1)))
    with pytest.raises(rj.Refused, match="1 MiB"):
        env.new(refs=["big"])
    register(env, "long", make_ref(tmp_path, "long", readme="y" * 9000))
    readme = pj.new(repo="demo", message="m", cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs, queues_dir=env.queues, job_id="jq", refs=["long"]).data["refs"][0]["readme"]
    assert len(readme) == pr.README_MAX + len(pr.CUT) and readme.endswith(pr.CUT) and set(readme[:-len(pr.CUT)]) == {"y"}


def test_the_file_list_is_cut_by_count_and_by_characters(env, tmp_path):
    many = {f"f/{i:04d}.txt": "1" for i in range(260)}
    register(env, "many", make_ref(tmp_path, "many", files=many))
    files = env.new(refs=["many"]).data["refs"][0]["files"]
    assert files.count("\n") <= pr.FILES_MAX and "(and " in files and len(files) <= pr.FILES_CHARS + 30
    got = pr._paths(str(tmp_path / "many"), git(tmp_path / "many", "rev-parse", "HEAD").decode().strip())
    assert got == files                                                     # deterministic


def test_no_readme_gives_files_only_and_an_empty_repository_is_refused(env, tmp_path):
    register(env, "nr", make_ref(tmp_path, "nr", readme=None))
    got = env.new(refs=["nr"]).data["refs"][0]
    assert got["readme"] is None and "Its README.md" not in pr.block(got)
    empty = tmp_path / "empty"
    empty.mkdir()
    git(empty, "init", "-q", "-b", "main")
    register(env, "empty", empty)
    with pytest.raises(rj.Refused):
        pj.new(repo="demo", message="m", cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs, queues_dir=env.queues, job_id="jq", refs=["empty"])


def test_an_inherited_git_dir_does_not_redirect_the_read(env, tmp_path, monkeypatch):
    other = make_ref(tmp_path, "other", readme="OTHER REPO README\n")
    register(env, "r", make_ref(tmp_path, "r"))
    monkeypatch.setenv("GIT_DIR", str(other / ".git"))
    got = pr.read(env.cfg, "r", target="demo")
    assert "OTHER REPO" not in json.dumps(got) and "expenses are positive" in got["readme"]


def test_the_reference_is_read_from_head_not_the_working_tree(env, tmp_path):
    ref = make_ref(tmp_path, "r")
    (ref / "README.md").write_text("UNCOMMITTED EDIT\n")
    register(env, "r", ref)
    assert "UNCOMMITTED" not in env.new(refs=["r"]).data["refs"][0]["readme"]


def test_references_that_are_too_big_for_the_input_budget_are_refused(env, tmp_path):
    for n in "ab":
        register(env, n, make_ref(tmp_path, n, readme="z" * 8000, files={f"d/{i}/{'p' * 150}": "1" for i in range(60)}))
    env.cfg["prd_writer"]["turn"]["max_input_tokens"] = 6000
    with pytest.raises(rj.Refused, match="a quarter"):
        env.new(refs=["a", "b"])


def test_refs_keep_the_cli_order_and_validation_rejects_a_damaged_job(env, tmp_path):
    register(env, "b", make_ref(tmp_path, "b"))
    register(env, "a", make_ref(tmp_path, "a"))
    job = env.new(refs=["b", "a"])
    assert [r["name"] for r in job.data["refs"]] == ["b", "a"]
    for bad in ("x", [1], [{"name": "a"}], [{"name": "a", "commit": "c", "files": "f", "readme": 5}], job.data["refs"] * 2):
        assert not pr.valid(bad)
    job.data["refs"] = [{"name": "a"}]
    with pytest.raises(rj.Refused, match="not a PRD job's"):
        pj._valid(job)


def test_the_target_snapshot_does_not_contain_the_reference(env, tmp_path):
    register(env, "r", make_ref(tmp_path, "r", readme="REF ONLY MARKER\n"))
    job = env.new(refs=["r"])
    src = Path(job.runs) / f"{job.id}-w1" / "source"
    assert src.is_dir() and not any("REF ONLY MARKER" in p.read_text(errors="ignore") for p in src.rglob("*") if p.is_file())


def test_a_commit_with_no_files_and_no_readme_is_refused(env, tmp_path):
    empty = tmp_path / "emptycommit"
    empty.mkdir()
    git(empty, "init", "-q", "-b", "main")
    git(empty, "commit", "-q", "--allow-empty", "-m", "nothing")
    register(env, "emptycommit", empty)
    with pytest.raises(rj.Refused, match="neither files nor"):
        env.new(refs=["emptycommit"])
