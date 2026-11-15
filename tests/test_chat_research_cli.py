"""C3 (SPEC_CHAT_APP 12, 12.10 items 9 and 10): `argus research --via ui --job-id ID`. The job records where it was started, an id the
chat's daily cap could not find is refused before any job exists, and a second start of the same id cannot overwrite the first."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_research_job as t  # noqa: E402

from router import job as rj  # noqa: E402
from router import research as rr  # noqa: E402

NOW = "2026-11-03T00:00:00Z"
GOOD = "j20261103_000000_ab12"
SCRIPT = [t.PLAN, t.SEARCH, t.FETCH, t.SUBMIT, t.REPORT, t.CHECK]


def start(env, **kw):
    return rr.start(question=t.QUESTION, cfg=env.cfg, deps=env.deps, jobs_dir=env.jobs, **kw)


def created(job):
    return [e for e in job.data["log"] if e["what"] == "created"][0]


def test_a_job_started_with_via_records_it_in_the_created_entry(tmp_path):
    env = t.Env(tmp_path, SCRIPT)
    job = start(env, job_id=GOOD, via="ui")
    assert created(job)["via"] == "ui" and job.id == GOOD and job.data["state"] == rr.REPORT_READY


def test_without_via_the_created_entry_has_no_via_field(tmp_path):
    env = t.Env(tmp_path, SCRIPT)
    assert "via" not in created(start(env, job_id="jr"))


@pytest.mark.parametrize("via", ["web", "UI", "", "ui "])
def test_a_via_that_is_not_ui_creates_no_job(tmp_path, via):
    env = t.Env(tmp_path, [])
    with pytest.raises(rj.Refused, match="via"):
        start(env, job_id=GOOD, via=via)
    assert not (env.jobs / GOOD).exists()


@pytest.mark.parametrize("job_id", [
    GOOD + "\n",                       # rj.JOB_ID's `$` accepts a trailing newline
    "jfoo",                            # a job id the chat's cap never looks at
    "j20261103_000000_AB12", "j20261103_000000_ab1", "j20261103_000000_ab123", "xj20261103_000000_ab12",
    "j20261102_234959_ab12",           # back-dated: ten minutes and more away from now
    "j20261103_001001_ab12",           # in the future
    "j20261399_000000_ab12",           # an impossible date
])
def test_an_id_the_daily_cap_could_not_find_is_refused_with_via(tmp_path, job_id):
    env = t.Env(tmp_path, [])
    with pytest.raises(rj.Refused, match="no job was created"):
        start(env, job_id=job_id, via="ui")
    assert not list(env.jobs.glob("*")) if env.jobs.exists() else True


def test_an_id_within_ten_minutes_either_way_is_accepted(tmp_path):
    for i, jid in enumerate(["j20261102_235501_0001", "j20261103_000959_0002"]):
        env = t.Env(tmp_path / str(i), SCRIPT)
        assert start(env, job_id=jid, via="ui").id == jid


def test_an_id_without_via_keeps_the_old_rule(tmp_path):
    env = t.Env(tmp_path, SCRIPT)
    assert start(env, job_id="jr").id == "jr"


def test_a_second_start_of_an_existing_id_is_refused_and_the_first_record_stays(tmp_path):
    env = t.Env(tmp_path, SCRIPT)
    first = start(env, job_id=GOOD, via="ui")
    again = t.Env(tmp_path / "x", [])
    again.jobs = env.jobs
    with pytest.raises(rj.Refused, match="already exists"):
        start(again, job_id=GOOD, via="ui")
    assert rj.open_job(GOOD, env.jobs).data["log"] == first.data["log"]


def test_the_refusal_inside_the_lock_covers_a_job_that_appeared_after_the_first_check(tmp_path, monkeypatch):
    env = t.Env(tmp_path, [])
    real = rj.Job.lock
    import json as _json

    def lock(self):
        self.dir.mkdir(parents=True, exist_ok=True)
        self.file.write_text(_json.dumps({"job": self.dir.name, "kind": "research", "state": "ABANDONED", "log": []}))
        return real(self)
    monkeypatch.setattr(rj.Job, "lock", lock)
    with pytest.raises(rj.Refused, match="already exists"):
        start(env, job_id=GOOD, via="ui")
    assert _json.loads((env.jobs / GOOD / "job.json").read_text())["state"] == "ABANDONED"


def test_the_cli_takes_via_and_job_id(tmp_path, capsys):
    sys.path.insert(0, str(t.ROOT / "scripts"))
    import argus
    env = t.Env(tmp_path, SCRIPT)
    rc = argus.main(["--jobs-dir", str(env.jobs), "research", "--question", t.QUESTION, "--via", "ui", "--job-id", GOOD], deps=env.deps)
    assert rc == 0 and created(rj.open_job(GOOD, env.jobs))["via"] == "ui"
    with pytest.raises(SystemExit):
        argus.main(["--jobs-dir", str(env.jobs), "research", "--question", t.QUESTION, "--via", "web"], deps=env.deps)


def test_issue_new_also_refuses_a_job_that_appeared_after_the_first_check(tmp_path, monkeypatch):
    import json as _json

    import test_issue_writer as w
    env = w.Env(tmp_path, [])
    real = rj.Job.lock

    def lock(self):
        self.dir.mkdir(parents=True, exist_ok=True)
        self.file.write_text(_json.dumps({"job": self.dir.name, "kind": "issue", "state": "ABANDONED", "log": []}))
        return real(self)
    monkeypatch.setattr(rj.Job, "lock", lock)
    with pytest.raises(rj.Refused, match="already exists"):
        env.new()
    assert _json.loads((env.jobs / "ji" / "job.json").read_text())["state"] == "ABANDONED"
