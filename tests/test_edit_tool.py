"""EditFile: one exact, unique replacement under the same scope rules as WriteFile, and safe to run again after a
crash (a journal outside the workspace, keyed by the tool step's memo key). The ledger records what the provider says
about how a reply ended (reasoning tokens, stop reason). Cross-process crash tests are in tests/test_codetask_crash.py."""
import copy
import json
import sys
from pathlib import Path

import pytest

from codetask.tools import Toolbox, offered
from harness.events import EventLog

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="the path jail needs openat; the VM runs these")

CONTRACT = {"contract": "t", "scope": {"writable": ["src/**"], "protected": ["tests/**"]}, "validation": []}
A = "def f(x):\n    return x\n\n\ndef g(x):\n    return x\n"


class Crash(BaseException):
    pass


class CrashAt:
    def __init__(self, point):
        self.target = point

    def point(self, name, **meta):
        if name == self.target:
            raise Crash(name)


def setup(tmp_path, crasher=None, allowed=("read_file", "write_file", "edit_file"), journal=True):
    ws = tmp_path / "ws"
    (ws / "src").mkdir(parents=True)
    (ws / "tests").mkdir()
    (ws / "src" / "a.py").write_text(A)
    (ws / "tests" / "t.py").write_text("x = 1\n")
    box = Toolbox(str(ws), CONTRACT, {}, allowed, EventLog(tmp_path / "e.jsonl"),
                  journal=tmp_path / "journal.jsonl" if journal else None, crasher=crasher)
    return box, ws


def edit(box, path, old, new, key="k1"):
    return box.run({"name": "EditFile", "args": {"path": path, "old_text": old, "new_text": new}, "id": "c"},
                   step_key=key)["content"]


def test_a_unique_piece_of_text_is_replaced(tmp_path):
    box, ws = setup(tmp_path)
    out = edit(box, "src/a.py", "def f(x):\n    return x\n", "def f(x):\n    return x + 1\n")
    assert out.startswith("src/a.py edited: 1 occurrence replaced")
    assert (ws / "src" / "a.py").read_text() == A.replace("return x\n", "return x + 1\n", 1)


@pytest.mark.parametrize("old,why", [("nowhere", "was not found"), ("    return x\n", "occurs 2 times")])
def test_missing_or_ambiguous_text_changes_nothing(tmp_path, old, why):
    box, ws = setup(tmp_path)
    out = edit(box, "src/a.py", old, "X")
    assert why in out and "nothing changed" in out.lower()
    assert (ws / "src" / "a.py").read_text() == A and not (tmp_path / "journal.jsonl").exists()


@pytest.mark.parametrize("path,why", [
    ("tests/t.py", "is protected"),
    ("README.md", "outside the writable scope"),
    ("SUMMARY.json", "written by Finish"),
    ("../outside.py", "Refused"),
    ("/etc/passwd", "Refused"),
    ("src/missing.py", "No such file"),
])
def test_the_write_scope_and_the_path_jail_hold(tmp_path, path, why):
    box, ws = setup(tmp_path)
    assert why in edit(box, path, "x", "y")
    assert (ws / "src" / "a.py").read_text() == A and (ws / "tests" / "t.py").read_text() == "x = 1\n"


def test_a_symlink_in_the_writable_scope_is_not_followed(tmp_path):
    box, ws = setup(tmp_path)
    secret = tmp_path / "secret.py"
    secret.write_text("SECRET = 1\n")
    (ws / "src" / "link.py").symlink_to(secret)
    assert "Refused" in edit(box, "src/link.py", "SECRET = 1", "SECRET = 2")
    assert secret.read_text() == "SECRET = 1\n"


@pytest.mark.parametrize("args,why", [
    ({"path": "src/a.py", "old_text": "", "new_text": "x"}, "must not be empty"),
    ({"path": "src/a.py", "old_text": "def f", "new_text": "def f"}, "the same"),
    ({"path": "src/a.py", "old_text": 1, "new_text": "x"}, "needs a string"),
])
def test_malformed_edits_are_rejected(tmp_path, args, why):
    box, ws = setup(tmp_path)
    out = box.run({"name": "EditFile", "args": args, "id": "c"}, step_key="k")["content"]
    assert why in out and (ws / "src" / "a.py").read_text() == A


def test_without_a_journal_or_a_step_key_an_edit_is_refused(tmp_path):
    box, ws = setup(tmp_path, journal=False)
    assert "no step journal" in edit(box, "src/a.py", "def f", "def h")
    box, ws = setup(tmp_path / "2")
    assert "no step journal" in edit(box, "src/a.py", "def f", "def h", key=None)
    assert (ws / "src" / "a.py").read_text() == A


def test_edit_file_is_offered_and_allowed_only_when_granted(tmp_path):
    from codetask.tools import EditFile
    assert EditFile not in offered(["read_file", "write_file"]) and EditFile in offered(["edit_file"])
    box, ws = setup(tmp_path, allowed=("read_file", "write_file"))
    assert edit(box, "src/a.py", "def f", "def h").startswith("Denied")
    assert (ws / "src" / "a.py").read_text() == A


# ---- safe to run again: the journal (docs in codetask/tools.py) -------------------------------------------------

INSERT_OLD, INSERT_NEW = "def g(x):\n", "def g(x):\n    # g is the identity\n"     # new_text contains old_text


def test_an_insertion_run_again_for_the_same_step_is_applied_once(tmp_path):
    box, ws = setup(tmp_path)
    first = edit(box, "src/a.py", INSERT_OLD, INSERT_NEW)
    again = edit(box, "src/a.py", INSERT_OLD, INSERT_NEW)          # the step ran, its result was not committed
    assert again == first
    assert (ws / "src" / "a.py").read_text().count("# g is the identity") == 1


def test_the_same_edit_in_another_step_is_a_new_edit(tmp_path):
    box, ws = setup(tmp_path)
    edit(box, "src/a.py", INSERT_OLD, INSERT_NEW, key="step-3")
    edit(box, "src/a.py", INSERT_OLD, INSERT_NEW, key="step-5")
    assert (ws / "src" / "a.py").read_text().count("# g is the identity") == 2


def test_a_crash_between_journal_and_write_makes_the_edit_once_on_resume(tmp_path):
    box, ws = setup(tmp_path, crasher=CrashAt("edit@after_journal"))
    with pytest.raises(Crash):
        edit(box, "src/a.py", INSERT_OLD, INSERT_NEW)
    assert (ws / "src" / "a.py").read_text() == A                     # recorded, not yet written
    assert len((tmp_path / "journal.jsonl").read_text().splitlines()) == 1
    box.crasher = None
    edit(box, "src/a.py", INSERT_OLD, INSERT_NEW)
    assert (ws / "src" / "a.py").read_text().count("# g is the identity") == 1
    assert len((tmp_path / "journal.jsonl").read_text().splitlines()) == 1


def test_a_file_changed_after_the_edit_was_recorded_is_refused(tmp_path):
    box, ws = setup(tmp_path, crasher=CrashAt("edit@after_journal"))
    with pytest.raises(Crash):
        edit(box, "src/a.py", INSERT_OLD, INSERT_NEW)
    (ws / "src" / "a.py").write_text(A + "\n# changed by someone else\n")
    box.crasher = None
    assert "changed after this edit was recorded" in edit(box, "src/a.py", INSERT_OLD, INSERT_NEW)
    assert (ws / "src" / "a.py").read_text() == A + "\n# changed by someone else\n"


def test_a_journal_line_cut_off_by_a_crash_is_ignored(tmp_path):
    box, ws = setup(tmp_path)
    (tmp_path / "journal.jsonl").write_text('{"key": "half')
    edit(box, "src/a.py", INSERT_OLD, INSERT_NEW)
    assert (ws / "src" / "a.py").read_text().count("# g is the identity") == 1


# ---- an end-to-end run through the agent loop (fake model, fake validation) -----------------------------------

def test_a_contract_can_grant_edit_file_and_the_agent_loop_passes_the_step_key(tmp_path):
    from codetask.run import run_code_task
    from models.fake import StrictScriptedChatModel, reply
    from runner import load_config
    root = Path(__file__).resolve().parent.parent
    contract = json.loads((root / "fixtures/contracts/fix_divide.json").read_text(encoding="utf-8"))
    contract["tools"] = ["edit_file"]
    calc = (root / "fixtures/repos/calc/src/calc.py").read_text(encoding="utf-8")
    fixed = calc.replace("    if b == 0:\n        return 0\n", "")

    def call(name, args, id):
        return reply(tool_calls=[{"name": name, "args": args, "id": id}], input_tokens=500, output_tokens=60)

    def validate(spec, workspace, sandbox_cfg, log=None):
        ok = (Path(workspace) / "src" / "calc.py").read_text() == fixed
        return {"id": f"validation:{spec['id']}", "layer": "C", "status": "pass" if ok else "fail",
                "reason": "" if ok else "not fixed",
                "evidence": {"must_pass": {t: "ok" if ok else "FAIL" for t in spec.get("must_pass", [])},
                             "tests_run": 7, "failures": 0 if ok else 1, "output_tail": ""}}

    claims = [{"claim": "file_changed", "path": "src/calc.py"}, {"claim": "issue_fixed", "evidence": "validation:target"}]
    model = StrictScriptedChatModel(script=[
        call("EditFile", {"path": "src/calc.py", "old_text": "    if b == 0:\n        return 0\n", "new_text": ""}, "e1"),
        call("Finish", {"claims": claims, "summary": "divide raises on zero"}, "f1")])
    cfg = load_config()
    cfg["roles"]["coder"]["model"] = "fake:scripted"
    path = tmp_path / "c.json"
    path.write_text(json.dumps(contract), encoding="utf-8")
    r = run_code_task(contract_path=path, run_id="e", runs_dir=tmp_path / "runs", cfg=cfg, models={"coder": model},
                      validate=validate, preflight=lambda: (True, "ok"))
    assert r["status"] == "DONE" and "edit_file" in r["tools"]
    assert "EditFile" in [t.__name__ for t in model.bound_tools]
    assert "EditFile: replace one exact piece of text" in model.calls[0]["messages"][0].content
    journal = [json.loads(line) for line in (tmp_path / "runs" / "e" / "tool_journal.jsonl").read_text().splitlines()]
    assert len(journal) == 1 and journal[0]["path"] == "src/calc.py"
    assert not (tmp_path / "runs" / "e" / "workspace" / "tool_journal.jsonl").exists()   # outside the workspace
    calls = [json.loads(line) for line in (tmp_path / "runs" / "e" / "events.jsonl").read_text().splitlines()
             if '"event": "llm_call"' in line]
    assert calls and all("reasoning_tokens" in e and "stop_reason" in e for e in calls)


def test_reply_details_reports_what_the_provider_said_and_none_otherwise():
    from langchain_core.messages import AIMessage
    from harness.llm import reply_details
    m = AIMessage(content="", usage_metadata={"input_tokens": 9418, "output_tokens": 4096, "total_tokens": 13514,
                                             "output_token_details": {"reasoning": 2505}},
                  response_metadata={"stop_reason": "max_tokens"})
    assert reply_details(m) == {"reasoning_tokens": 2505, "stop_reason": "max_tokens"}
    assert reply_details(AIMessage(content="x")) == {"reasoning_tokens": None, "stop_reason": None}
    assert reply_details(AIMessage(content="x", response_metadata={"finish_reason": "length"}))["stop_reason"] == "length"


# ---- large files (SWE batch 5: sympy files of 117-182 KB were refused, so agents could not apply a fix they had found) --

def _big(n_bytes):
    body, i = [], 0
    while sum(map(len, body)) < n_bytes:
        body.append(f"def f{i}(x):\n    return x + {i}\n\n\n")
        i += 1
    return "".join(body)


@pytest.mark.parametrize("size", [150_000, 250_000])     # over MAX_READ; the second also over MAX_WRITE
def test_a_file_larger_than_a_read_or_a_write_is_edited_in_place(tmp_path, size):
    import codetask.tools as ct
    assert size > ct.MAX_READ and size < ct.EDIT_MAX_FILE
    box, ws = setup(tmp_path)
    text = _big(size)
    (ws / "src" / "big.py").write_text(text)
    out = edit(box, "src/big.py", "def f7(x):\n    return x + 7\n", "def f7(x):\n    return x - 7\n")
    assert out.startswith("src/big.py edited: 1 occurrence replaced"), out
    assert (ws / "src" / "big.py").read_text() == text.replace("return x + 7\n", "return x - 7\n", 1)


def test_a_file_over_the_edit_limit_is_refused_and_left_as_it_was(tmp_path, monkeypatch):
    import codetask.tools as ct
    monkeypatch.setattr(ct, "EDIT_MAX_FILE", 50_000)
    box, ws = setup(tmp_path)
    text = _big(60_000)
    (ws / "src" / "big.py").write_text(text)
    out = edit(box, "src/big.py", "def f7(x):\n    return x + 7\n", "def f7(x):\n    return x - 7\n")
    assert "larger than 50000 bytes" in out
    assert (ws / "src" / "big.py").read_text() == text


def test_an_edit_that_would_grow_a_file_over_the_limit_changes_nothing(tmp_path, monkeypatch):
    import codetask.tools as ct
    monkeypatch.setattr(ct, "EDIT_MAX_FILE", 50_000)
    box, ws = setup(tmp_path)
    text = _big(45_000)
    (ws / "src" / "big.py").write_text(text)
    out = edit(box, "src/big.py", "def f7(x):\n", "def f7(x):\n" + "    # pad\n" * 1000)
    assert "would be larger than 50000 bytes; nothing changed" in out
    assert (ws / "src" / "big.py").read_text() == text
