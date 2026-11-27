"""SPEC_CHAT_PACKAGES S2: `argus env add` and `argus env abandon`, the `argus status` read that settles a dead env job, and the argv of `env init` and `env propose` that did
not change when `env` became a command with subcommands. The container runner is a fake; the config is a small dict."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import argus  # noqa: E402

from router import env_job as ej  # noqa: E402
from router import job as rj  # noqa: E402
from tests.test_env_job import BASE, NOW, OLD, FakeDocker, cfg_of, deps, job_id  # noqa: E402

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="posix")


@pytest.fixture
def cli(tmp_path, monkeypatch, capsys):
    root, jobs = tmp_path / "root", tmp_path / "jobs"
    d = root / "environments" / "bulking_node22"
    d.mkdir(parents=True)
    (d / "base").write_text(BASE)
    (d / "package.json").write_text(json.dumps({"name": "env"}))
    (d / "package-lock.json").write_text(json.dumps(OLD))
    jobs.mkdir()
    monkeypatch.setattr(rj, "ROOT", root)
    monkeypatch.setattr(argus, "load_config", lambda c=None: cfg_of())
    monkeypatch.setattr(argus, "sandbox_cfg", lambda c=None: cfg_of()["sandbox"])
    plan = {}

    def make(**kw):
        class Patched(ej.Docker):
            def __init__(self):
                self.fake = FakeDocker(**{**plan, **kw})

            def run(self, argv, timeout_s, name):
                return self.fake.run(argv, timeout_s, name)

            def remove(self, name):
                self.fake.remove(name)
        monkeypatch.setattr(ej, "Docker", Patched)

    make()
    pk = tmp_path / "packages.txt"
    pk.write_text("foo\n")

    def run(*args, via_clock=NOW):
        rc = argus.main(["--jobs-dir", str(jobs), *args], deps=deps(via_clock))
        out = capsys.readouterr()
        return rc, out.out, out.err

    run.make, run.jobs, run.pk, run.root = make, jobs, pk, root
    return run


def add(cli, n=0, *extra, text=None):
    if text is not None:
        cli.pk.write_text(text)
    return cli("env", "add", "--repo", "bulking-app", "--job-id", job_id(n), "--packages-file", str(cli.pk), "--via", "ui", "--yes", *extra)


def test_add_resolves_and_prints_the_status(cli):
    rc, out, err = add(cli)
    assert rc == 0 and f"job {job_id()}: AWAITING_HUMAN (env)" in out and "report: OK" in out and "money: none" in out
    assert rj.open_job(job_id(), cli.jobs).data["state"] == "AWAITING_HUMAN"


def test_a_refused_report_exits_one_and_says_why(cli):
    cli.make(install_rc=1, install_log="npm error code ETARGET")
    rc, out, err = add(cli)
    assert rc == 1 and "REFUSED (env)" in out and "BLOCK no version of that package is old enough" in out


@pytest.mark.parametrize("text", ["foo@^1.0.0", "", "react", "a\nb\nc\nd\ne\nf"])
def test_a_bad_request_is_a_refusal_and_makes_no_job(cli, text):
    rc, out, err = add(cli, text=text)
    assert rc == 2 and err.startswith("refused:") and "nothing was started" in err
    assert [p.name for p in cli.jobs.iterdir() if p.is_dir()] == []


def test_the_packages_file_is_bounded_and_must_be_text(cli):
    cli.pk.write_bytes(b"foo\n" + b"x" * 5000)
    rc, out, err = add(cli)
    assert rc == 2 and "larger than 4 KB" in err
    cli.pk.write_bytes(b"\xff\xfe\x00foo")
    rc, out, err = add(cli)
    assert rc == 2 and "cannot be read as text" in err
    cli.pk.unlink()
    rc, out, err = add(cli)
    assert rc == 2 and "cannot be read as text" in err


@pytest.mark.parametrize("drop", ["--repo", "--job-id", "--packages-file", "--via", "--yes"])
def test_every_option_of_add_is_required(cli, drop):
    args = ["env", "add", "--repo", "bulking-app", "--job-id", job_id(), "--packages-file", str(cli.pk), "--via", "ui", "--yes"]
    if drop == "--yes":
        args.remove("--yes")
    else:
        i = args.index(drop)
        del args[i:i + 2]
    with pytest.raises(SystemExit) as e:
        argus.main(["--jobs-dir", str(cli.jobs), *args], deps=deps())
    assert e.value.code == 2


def test_via_must_be_ui(cli):
    with pytest.raises(SystemExit):
        argus.main(["--jobs-dir", str(cli.jobs), "env", "add", "--repo", "bulking-app", "--job-id", job_id(), "--packages-file", str(cli.pk), "--via", "cli", "--yes"], deps=deps())


def test_abandon_ends_a_request_and_frees_the_slot(cli):
    add(cli)
    rc, out, err = cli("env", "abandon", job_id(), "--via", "ui", "--yes")
    assert rc == 0 and "ABANDONED" in out
    rc, out, err = add(cli, 1)
    assert rc == 0


def test_abandon_of_an_unknown_job_is_a_refusal(cli):
    rc, out, err = cli("env", "abandon", job_id(9), "--via", "ui", "--yes")
    assert rc == 2 and "refused" in err


def test_status_settles_a_dead_env_job(cli):
    cfg = cfg_of()
    with ej.start(repo="bulking-app", job_id=job_id(), text="foo", cfg=cfg, deps=deps(), jobs_dir=cli.jobs, via="ui", root=cli.root, docker=FakeDocker()):
        pass                                                         # the process "dies": the lock is released and the job stays NEW
    rc, out, err = cli("status", job_id())
    assert rc == 0 and "FAILED (env)" in out and rj.open_job(job_id(), cli.jobs).data["state"] == "FAILED"


def test_status_of_a_live_env_job_is_not_settled(cli):
    cfg = cfg_of()
    with ej.start(repo="bulking-app", job_id=job_id(), text="foo", cfg=cfg, deps=deps(), jobs_dir=cli.jobs, via="ui", root=cli.root, docker=FakeDocker()):
        rc, out, err = cli("status", job_id())
    assert rc == 0 and "NEW (env)" in out


def test_status_of_other_kinds_still_works(cli, tmp_path):
    other = rj.Job(cli.jobs / "j20261127_120000_aaaa")
    with other.lock():
        other.data = {"job": other.dir.name, "kind": "manager", "state": "OPEN", "created_at": NOW, "max_usd": 0.2, "conversation": [], "stages": {}, "log": [],
                      "inputs": {"role": "x", "model": "m", "readable_repos": []}}
        other.save()
    rc, out, err = cli("status", other.dir.name)
    assert rc == 0 and "(manager)" in out


def test_env_propose_keeps_its_argv_with_the_key_options_after_the_subcommand(monkeypatch, tmp_path, capsys):
    import os
    import router.env_propose as ep_
    seen = {}

    def propose(name, **kw):
        seen["call"] = (name, kw["cap_usd"])
        return {"name": "x-app", "description": "d", "billed_usd": 0.0}

    key = tmp_path / "key"
    key.write_text("sk-or-v1-testkey1234567890abcdef\n")
    os.chmod(key, 0o600)
    monkeypatch.setattr(ep_, "propose", propose)
    monkeypatch.setattr(argus, "load_config", lambda c=None: {})
    rc = argus.main(["--jobs-dir", str(tmp_path), "env", "propose", "a small app", "--cap-usd", "0.05", "--key-file", str(key), "--yes"], deps=deps())
    assert rc == 0 and seen["call"] == ("a small app", 0.05) and "argus env init x-app" in capsys.readouterr().out


def test_env_needs_a_known_subcommand(tmp_path):
    for args in (["env"], ["env", "nonsense"], ["env", "init"]):
        with pytest.raises(SystemExit):
            argus.main(["--jobs-dir", str(tmp_path), *args], deps=deps())
