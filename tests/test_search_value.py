"""The search-value experiment (docs/reviews/TASK_SEARCH_VALUE.md): three contract variants of one task. These tests
hold the acceptance criteria of the design: the variants ask for the same work, B differs from A by exactly one
neutral sentence, no issue names the bug's path, and C keeps every tool except search."""
import ast
import copy
import json
import re
import sys
from pathlib import Path

import pytest

from evals import runner as ev

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "evals" / "search_v1" / "manifest.json"
SENTENCE = "The repository is large; you can search file contents with SearchFiles."
REPO = ROOT / "fixtures" / "repos" / "ledger"
BUG_PATH = ["src/jobs/cycle.py", "src/core/ledger.py", "src/common/options.py", "src/common/settings.py"]


def contracts():
    return {k: json.loads((ROOT / f"fixtures/contracts/ledger_terms_{k}.json").read_text(encoding="utf-8"))
            for k in "abc"}


def test_the_variants_ask_for_the_same_work():
    c = contracts()
    same = {}
    for k, v in c.items():
        v = copy.deepcopy(v)
        v.pop("contract")
        v.pop("tools", None)
        v["inputs"].pop("issue")
        same[k] = v
    assert same["a"] == same["b"] == same["c"]
    assert c["a"]["tools"] == c["b"]["tools"] == ["search_files"] and "tools" not in c["c"]
    assert c["a"]["inputs"]["issue"] == c["c"]["inputs"]["issue"]


def test_b_differs_from_a_by_exactly_the_neutral_sentence():
    c = contracts()
    assert c["b"]["inputs"]["issue"] == c["a"]["inputs"]["issue"] + " " + SENTENCE


def words(text):
    return {w.lower() for w in re.findall(r"[A-Za-z_]+", text)}


def bug_path_names():
    """File stems, function and class names on the bug's path, and the configuration's field names."""
    names = set()
    for rel in BUG_PATH:
        names.add(Path(rel).stem)
        for node in ast.walk(ast.parse((REPO / rel).read_text(encoding="utf-8"))):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                names.add(node.name)
    config = json.loads((REPO / "src" / "config" / "schedules.json").read_text(encoding="utf-8"))
    names |= {"schedules"} | set(config["defaults"])
    return {n.lower() for n in names}


def test_no_issue_names_the_bug_path_and_the_sentence_names_only_the_tool():
    names = bug_path_names()
    assert {"ledger", "merge_options", "prepare_lines", "grace_days"} <= names       # the guard sees the path
    for k, c in contracts().items():
        assert not words(c["inputs"]["issue"]) & names, k
    assert not words(SENTENCE) & (names | words(contracts()["a"]["inputs"]["workspace"])) - {"searchfiles"}


def test_the_manifest_labels_and_scripts_never_reach_the_contracts():
    m = ev.load_manifest(MANIFEST)
    assert [t["contract"] for t in m["tasks"]] == [f"fixtures/contracts/ledger_terms_{k}.json" for k in "abc"]
    for t in m["tasks"]:
        text = (ROOT / t["contract"]).read_text(encoding="utf-8")
        for word in (t["category"], "expected", "reference", "wrong"):
            assert word not in text


def test_the_experiment_is_not_part_of_eval_set_v1():
    v1 = ev.load_manifest(ROOT / "evals" / "v1" / "manifest.json")
    assert not any("ledger" in t["contract"] for t in v1["tasks"])
    assert ev.benchmark_hash(MANIFEST) != ev.benchmark_hash(ROOT / "evals" / "v1" / "manifest.json")


@pytest.mark.skipif(sys.platform == "win32", reason="the path jail needs openat; the VM runs these")
def test_c_offers_every_tool_but_search_and_refuses_a_search_call(tmp_path):
    from codetask.run import run_code_task
    from models.fake import StrictScriptedChatModel, reply
    from runner import load_config

    def call(name, args, id):
        return reply(tool_calls=[{"name": name, "args": args, "id": id}], input_tokens=500, output_tokens=60)

    def validate(spec, workspace, sandbox_cfg, log=None):
        return {"id": f"validation:{spec['id']}", "layer": "C", "status": "fail", "reason": "not fixed",
                "evidence": {"must_pass": {}, "tests_run": 8, "failures": 1, "output_tail": ""}}

    cfg = load_config()
    cfg["roles"]["coder"]["model"] = "fake:scripted"
    path = tmp_path / "c.json"
    path.write_text(json.dumps(contracts()["c"]), encoding="utf-8")
    nothing = call("Finish", {"claims": [], "summary": "not fixed"}, "f1")
    model = StrictScriptedChatModel(script=[call("SearchFiles", {"text": "late fee"}, "s1"),
                                            call("ReadFile", {"path": "src/core/ledger.py"}, "r1"), nothing, nothing])
    r = run_code_task(contract_path=path, run_id="c", runs_dir=tmp_path / "runs", cfg=cfg, models={"coder": model},
                      validate=validate, preflight=lambda: (True, "ok"))
    assert r["tools"] == cfg["tools"]["coder"] == ["list_files", "read_file", "write_file", "run_validation"]
    assert sorted(t.__name__ for t in model.bound_tools) == ["Finish", "ListFiles", "ReadFile", "RunValidation",
                                                             "WriteFile"]
    answers = {m.tool_call_id: m.content for c in model.calls for m in c["messages"] if hasattr(m, "tool_call_id")}
    assert answers["s1"].startswith("Denied") and "def prepare_lines" in answers["r1"]
    evs = [json.loads(line) for line in (tmp_path / "runs" / "c" / "events.jsonl").read_text().splitlines()]
    assert [e["tool"] for e in evs if e["event"] == "tool_denied"] == ["search_files"]
    assert not any(e["event"] == "tool_call" and e.get("tool") == "search_files" for e in evs)
    (eff,) = [e for e in evs if e["event"] == "tools_effective"]
    assert eff["tools"] == r["tools"] and eff["from_contract"] == []
