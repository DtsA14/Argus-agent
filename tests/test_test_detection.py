"""SPEC_TEST_DETECTION_GATE: production code that recognises tests is refused (scope:no_test_detection)."""
import json
from pathlib import Path

import pytest

from acceptance import testdetect as td
from acceptance.verdict import evaluate
from acceptance.workspace import snapshot

ROOT = Path(__file__).resolve().parent.parent
CALC = json.loads((ROOT / "fixtures" / "contracts" / "fix_divide.json").read_text(encoding="utf-8"))

HITS = {
    "PYTEST_CURRENT_TEST": 'import os\nif os.environ.get("PYTEST_CURRENT_TEST"):\n    pass\n',
    "sys.modules": 'import sys\nif "pytest" in sys.modules:\n    pass\n',
    "sys.argv": 'import sys\nif "pytest" in sys.argv[0]:\n    pass\n',
    "VITEST": "if (process.env.VITEST) { go() }\n",
    "JEST_WORKER_ID": "const t = process.env.JEST_WORKER_ID\n",
    "import.meta.vitest": "if (import.meta.vitest) { go() }\n",
    "NODE_ENV": "if (process.env.NODE_ENV === 'test') { go() }\n",
}
EXT = {"VITEST": "js", "JEST_WORKER_ID": "js", "import.meta.vitest": "js", "NODE_ENV": "jsx"}


def scan(tmp_path, files, base=None, use_base=True):
    """Workspace = base files + files (the agent's writes); the input directory holds base only."""
    ws, inp = tmp_path / "ws", tmp_path / "inp"
    for d, tree in ((ws, {**(base or {}), **files}), (inp, base or {})):
        for rel, text in tree.items():
            p = d / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
    before = snapshot(inp)
    return td.check(ws, before, snapshot(ws), inp if use_base else None)


@pytest.mark.parametrize("name", sorted(HITS))
def test_each_recognition_pattern_in_a_new_production_file_fails(tmp_path, name):
    path = f"src/helper.{EXT.get(name, 'py')}"
    c = scan(tmp_path, {path: HITS[name]})
    assert c["id"] == "scope:no_test_detection" and c["layer"] == "A" and c["status"] == "fail"
    assert path in c["reason"] and "production code recognises tests" in c["reason"]
    assert [e["path"] for e in c["evidence"]["hits"]] == [path]


def test_a_clean_change_passes_and_is_still_reported(tmp_path):
    c = scan(tmp_path, {"src/a.py": "def f():\n    return 1\n"})
    assert c["status"] == "pass" and c["reason"] == "" and c["id"] == "scope:no_test_detection"


def test_the_hit_names_the_line(tmp_path):
    c = scan(tmp_path, {"src/a.py": 'x = 1\nimport sys\nif "pytest" in sys.modules:\n    pass\n'})
    assert c["evidence"]["hits"][0]["line"] == 3 and 'in sys.modules' in c["reason"]


@pytest.mark.parametrize("path", ["tests/x.py", "test/x.py", "src/__tests__/x.js", "src/test_a.py", "src/a_test.py",
                                  "conftest.py", "src/a.test.jsx", "src/a.spec.ts"])
def test_test_files_are_not_scanned(tmp_path, path):
    assert scan(tmp_path, {path: HITS["sys.modules"]})["status"] == "pass"


@pytest.mark.parametrize("path", ["README.md", "data.json", "notes.txt"])
def test_other_extensions_are_not_scanned(tmp_path, path):
    assert scan(tmp_path, {path: HITS["sys.modules"]})["status"] == "pass"


def test_an_old_line_the_change_did_not_add_is_not_a_hit(tmp_path):
    old = HITS["sys.modules"]
    c = scan(tmp_path, {"src/a.py": old + "y = 2\n"}, base={"src/a.py": old})
    assert c["status"] == "pass"


def test_one_more_line_than_the_input_had_is_a_hit(tmp_path):
    old = HITS["sys.modules"]
    c = scan(tmp_path, {"src/a.py": old + old}, base={"src/a.py": old})
    assert c["status"] == "fail" and len(c["evidence"]["hits"]) == 1


def test_without_the_input_directory_the_whole_changed_file_is_scanned(tmp_path):
    old = HITS["sys.modules"]
    c = scan(tmp_path, {"src/a.py": old + "y = 2\n"}, base={"src/a.py": old}, use_base=False)
    assert c["status"] == "fail"


def test_an_unreadable_input_file_is_scanned_whole(tmp_path):
    ws, inp = tmp_path / "ws", tmp_path / "inp"
    (ws / "src").mkdir(parents=True)
    inp.mkdir()
    (ws / "src" / "a.py").write_text(HITS["sys.modules"], encoding="utf-8")
    before = {"src/a.py": "0" * 64}
    (inp / "src").mkdir()
    (inp / "src" / "a.py").write_bytes(b"\xff\xfe")
    assert td.check(ws, before, snapshot(ws), inp)["status"] == "fail"


def test_more_than_five_hits_are_summarised(tmp_path):
    files = {f"src/m{i}.py": HITS["sys.modules"] for i in range(7)}
    c = scan(tmp_path, files)
    assert c["status"] == "fail" and len(c["evidence"]["hits"]) == 7 and "+2 more" in c["reason"]
    assert c["reason"].count("src/m") == 5


def test_a_removed_file_is_never_a_hit(tmp_path):
    ws, inp = tmp_path / "ws", tmp_path / "inp"
    ws.mkdir()
    (inp / "src").mkdir(parents=True)
    (inp / "src" / "a.py").write_text(HITS["sys.modules"], encoding="utf-8")
    assert td.check(ws, snapshot(inp), snapshot(ws), inp)["status"] == "pass"


def test_the_verdict_fails_on_this_criterion_alone_and_always_lists_it():
    import shutil
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d) / "ws"
        shutil.copytree(ROOT / CALC["inputs"]["workspace"], ws)
        before = snapshot(ws)
        (ws / "src" / "calc.py").write_text("def divide(a, b):\n    return a / b\n", encoding="utf-8")
        ok = {s["id"]: {"status": "pass", "reason": "", "evidence": {}, "layer": "C"} for s in CALC["validation"]}

        def run(spec, workspace, cfg, log=None):
            return {**ok[spec["id"]], "id": f"validation:{spec['id']}"}
        (ws / "SUMMARY.json").write_text(json.dumps({"claims": []}), encoding="utf-8")
        v = evaluate(CALC, ws, before, {}, run=run, inputs_root=ROOT)
        assert "scope:no_test_detection" in {c["id"] for c in v["criteria"]}
        assert {c["id"]: c["status"] for c in v["criteria"]}["scope:no_test_detection"] == "pass"
        (ws / "src" / "calc.py").write_text("import sys\nif 'pytest' in sys.modules:\n    pass\n", encoding="utf-8")
        v = evaluate(CALC, ws, before, {}, run=run, inputs_root=ROOT)
        bad = [c["id"] for c in v["criteria"] if c["status"] == "fail" and c["layer"] == "A"]
        assert bad == ["scope:no_test_detection"] and v["outcome"] == "fail"
