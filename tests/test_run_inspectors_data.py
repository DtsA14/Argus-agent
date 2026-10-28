"""Pilot 3a. (1) The data of tests/test_run_inspectors.py: the output of audit_run.py and failure_trace.py, captured from the scripts as they
were before the change, for each synthetic run (GOLDEN), and the audit of a run blocked before any model call (BLOCKED_AUDIT).
(2) The contract of evals/runlog.py, the shared reader of a run directory, at the end of this file."""
import json
import sqlite3

GOLDEN = {'f1': {'audit': "effective tools ['list_files', 'read_file', 'write_file', 'run_validation']\n"
                 'effective system prompt sha256 fbc2af7c09fe4eed64f3a907146d795d75a9b923cdcbfe09428831e05dd5e57b\n'
                 'llm_call_started 4, llm_call 4 (ok 4, refused 0)\n'
                 '  it 0 step  0 ok       hash ok in 500 out 60 usd 0.0008 \n'
                 '      -> ReadFile {"path": "src/calc.py"}\n'
                 '  it 0 step  1 ok       hash ok in 500 out 60 usd 0.0008 \n'
                 '      -> WriteFile {"content": "\\"\\"\\"Small arithmetic helpers.\\"\\"\\"\\n\\n\\ndef add(a, '
                 'b):\\n    return a + b\\n\\n\\ndef subtract(a, b):\\n    return a - b\\n\\n\\ndef multiply(a, '
                 'b):\\n  \n'
                 '  it 0 step  2 ok       hash ok in 500 out 60 usd 0.0008 \n'
                 '      -> RunValidation {"id": "target"}\n'
                 '  it 0 step  3 ok       hash ok in 500 out 60 usd 0.0008 \n'
                 '      -> Finish {"claims": [{"claim": "tests_pass", "evidence": "validation:unit"}, {"claim": '
                 '"issue_fixed", "evidence": "validation:target"}, {"claim": "file_changed", "path":\n'
                 'prompt_hash checked 4, mismatches 0\n'
                 "  {'event': 'status', 'old': None, 'new': 'RUNNING', 'reason': None, 'blocked_reason': None}\n"
                 "  {'event': 'attempt_end', 'reason': 'finished', 'steps': 3, 'node': 'agent', 'task': 'fix_divide', "
                 "'iteration': 0}\n"
                 "  {'event': 'status', 'old': 'RUNNING', 'new': 'DONE', 'reason': 'all criteria passed', "
                 "'blocked_reason': None}\n"
                 "result {'status': 'DONE', 'stop_reason': 'all criteria passed', 'blocked_reason': None, 'attempts': "
                 "1, 'usd_billed': 0.0032, 'llm_calls': 4, 'llm_calls_unknown': 0, 'tools': ['list_files', "
                 "'read_file', 'write_file', 'run_validation']}\n",
        'trace': '##### f1\n'
                 '  it0 s0 ok      in   500 | ReadFile(src/calc.py)\n'
                 '        text: ok\n'
                 '  it0 s1 ok      in   500 | WriteFile(src/calc.py)\n'
                 '        text: ok\n'
                 '  it0 s2 ok      in   500 | RunValidation(target)\n'
                 '        text: ok\n'
                 '  it0 s3 ok      in   500 | Finish()\n'
                 '        text: ok\n'},
 'f2': {'audit': "effective tools ['list_files', 'read_file', 'write_file', 'run_validation']\n"
                 'effective system prompt sha256 fbc2af7c09fe4eed64f3a907146d795d75a9b923cdcbfe09428831e05dd5e57b\n'
                 'llm_call_started 3, llm_call 3 (ok 3, refused 0)\n'
                 '  it 0 step  0 ok       hash ok in 500 out 60 usd 0.0008 \n'
                 '      -> Finish {"claims": [{"claim": "tests_pass", "evidence": "validation:unit"}, {"claim": '
                 '"issue_fixed", "evidence": "validation:target"}, {"claim": "file_changed", "path":\n'
                 '  it 1 step  0 ok       hash ok in 500 out 60 usd 0.0008 \n'
                 '      -> WriteFile {"content": "\\"\\"\\"Small arithmetic helpers.\\"\\"\\"\\n\\n\\ndef add(a, '
                 'b):\\n    return a + b\\n\\n\\ndef subtract(a, b):\\n    return a - b\\n\\n\\ndef multiply(a, '
                 'b):\\n  \n'
                 '  it 1 step  1 ok       hash ok in 500 out 60 usd 0.0008 \n'
                 '      -> Finish {"claims": [{"claim": "tests_pass", "evidence": "validation:unit"}, {"claim": '
                 '"issue_fixed", "evidence": "validation:target"}, {"claim": "file_changed", "path":\n'
                 'prompt_hash checked 3, mismatches 0\n'
                 "  {'event': 'status', 'old': None, 'new': 'RUNNING', 'reason': None, 'blocked_reason': None}\n"
                 "  {'event': 'attempt_end', 'reason': 'finished', 'steps': 0, 'node': 'agent', 'task': 'fix_divide', "
                 "'iteration': 0}\n"
                 "  {'event': 'status', 'old': 'RUNNING', 'new': 'RUNNING', 'reason': None, 'blocked_reason': None}\n"
                 "  {'event': 'attempt_end', 'reason': 'finished', 'steps': 1, 'node': 'agent', 'task': 'fix_divide', "
                 "'iteration': 1}\n"
                 "  {'event': 'status', 'old': 'RUNNING', 'new': 'DONE', 'reason': 'all criteria passed', "
                 "'blocked_reason': None}\n"
                 "result {'status': 'DONE', 'stop_reason': 'all criteria passed', 'blocked_reason': None, 'attempts': "
                 "2, 'usd_billed': 0.0024, 'llm_calls': 3, 'llm_calls_unknown': 0, 'tools': ['list_files', "
                 "'read_file', 'write_file', 'run_validation']}\n",
        'trace': '##### f2\n'
                 '  it0 s0 ok      in   500 | Finish()\n'
                 '        text: ok\n'
                 '  it1 s0 ok      in   500 | WriteFile(src/calc.py)\n'
                 '        text: ok\n'
                 '  it1 s1 ok      in   500 | Finish()\n'
                 '        text: ok\n'},
 'f3': {'audit': "effective tools ['list_files', 'read_file', 'write_file', 'run_validation']\n"
                 'effective system prompt sha256 fbc2af7c09fe4eed64f3a907146d795d75a9b923cdcbfe09428831e05dd5e57b\n'
                 'llm_call_started 2, llm_call 2 (ok 2, refused 0)\n'
                 '  it 0 step  0 ok       hash ok in 500 out 60 usd 0.0008 \n'
                 '      -> Finish {"claims": [{"claim": "tests_pass", "evidence": "validation:unit"}, {"claim": '
                 '"issue_fixed", "evidence": "validation:target"}, {"claim": "file_changed", "path":\n'
                 '  it 1 step  0 ok       hash ok in 500 out 60 usd 0.0008 \n'
                 '      -> Finish {"claims": [{"claim": "tests_pass", "evidence": "validation:unit"}, {"claim": '
                 '"issue_fixed", "evidence": "validation:target"}, {"claim": "file_changed", "path":\n'
                 'prompt_hash checked 2, mismatches 0\n'
                 "  {'event': 'status', 'old': None, 'new': 'RUNNING', 'reason': None, 'blocked_reason': None}\n"
                 "  {'event': 'attempt_end', 'reason': 'finished', 'steps': 0, 'node': 'agent', 'task': 'fix_divide', "
                 "'iteration': 0}\n"
                 "  {'event': 'status', 'old': 'RUNNING', 'new': 'RUNNING', 'reason': None, 'blocked_reason': None}\n"
                 "  {'event': 'attempt_end', 'reason': 'finished', 'steps': 0, 'node': 'agent', 'task': 'fix_divide', "
                 "'iteration': 1}\n"
                 "  {'event': 'status', 'old': 'RUNNING', 'new': 'FAILED_ACCEPTANCE', 'reason': 'stagnant: the same "
                 "criteria failed 2 attempts in a row', 'blocked_reason': None}\n"
                 "result {'status': 'FAILED_ACCEPTANCE', 'stop_reason': 'stagnant: the same criteria failed 2 attempts "
                 "in a row', 'blocked_reason': None, 'attempts': 2, 'usd_billed': 0.0016, 'llm_calls': 2, "
                 "'llm_calls_unknown': 0, 'tools': ['list_files', 'read_file', 'write_file', 'run_validation']}\n",
        'trace': '##### f3\n'
                 '  it0 s0 ok      in   500 | Finish()\n'
                 '        text: ok\n'
                 '  it1 s0 ok      in   500 | Finish()\n'
                 '        text: ok\n'},
 'f5': {'audit': "effective tools ['list_files', 'read_file', 'write_file', 'run_validation']\n"
                 'effective system prompt sha256 fbc2af7c09fe4eed64f3a907146d795d75a9b923cdcbfe09428831e05dd5e57b\n'
                 'llm_call_started 3, llm_call 2 (ok 2, refused 0)\n'
                 '  it 0 step  0 ok       hash ok in 500 out 60 usd 0.0008 \n'
                 '      -> WriteFile {"content": "\\"\\"\\"Small arithmetic helpers.\\"\\"\\"\\n\\n\\ndef add(a, '
                 'b):\\n    return a + b\\n\\n\\ndef subtract(a, b):\\n    return a - b\\n\\n\\ndef multiply(a, '
                 'b):\\n  \n'
                 '  it 0 step  1 ok       hash ok in 500 out 60 usd 0.0008 \n'
                 '      -> Finish {"claims": [{"claim": "tests_pass", "evidence": "validation:unit"}, {"claim": '
                 '"issue_fixed", "evidence": "validation:target"}, {"claim": "file_changed", "path":\n'
                 'prompt_hash checked 2, mismatches 0\n'
                 "  {'event': 'status', 'old': None, 'new': 'RUNNING', 'reason': None, 'blocked_reason': None}\n"
                 "  {'event': 'attempt_end', 'reason': 'finished', 'steps': 1, 'node': 'agent', 'task': 'fix_divide', "
                 "'iteration': 0}\n"
                 "  {'event': 'status', 'old': 'RUNNING', 'new': 'DONE', 'reason': 'all criteria passed', "
                 "'blocked_reason': None}\n"
                 "result {'status': 'DONE', 'stop_reason': 'all criteria passed', 'blocked_reason': None, 'attempts': "
                 "1, 'usd_billed': 0.023721, 'llm_calls': 3, 'llm_calls_unknown': 1, 'tools': ['list_files', "
                 "'read_file', 'write_file', 'run_validation']}\n",
        'trace': '##### f5\n'
                 '  it0 s0 ok      in   500 | WriteFile(src/calc.py)\n'
                 '        text: ok\n'
                 '  it0 s1 ok      in   500 | Finish()\n'
                 '        text: ok\n'},
 'f8': {'audit': "effective tools ['list_files', 'read_file', 'write_file', 'run_validation']\n"
                 'effective system prompt sha256 fbc2af7c09fe4eed64f3a907146d795d75a9b923cdcbfe09428831e05dd5e57b\n'
                 'llm_call_started 3, llm_call 3 (ok 3, refused 0)\n'
                 '  it 0 step  0 ok       hash ok in 500 out 60 usd 0.0008 \n'
                 '      -> ReadFile {"path": "src/ddddddddddddddddddddddddddddddddddddddddddddd0.py"}\n'
                 '      -> ReadFile {"path": "src/ddddddddddddddddddddddddddddddddddddddddddddd1.py"}\n'
                 '      -> ReadFile {"path": "src/ddddddddddddddddddddddddddddddddddddddddddddd2.py"}\n'
                 '  it 0 step  1 ok       hash ok in 500 out 60 usd 0.0008 \n'
                 '      -> WriteFile {"content": "\\"\\"\\"Small arithmetic helpers.\\"\\"\\"\\n\\n\\ndef add(a, '
                 'b):\\n    return a + b\\n\\n\\ndef subtract(a, b):\\n    return a - b\\n\\n\\ndef multiply(a, '
                 'b):\\n  \n'
                 '  it 0 step  2 ok       hash ok in 500 out 60 usd 0.0008 \n'
                 '      -> Finish {"claims": [{"claim": "tests_pass", "evidence": "validation:unit"}, {"claim": '
                 '"issue_fixed", "evidence": "validation:target"}, {"claim": "file_changed", "path":\n'
                 'prompt_hash checked 3, mismatches 0\n'
                 "  {'event': 'status', 'old': None, 'new': 'RUNNING', 'reason': None, 'blocked_reason': None}\n"
                 "  {'event': 'attempt_end', 'reason': 'finished', 'steps': 2, 'node': 'agent', 'task': 'fix_divide', "
                 "'iteration': 0}\n"
                 "  {'event': 'status', 'old': 'RUNNING', 'new': 'DONE', 'reason': 'all criteria passed', "
                 "'blocked_reason': None}\n"
                 "result {'status': 'DONE', 'stop_reason': 'all criteria passed', 'blocked_reason': None, 'attempts': "
                 "1, 'usd_billed': 0.0024, 'llm_calls': 3, 'llm_calls_unknown': 0, 'tools': ['list_files', "
                 "'read_file', 'write_file', 'run_validation']}\n",
        'trace': '##### f8\n'
                 '  it0 s0 ok      in   500 | ReadFile(src/ddddddddddddddddddddddddddddddddddddddddddddd0.py) '
                 'ReadFile(src/ddddddddddddddddddddddddddddddddddddddddddddd1.py) ReadFile(src/ddddddddd\n'
                 '        text: word word word word word word word word word word word word word word word word word '
                 'word word word word word word word word word word word word word word word word word word word word '
                 'word word word word word word word word word word word word word word word word word word word word '
                 'word word word word word word word word word word word word word word word word word word word word '
                 'word word word \n'
                 '  it0 s1 ok      in   500 | WriteFile(src/calc.py)\n'
                 '        text: ok\n'
                 '  it0 s2 ok      in   500 | Finish()\n'
                 '        text: ok\n'},
 'wrap': {'trace': '##### wrap\n'
                   '  it0 s0 ok      in   500 | ReadFile(src/calc.py)\n'
                   '        text: ok\n'
                   '  it0 s1 ok      in   500 | WriteFile(src/calc.py)\n'
                   '        text: ok\n'
                   '  it0 s2 ok      in   500 | RunValidation(target)\n'
                   '        text: ok\n'
                   '  it0 s3 ok      in   500 | Finish()\n'
                   '        text: ok\n'}}
BLOCKED_AUDIT = "effective tools None\nllm_call_started 0, llm_call 0 (ok 0, refused 0)\nprompt_hash checked 0, mismatches 0\n  {'event': 'status', 'old': None, 'new': 'BLOCKED', 'reason': 'sandbox unavailable: no sandbox', 'blocked_reason': 'sandbox_unavailable'}\nresult {'status': 'BLOCKED', 'stop_reason': 'sandbox unavailable: no sandbox', 'blocked_reason': 'sandbox_unavailable', 'attempts': 0, 'usd_billed': 0.0, 'llm_calls': 0, 'llm_calls_unknown': 0, 'tools': None}\n"


def reader():
    import importlib
    return importlib.import_module("evals.runlog")


def test_events_are_read_with_the_number_of_lines_that_did_not_decode(tmp_path):
    (tmp_path / "events.jsonl").write_text('{"event": "a"}\n\n{"event": "b", "n": 2}\nnot json\n{"event": "c', encoding="utf-8")
    events, skipped = reader().read_events(tmp_path)
    assert events == [{"event": "a"}, {"event": "b", "n": 2}] and skipped == 2     # a blank line is not a skipped one
    (tmp_path / "events.jsonl").write_text('{"event": "a"}\n', encoding="utf-8")
    assert reader().read_events(tmp_path) == ([{"event": "a"}], 0)


def test_result_memo_and_the_skipped_line_are_read_as_the_inspectors_need_them(tmp_path):
    rl = reader()
    assert rl.read_result(tmp_path) is None                              # a run that never got a result.json
    (tmp_path / "result.json").write_text(json.dumps({"status": "DONE", "attempts": 1}), encoding="utf-8")
    assert rl.read_result(tmp_path) == {"status": "DONE", "attempts": 1}
    db = sqlite3.connect(tmp_path / "memo.sqlite")
    db.execute("create table memo (key text primary key, value text)")
    db.execute("insert into memo values (?, ?)", (json.dumps(["llm", "c", 0, 0, 1]), json.dumps({"content": "x"})))
    db.commit()
    db.close()
    assert rl.read_memo(tmp_path) == {json.dumps(["llm", "c", 0, 0, 1]): {"content": "x"}}
    assert rl.skipped_line(0) is None and rl.skipped_line(3) == "events skipped: 3"
