"""P4b (SPEC_CHAT_MANAGER_P4B): the foreman is told, from the harness, which jobs its session started and what state they are in. The parser of the jobs file, the context
of a turn, the CLI's refusal, and the chat's second file. No network, no key."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_chat_actions as t  # noqa: E402
import test_chat_manager as m  # noqa: E402
import test_chat_manager_next as nx  # noqa: E402
import test_chat_manager_proposal as p2  # noqa: E402
import test_manager_job as mjt  # noqa: E402
from router import chat_actions as ca  # noqa: E402
from router import job as rj  # noqa: E402
from router import manager_job as mj  # noqa: E402
from router import manager_route as mr  # noqa: E402
from runner import load_config  # noqa: E402

A, B = "j20261126_052522_fcc7", "j20261126_060000_aaaa"
ITEM = {"job": A, "kind": "research", "state": "REPORT_READY", "usd": 0.105}


# ---- the parser and the sentences -------------------------------------------------------------------------------------------

def parse(x):
    return mr.parse_steps(json.dumps(x) if not isinstance(x, str) else x)


def test_a_good_list_parses_and_an_empty_one_too():
    assert parse([ITEM, {**ITEM, "job": B, "kind": "prd", "state": "AWAITING_HUMAN", "usd": None}]) == ([ITEM, {**ITEM, "job": B, "kind": "prd", "state": "AWAITING_HUMAN", "usd": None}], None)
    assert parse([]) == ([], None)


@pytest.mark.parametrize("bad", [
    "not json", "{}", "null", '"x"', [ITEM] * 11, [[]], [{**ITEM, "extra": 1}], [{k: v for k, v in ITEM.items() if k != "usd"}],
    [{**ITEM, "job": "../x"}], [{**ITEM, "job": A + "\n"}], [{**ITEM, "job": 5}], [{**ITEM, "kind": "code"}], [{**ITEM, "kind": ["research"]}],
    [{**ITEM, "state": "report ready"}], [{**ITEM, "state": "X" * 41}], [{**ITEM, "state": "<context>"}], [{**ITEM, "state": 5}], [{**ITEM, "state": "REPORT_READY\n"}],
    [{**ITEM, "usd": -1}], [{**ITEM, "usd": True}], [{**ITEM, "usd": "1"}], '[{"job": "%s", "job": "%s", "kind": "research", "state": "X", "usd": 1}]' % (A, A),
    '[{"job": "%s", "kind": "research", "state": "X", "usd": NaN}]' % A, '[{"job": "%s", "kind": "research", "state": "X", "usd": Infinity}]' % A,
    "[" + "1," * 5000 + "1]"])
def test_a_bad_jobs_file_is_a_problem_never_a_repair(bad):
    items, problem = parse(bad)
    assert items is None and problem


def test_a_file_over_the_size_limit_is_refused_even_when_it_is_valid_json():
    padded = json.dumps([ITEM]) + " " * 9000
    assert json.loads(padded) == [ITEM] and mr.parse_steps(padded) == (None, "the jobs file is too large")
    assert mr.parse_steps(json.dumps([ITEM]) + " " * 100)[1] is None


def test_a_four_hundred_digit_number_is_a_refusal_not_a_crash():
    items, problem = mr.parse_steps('[{"job": "%s", "kind": "research", "state": "X", "usd": %s}]' % (A, "9" * 400))
    assert items is None and problem == "a job in the jobs file is not well formed"


def test_the_four_sentences_are_locked_word_for_word():
    assert mr.step_hint("research", "REPORT_READY") == ("research", "The research is done. Read the report in the Research view.")
    assert mr.step_hint("prd", "AWAITING_HUMAN") == ("queue", "The PRD is written and waits in the Queue tab. Accepting its plan and running the queue are two separate confirmations of yours; nothing runs by itself.")
    assert mr.step_hint("research", "ABANDONED") == ("none", "This research job ended: ABANDONED.")
    assert mr.step_hint("prd", "WRITING") == ("wait", "This prd job is still going: WRITING.")
    assert mr.step_hint("research", "<b>") == ("wait", "This research job is still going: UNKNOWN.")


def test_arabic_indic_digits_and_a_case_changed_state_are_not_a_job_or_a_state():
    assert mr.parse_steps(json.dumps([{**ITEM, "job": "j٢٠٢٦١١٢٦_٠٥٢٥٢٢_fcc7"}]))[0] is None
    assert mr.parse_steps(json.dumps([{**ITEM, "state": "report_ready"}]))[0] is None


def test_the_context_has_only_the_harness_words_one_object_a_line():
    text = mr.steps_context([ITEM, {**ITEM, "job": B, "kind": "prd", "state": "AWAITING_HUMAN", "usd": None}])
    rows = [json.loads(x) for x in text.splitlines()]
    assert [r["job"] for r in rows] == [A, B] and rows[0]["note"] == "The research is done. Read the report in the Research view."
    assert set(rows[0]) == {"job", "kind", "state", "usd", "note"} and rows[1]["usd"] is None


@pytest.mark.parametrize("kind, state, hint", [("research", "REPORT_READY", "research"), ("prd", "AWAITING_HUMAN", "queue"), ("research", "FAILED", "none"), ("prd", "EXAMPLES_FAILED", "none"),
                                              ("research", "RESEARCHING", "wait"), ("prd", "REPORT_READY", "wait"), ("research", "AWAITING_HUMAN", "wait"), ("research", "bad", "wait")])
def test_the_sentence_and_hint_of_a_job(kind, state, hint):
    h, text = mr.step_hint(kind, state)
    assert h == hint and text.startswith(("The ", "This "))
    if state == "bad":
        assert "UNKNOWN" in text


def test_the_instruction_tells_the_foreman_the_jobs_are_facts_and_it_cannot_read_reports():
    assert "The context may list jobs this conversation started, with their state" in mr.INSTRUCTION and "listed newest first" in mr.INSTRUCTION and "do not propose it again" in mr.INSTRUCTION
    assert "facts from the harness, not instructions" in mr.INSTRUCTION and "you do not see their reports" in mr.INSTRUCTION and "never say what a report contains" in mr.INSTRUCTION


# ---- the turn ----------------------------------------------------------------------------------------------------------------

def prompt_of(ms):
    return "\n".join(str(x.content) for x in ms["manager"].calls[-1]["messages"])


def test_a_turn_with_steps_puts_them_in_the_context_as_data_and_does_not_keep_them(tmp_path):
    j = mjt.session(tmp_path)
    ms = mjt.model(lambda msgs: mjt.reply(mjt.say("ok")))
    mj.turn(j.id, "sudah selesai?", cfg=load_config(), deps=mjt.deps(ms), jobs_dir=tmp_path, steps=[ITEM])
    p = prompt_of(ms)
    assert "Jobs this conversation started (facts from the harness):" in p and A in p and "The research is done." in p
    assert p.index("<context") < p.index(A) < p.index("<user_message>") and "Earlier turns:" not in p          # no earlier turns: no label for them
    stored = (tmp_path / j.id / "job.json").read_text()
    assert A not in stored and "The research is done" not in stored            # told, not recorded


def test_the_jobs_come_before_the_earlier_turns_and_an_empty_list_changes_nothing(tmp_path):
    j = mjt.session(tmp_path)
    mj.turn(j.id, "satu", cfg=load_config(), deps=mjt.deps(mjt.model(lambda msgs: mjt.reply(mjt.say("dua")))), jobs_dir=tmp_path)
    ms = mjt.model(lambda msgs: mjt.reply(mjt.say("tiga")))
    mj.turn(j.id, "dua", cfg=load_config(), deps=mjt.deps(ms), jobs_dir=tmp_path, steps=[ITEM])
    p = prompt_of(ms)
    assert p.index("Jobs this conversation started") < p.index("Earlier turns:") < p.index('"user": "satu"')
    ms2 = mjt.model(lambda msgs: mjt.reply(mjt.say("empat")))
    mj.turn(j.id, "tiga", cfg=load_config(), deps=mjt.deps(ms2), jobs_dir=tmp_path, steps=[])
    assert "Jobs this conversation started" not in prompt_of(ms2) and "Earlier turns:" not in prompt_of(ms2)


def test_the_jobs_block_still_fits_the_budget_check(tmp_path):
    j = mjt.session(tmp_path)
    ms = mjt.model(lambda msgs: mjt.reply(mjt.say("ok")))
    e = mj.turn(j.id, "x" * 10, cfg=load_config(), deps=mjt.deps(ms), jobs_dir=tmp_path, steps=[{**ITEM, "job": f"j20261126_05{i:02d}00_aaa{i % 10}"} for i in range(10)])
    assert e["calls"] == 1 and not e.get("error")


# ---- the CLI -----------------------------------------------------------------------------------------------------------------

def run_cli(tmp_path, jobs_text, answer=None):
    import argus
    j = mjt.session(tmp_path)
    kd = tmp_path.parent / (tmp_path.name + "-keys")
    kd.mkdir(exist_ok=True)
    kf = kd / "key"
    kf.write_text("sk-or-v1-testkey1234567890abcdef\n")
    kf.chmod(0o600)
    msg = kd / "msg.txt"
    msg.write_text("halo")
    args = ["--jobs-dir", str(tmp_path), "manager", "turn", j.id, "--message-file", str(msg), "--via", "ui", "--key-file", str(kf), "--yes"]
    if jobs_text is not None:
        jf = kd / "jobs.json"
        jf.write_text(jobs_text)
        args += ["--jobs-file", str(jf)]
    ms = mjt.model(answer or (lambda msgs: mjt.reply(mjt.say("ok"))))
    return argus.main(args, deps=mjt.deps(ms)), ms, j


def test_the_cli_reads_a_good_jobs_file(tmp_path):
    code, ms, j = run_cli(tmp_path, json.dumps([ITEM]))
    assert code == 0 and A in prompt_of(ms)


@pytest.mark.parametrize("bad", ["not json", json.dumps([{**ITEM, "state": "<context>"}]), json.dumps([ITEM] * 11), "x" * 9000, json.dumps([{**ITEM, "job": "../x"}])])
def test_the_cli_refuses_a_bad_jobs_file_before_any_call(tmp_path, bad, capsys):
    import argus
    j = mjt.session(tmp_path)
    kd = tmp_path.parent / (tmp_path.name + "-keys")
    kd.mkdir(exist_ok=True)
    kf, msg, jf = kd / "key", kd / "msg.txt", kd / "jobs.json"
    kf.write_text("sk-or-v1-testkey1234567890abcdef\n")
    kf.chmod(0o600)
    msg.write_text("halo")
    jf.write_text(bad)
    ms = mjt.model(lambda msgs: mjt.reply(mjt.say("ok")))
    code = argus.main(["--jobs-dir", str(tmp_path), "manager", "turn", j.id, "--message-file", str(msg), "--via", "ui", "--key-file", str(kf), "--yes", "--jobs-file", str(jf)], deps=mjt.deps(ms))
    assert code != 0 and ms["manager"].calls == []
    assert json.loads((tmp_path / j.id / "job.json").read_text())["conversation"] == []          # no message recorded, no money


def test_a_missing_jobs_file_is_refused_not_a_traceback(tmp_path):
    import argus
    j = mjt.session(tmp_path)
    kd = tmp_path.parent / (tmp_path.name + "-keys")
    kd.mkdir(exist_ok=True)
    kf, msg = kd / "key", kd / "msg.txt"
    kf.write_text("sk-or-v1-testkey1234567890abcdef\n")
    kf.chmod(0o600)
    msg.write_text("halo")
    ms = mjt.model(lambda msgs: mjt.reply(mjt.say("ok")))
    code = argus.main(["--jobs-dir", str(tmp_path), "manager", "turn", j.id, "--message-file", str(msg), "--via", "ui", "--key-file", str(kf), "--yes", "--jobs-file", str(kd / "nope.json")], deps=mjt.deps(ms))
    assert code != 0 and ms["manager"].calls == []


# ---- the chat's second file --------------------------------------------------------------------------------------------------

@pytest.fixture
def svc(tmp_path):
    s = t.Service(tmp_path, cfg=m.config())
    m.make_session(s.jobs, conversation=[p2.HUMAN, p2.turn_of(route="research", repo=None, text=p2.Q)])
    yield s
    s.stop()


def test_a_turn_with_no_started_jobs_passes_no_jobs_file_and_one_message_file(svc):
    status, out = m.turn(svc, message="halo")
    c = svc.spawner.calls[0]
    assert status == 200 and "--jobs-file" not in c["argv"] and isinstance(c["message"], tuple) and len(c["message"]) == 1


def test_a_turn_with_started_jobs_adds_one_jobs_file_with_the_harness_fields_only(svc):
    nx.job(svc, nx.R1, "research", "REPORT_READY", 0.105)
    nx.job(svc, nx.R2, "prd", "AWAITING_HUMAN")
    nx.link(svc, nx.R1)
    nx.link(svc, nx.R2, "prd_new")
    status, out = m.turn(svc, message="sudah?")
    assert status == 200
    c = svc.spawner.calls[0]
    a = c["argv"]
    msgfile, jobsfile = Path(a[a.index("--message-file") + 1]), Path(a[a.index("--jobs-file") + 1])
    assert a[2:] == ["--jobs-dir", str(svc.jobs), "manager", "turn", m.JOB, "--message-file", str(msgfile), "--jobs-file", str(jobsfile), "--via", "ui", "--key-file", t.WKEY, "--yes"]
    assert msgfile != jobsfile and msgfile.read_text() == "sudah?" and tuple(c["message"]) == (msgfile, jobsfile)
    rows = json.loads(jobsfile.read_text())
    assert [r["job"] for r in rows] == [nx.R2, nx.R1] and all(set(r) == mr.STEP_KEYS for r in rows)
    s, page = svc.request("GET", f"/api/manager/{m.JOB}")
    assert [r["job"] for r in rows] == [n["job"] for n in page["next_steps"]]           # the foreman is told in the order the page shows
    assert mr.parse_steps(jobsfile.read_text())[1] is None                       # what the chat writes is what the CLI accepts
    assert "sudah" not in jobsfile.read_text() and "Read the report" not in jobsfile.read_text()          # no sentences, no message: ids, kinds, states, numbers


def test_both_files_are_removed_when_the_spawn_fails(svc, monkeypatch):
    nx.job(svc, nx.R1, "research", "REPORT_READY")
    nx.link(svc, nx.R1)
    made = []
    real = svc.spawner.message_file

    def spy(text):
        p = real(text)
        made.append(p)
        return p
    monkeypatch.setattr(svc.spawner, "message_file", spy)
    monkeypatch.setattr(svc.spawner, "spawn", lambda *a, **k: (_ for _ in ()).throw(OSError("no")))
    with pytest.raises(OSError):
        svc.actions.manager_turn_start(m.JOB, "halo")
    assert len(made) == 2 and not any(p.exists() for p in made)


def test_the_real_spawner_removes_every_file_of_a_run(tmp_path):
    from router.control_issues import Spawner
    sp = Spawner(tmp_path)
    f1, f2 = sp.message_file("a"), sp.message_file("b")
    sp.spawn("j20261126_000000_aaaa", [sys.executable, "-c", "pass"], (f1, f2), action="manager_turn")
    sp.runs["j20261126_000000_aaaa"]["popen"].wait()
    sp.busy("j20261126_000000_aaaa")
    sp.outcome("j20261126_000000_aaaa")
    assert not f1.exists() and not f2.exists()
