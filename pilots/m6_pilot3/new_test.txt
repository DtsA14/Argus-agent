"""M6 pilot 3: one reader of a code-task run directory, two inspectors that must keep printing what they always printed, and a
report over runs.

Synthetic runs (a scripted model, an injected validation: no Docker, no money) are built once and then looked at by the
scripts as subprocesses:
  scripts/audit_run.py and scripts/failure_trace.py: for runs that finished normally (f1, f2, f3, f5, the last after a crash and
  a resume) their output is the one the scripts printed before this change, byte for byte (GOLDEN). Only three things change,
  and each was a crash: a line of events.jsonl that does not decode is skipped wherever it is (and one line "events skipped: N"
  ends the output, only when N is not 0), audit_run.py audits a run that made no model call, and failure_trace.py reports a
  directory that has no result.json and goes on.
  scripts/pilot_report.py: a JSON report over runs, defined in the issue of the task. The tests compare the parsed report (keys
  in this order, numbers within 1e-6), never the text."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from codetask.run import run_code_task
from models.fake import CallableChatModel, StrictScriptedChatModel, reply
from runner import load_config

ROOT = Path(__file__).resolve().parent.parent
CUT = '{"ts": 2.5, "event": "llm_ca'                           # what a process killed mid-write leaves behind

GOLDEN = {'f1': {'audit': "effective tools ['list_files', 'read_file', 'write_file', 'run_validation']\n"
                 'effective system prompt sha256 ee7af58da465bd579f4f82ba9547cfefbc441577f89b04a101fdd123ee0d3bc0\n'
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
                 'effective system prompt sha256 ee7af58da465bd579f4f82ba9547cfefbc441577f89b04a101fdd123ee0d3bc0\n'
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
                 'effective system prompt sha256 ee7af58da465bd579f4f82ba9547cfefbc441577f89b04a101fdd123ee0d3bc0\n'
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
                 'effective system prompt sha256 ee7af58da465bd579f4f82ba9547cfefbc441577f89b04a101fdd123ee0d3bc0\n'
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
                 "1, 'usd_billed': 0.023389, 'llm_calls': 3, 'llm_calls_unknown': 1, 'tools': ['list_files', "
                 "'read_file', 'write_file', 'run_validation']}\n",
        'trace': '##### f5\n'
                 '  it0 s0 ok      in   500 | WriteFile(src/calc.py)\n'
                 '        text: ok\n'
                 '  it0 s1 ok      in   500 | Finish()\n'
                 '        text: ok\n'}}
BLOCKED_AUDIT = "effective tools None\nllm_call_started 0, llm_call 0 (ok 0, refused 0)\nprompt_hash checked 0, mismatches 0\n  {'event': 'status', 'old': None, 'new': 'BLOCKED', 'reason': 'sandbox unavailable: no sandbox', 'blocked_reason': 'sandbox_unavailable'}\nresult {'status': 'BLOCKED', 'stop_reason': 'sandbox unavailable: no sandbox', 'blocked_reason': 'sandbox_unavailable', 'attempts': 0, 'usd_billed': 0.0, 'llm_calls': 0, 'llm_calls_unknown': 0, 'tools': None}\n"
REPORTS = {'all': '{\n'
        '  "runs": [\n'
        '    {\n'
        '      "run_id": "f1",\n'
        '      "status": "DONE",\n'
        '      "done": true,\n'
        '      "attempts": 1,\n'
        '      "llm_calls": 4,\n'
        '      "usd_billed": 0.0032,\n'
        '      "cost_known": true,\n'
        '      "events_skipped": 0,\n'
        '      "supervision_minutes": 5\n'
        '    },\n'
        '    {\n'
        '      "run_id": "f2",\n'
        '      "status": "DONE",\n'
        '      "done": true,\n'
        '      "attempts": 2,\n'
        '      "llm_calls": 3,\n'
        '      "usd_billed": 0.0024,\n'
        '      "cost_known": true,\n'
        '      "events_skipped": 0,\n'
        '      "supervision_minutes": 10.5\n'
        '    },\n'
        '    {\n'
        '      "run_id": "f3",\n'
        '      "status": "FAILED_ACCEPTANCE",\n'
        '      "done": false,\n'
        '      "attempts": 2,\n'
        '      "llm_calls": 2,\n'
        '      "usd_billed": 0.0016,\n'
        '      "cost_known": true,\n'
        '      "events_skipped": 0,\n'
        '      "supervision_minutes": 0\n'
        '    },\n'
        '    {\n'
        '      "run_id": "f4",\n'
        '      "status": "BLOCKED",\n'
        '      "done": false,\n'
        '      "attempts": 0,\n'
        '      "llm_calls": 0,\n'
        '      "usd_billed": 0.0,\n'
        '      "cost_known": true,\n'
        '      "events_skipped": 0,\n'
        '      "supervision_minutes": null\n'
        '    },\n'
        '    {\n'
        '      "run_id": "f5",\n'
        '      "status": "DONE",\n'
        '      "done": true,\n'
        '      "attempts": 1,\n'
        '      "llm_calls": 3,\n'
        '      "usd_billed": 0.023389,\n'
        '      "cost_known": true,\n'
        '      "events_skipped": 0,\n'
        '      "supervision_minutes": null\n'
        '    },\n'
        '    {\n'
        '      "run_id": "f5c",\n'
        '      "status": "DONE",\n'
        '      "done": true,\n'
        '      "attempts": 1,\n'
        '      "llm_calls": 3,\n'
        '      "usd_billed": 0.023389,\n'
        '      "cost_known": true,\n'
        '      "events_skipped": 1,\n'
        '      "supervision_minutes": null\n'
        '    },\n'
        '    {\n'
        '      "run_id": "f6a",\n'
        '      "status": "DONE",\n'
        '      "done": true,\n'
        '      "attempts": 1,\n'
        '      "llm_calls": 4,\n'
        '      "usd_billed": 0.05,\n'
        '      "cost_known": false,\n'
        '      "events_skipped": 0,\n'
        '      "supervision_minutes": null\n'
        '    },\n'
        '    {\n'
        '      "run_id": "f6b",\n'
        '      "status": "DONE",\n'
        '      "done": true,\n'
        '      "attempts": 1,\n'
        '      "llm_calls": 4,\n'
        '      "usd_billed": null,\n'
        '      "cost_known": false,\n'
        '      "events_skipped": 0,\n'
        '      "supervision_minutes": null\n'
        '    },\n'
        '    {\n'
        '      "run_id": "f6c",\n'
        '      "status": "DONE",\n'
        '      "done": true,\n'
        '      "attempts": 1,\n'
        '      "llm_calls": 4,\n'
        '      "usd_billed": 0.0032,\n'
        '      "cost_known": false,\n'
        '      "events_skipped": 0,\n'
        '      "supervision_minutes": null\n'
        '    },\n'
        '    {\n'
        '      "run_id": "f7",\n'
        '      "status": "NO_RESULT",\n'
        '      "done": false,\n'
        '      "attempts": null,\n'
        '      "llm_calls": null,\n'
        '      "usd_billed": null,\n'
        '      "cost_known": false,\n'
        '      "events_skipped": 0,\n'
        '      "supervision_minutes": null\n'
        '    }\n'
        '  ],\n'
        '  "summary": {\n'
        '    "runs": 10,\n'
        '    "done": 7,\n'
        '    "no_result": 1,\n'
        '    "success_rate": 0.777778,\n'
        '    "usd_known_total": 0.053978,\n'
        '    "usd_unknown_runs": 4,\n'
        '    "cost_per_success": 0.013494,\n'
        '    "cost_complete": false,\n'
        '    "attempts": {\n'
        '      "mean": 1.142857,\n'
        '      "median": 1,\n'
        '      "distribution": {\n'
        '        "0": 1,\n'
        '        "1": 6,\n'
        '        "2": 2\n'
        '      }\n'
        '    },\n'
        '    "supervision_minutes": {\n'
        '      "runs_with_data": 3,\n'
        '      "total": 15.5,\n'
        '      "mean": 5.166667\n'
        '    },\n'
        '    "events_skipped": 1\n'
        '  }\n'
        '}\n',
 'all_no_supervision': '{\n'
                       '  "runs": [\n'
                       '    {\n'
                       '      "run_id": "f1",\n'
                       '      "status": "DONE",\n'
                       '      "done": true,\n'
                       '      "attempts": 1,\n'
                       '      "llm_calls": 4,\n'
                       '      "usd_billed": 0.0032,\n'
                       '      "cost_known": true,\n'
                       '      "events_skipped": 0,\n'
                       '      "supervision_minutes": null\n'
                       '    },\n'
                       '    {\n'
                       '      "run_id": "f2",\n'
                       '      "status": "DONE",\n'
                       '      "done": true,\n'
                       '      "attempts": 2,\n'
                       '      "llm_calls": 3,\n'
                       '      "usd_billed": 0.0024,\n'
                       '      "cost_known": true,\n'
                       '      "events_skipped": 0,\n'
                       '      "supervision_minutes": null\n'
                       '    },\n'
                       '    {\n'
                       '      "run_id": "f3",\n'
                       '      "status": "FAILED_ACCEPTANCE",\n'
                       '      "done": false,\n'
                       '      "attempts": 2,\n'
                       '      "llm_calls": 2,\n'
                       '      "usd_billed": 0.0016,\n'
                       '      "cost_known": true,\n'
                       '      "events_skipped": 0,\n'
                       '      "supervision_minutes": null\n'
                       '    },\n'
                       '    {\n'
                       '      "run_id": "f4",\n'
                       '      "status": "BLOCKED",\n'
                       '      "done": false,\n'
                       '      "attempts": 0,\n'
                       '      "llm_calls": 0,\n'
                       '      "usd_billed": 0.0,\n'
                       '      "cost_known": true,\n'
                       '      "events_skipped": 0,\n'
                       '      "supervision_minutes": null\n'
                       '    },\n'
                       '    {\n'
                       '      "run_id": "f5",\n'
                       '      "status": "DONE",\n'
                       '      "done": true,\n'
                       '      "attempts": 1,\n'
                       '      "llm_calls": 3,\n'
                       '      "usd_billed": 0.023389,\n'
                       '      "cost_known": true,\n'
                       '      "events_skipped": 0,\n'
                       '      "supervision_minutes": null\n'
                       '    },\n'
                       '    {\n'
                       '      "run_id": "f5c",\n'
                       '      "status": "DONE",\n'
                       '      "done": true,\n'
                       '      "attempts": 1,\n'
                       '      "llm_calls": 3,\n'
                       '      "usd_billed": 0.023389,\n'
                       '      "cost_known": true,\n'
                       '      "events_skipped": 1,\n'
                       '      "supervision_minutes": null\n'
                       '    },\n'
                       '    {\n'
                       '      "run_id": "f6a",\n'
                       '      "status": "DONE",\n'
                       '      "done": true,\n'
                       '      "attempts": 1,\n'
                       '      "llm_calls": 4,\n'
                       '      "usd_billed": 0.05,\n'
                       '      "cost_known": false,\n'
                       '      "events_skipped": 0,\n'
                       '      "supervision_minutes": null\n'
                       '    },\n'
                       '    {\n'
                       '      "run_id": "f6b",\n'
                       '      "status": "DONE",\n'
                       '      "done": true,\n'
                       '      "attempts": 1,\n'
                       '      "llm_calls": 4,\n'
                       '      "usd_billed": null,\n'
                       '      "cost_known": false,\n'
                       '      "events_skipped": 0,\n'
                       '      "supervision_minutes": null\n'
                       '    },\n'
                       '    {\n'
                       '      "run_id": "f6c",\n'
                       '      "status": "DONE",\n'
                       '      "done": true,\n'
                       '      "attempts": 1,\n'
                       '      "llm_calls": 4,\n'
                       '      "usd_billed": 0.0032,\n'
                       '      "cost_known": false,\n'
                       '      "events_skipped": 0,\n'
                       '      "supervision_minutes": null\n'
                       '    },\n'
                       '    {\n'
                       '      "run_id": "f7",\n'
                       '      "status": "NO_RESULT",\n'
                       '      "done": false,\n'
                       '      "attempts": null,\n'
                       '      "llm_calls": null,\n'
                       '      "usd_billed": null,\n'
                       '      "cost_known": false,\n'
                       '      "events_skipped": 0,\n'
                       '      "supervision_minutes": null\n'
                       '    }\n'
                       '  ],\n'
                       '  "summary": {\n'
                       '    "runs": 10,\n'
                       '    "done": 7,\n'
                       '    "no_result": 1,\n'
                       '    "success_rate": 0.777778,\n'
                       '    "usd_known_total": 0.053978,\n'
                       '    "usd_unknown_runs": 4,\n'
                       '    "cost_per_success": 0.013494,\n'
                       '    "cost_complete": false,\n'
                       '    "attempts": {\n'
                       '      "mean": 1.142857,\n'
                       '      "median": 1,\n'
                       '      "distribution": {\n'
                       '        "0": 1,\n'
                       '        "1": 6,\n'
                       '        "2": 2\n'
                       '      }\n'
                       '    },\n'
                       '    "supervision_minutes": {\n'
                       '      "runs_with_data": 0,\n'
                       '      "total": null,\n'
                       '      "mean": null\n'
                       '    },\n'
                       '    "events_skipped": 1\n'
                       '  }\n'
                       '}\n',
 'no_done': '{\n'
            '  "runs": [\n'
            '    {\n'
            '      "run_id": "f3",\n'
            '      "status": "FAILED_ACCEPTANCE",\n'
            '      "done": false,\n'
            '      "attempts": 2,\n'
            '      "llm_calls": 2,\n'
            '      "usd_billed": 0.0016,\n'
            '      "cost_known": true,\n'
            '      "events_skipped": 0,\n'
            '      "supervision_minutes": null\n'
            '    },\n'
            '    {\n'
            '      "run_id": "f4",\n'
            '      "status": "BLOCKED",\n'
            '      "done": false,\n'
            '      "attempts": 0,\n'
            '      "llm_calls": 0,\n'
            '      "usd_billed": 0.0,\n'
            '      "cost_known": true,\n'
            '      "events_skipped": 0,\n'
            '      "supervision_minutes": null\n'
            '    }\n'
            '  ],\n'
            '  "summary": {\n'
            '    "runs": 2,\n'
            '    "done": 0,\n'
            '    "no_result": 0,\n'
            '    "success_rate": 0.0,\n'
            '    "usd_known_total": 0.0016,\n'
            '    "usd_unknown_runs": 0,\n'
            '    "cost_per_success": null,\n'
            '    "cost_complete": true,\n'
            '    "attempts": {\n'
            '      "mean": null,\n'
            '      "median": null,\n'
            '      "distribution": {\n'
            '        "0": 1,\n'
            '        "2": 1\n'
            '      }\n'
            '    },\n'
            '    "supervision_minutes": {\n'
            '      "runs_with_data": 0,\n'
            '      "total": null,\n'
            '      "mean": null\n'
            '    },\n'
            '    "events_skipped": 0\n'
            '  }\n'
            '}\n',
 'all_unknown': '{\n'
                '  "runs": [\n'
                '    {\n'
                '      "run_id": "f6a",\n'
                '      "status": "DONE",\n'
                '      "done": true,\n'
                '      "attempts": 1,\n'
                '      "llm_calls": 4,\n'
                '      "usd_billed": 0.05,\n'
                '      "cost_known": false,\n'
                '      "events_skipped": 0,\n'
                '      "supervision_minutes": null\n'
                '    },\n'
                '    {\n'
                '      "run_id": "f6b",\n'
                '      "status": "DONE",\n'
                '      "done": true,\n'
                '      "attempts": 1,\n'
                '      "llm_calls": 4,\n'
                '      "usd_billed": null,\n'
                '      "cost_known": false,\n'
                '      "events_skipped": 0,\n'
                '      "supervision_minutes": null\n'
                '    },\n'
                '    {\n'
                '      "run_id": "f6c",\n'
                '      "status": "DONE",\n'
                '      "done": true,\n'
                '      "attempts": 1,\n'
                '      "llm_calls": 4,\n'
                '      "usd_billed": 0.0032,\n'
                '      "cost_known": false,\n'
                '      "events_skipped": 0,\n'
                '      "supervision_minutes": null\n'
                '    },\n'
                '    {\n'
                '      "run_id": "f7",\n'
                '      "status": "NO_RESULT",\n'
                '      "done": false,\n'
                '      "attempts": null,\n'
                '      "llm_calls": null,\n'
                '      "usd_billed": null,\n'
                '      "cost_known": false,\n'
                '      "events_skipped": 0,\n'
                '      "supervision_minutes": null\n'
                '    }\n'
                '  ],\n'
                '  "summary": {\n'
                '    "runs": 4,\n'
                '    "done": 3,\n'
                '    "no_result": 1,\n'
                '    "success_rate": 1.0,\n'
                '    "usd_known_total": null,\n'
                '    "usd_unknown_runs": 4,\n'
                '    "cost_per_success": null,\n'
                '    "cost_complete": false,\n'
                '    "attempts": {\n'
                '      "mean": 1,\n'
                '      "median": 1,\n'
                '      "distribution": {\n'
                '        "1": 3\n'
                '      }\n'
                '    },\n'
                '    "supervision_minutes": {\n'
                '      "runs_with_data": 0,\n'
                '      "total": null,\n'
                '      "mean": null\n'
                '    },\n'
                '    "events_skipped": 0\n'
                '  }\n'
                '}\n',
 'only_done': '{\n'
              '  "runs": [\n'
              '    {\n'
              '      "run_id": "f1",\n'
              '      "status": "DONE",\n'
              '      "done": true,\n'
              '      "attempts": 1,\n'
              '      "llm_calls": 4,\n'
              '      "usd_billed": 0.0032,\n'
              '      "cost_known": true,\n'
              '      "events_skipped": 0,\n'
              '      "supervision_minutes": null\n'
              '    },\n'
              '    {\n'
              '      "run_id": "f5",\n'
              '      "status": "DONE",\n'
              '      "done": true,\n'
              '      "attempts": 1,\n'
              '      "llm_calls": 3,\n'
              '      "usd_billed": 0.023389,\n'
              '      "cost_known": true,\n'
              '      "events_skipped": 0,\n'
              '      "supervision_minutes": null\n'
              '    }\n'
              '  ],\n'
              '  "summary": {\n'
              '    "runs": 2,\n'
              '    "done": 2,\n'
              '    "no_result": 0,\n'
              '    "success_rate": 1.0,\n'
              '    "usd_known_total": 0.026589,\n'
              '    "usd_unknown_runs": 0,\n'
              '    "cost_per_success": 0.013295,\n'
              '    "cost_complete": true,\n'
              '    "attempts": {\n'
              '      "mean": 1,\n'
              '      "median": 1.0,\n'
              '      "distribution": {\n'
              '        "1": 2\n'
              '      }\n'
              '    },\n'
              '    "supervision_minutes": {\n'
              '      "runs_with_data": 0,\n'
              '      "total": null,\n'
              '      "mean": null\n'
              '    },\n'
              '    "events_skipped": 0\n'
              '  }\n'
              '}\n'}


def build(root, base):
    """Build the fixtures below `base` (a directory that does not exist yet). Returns {name: run directory}."""
    root, base = Path(root), Path(base)
    contract = json.loads((root / "fixtures" / "contracts" / "fix_divide.json").read_text(encoding="utf-8"))
    calc = (root / "fixtures" / "repos" / "calc" / "src" / "calc.py").read_text(encoding="utf-8")
    test = (root / "fixtures" / "repos" / "calc" / "tests" / "test_calc.py").read_text(encoding="utf-8")
    fixed = calc.replace("    if b == 0:\n        return 0\n", "")
    claims = [{"claim": "tests_pass", "evidence": "validation:unit"}, {"claim": "issue_fixed", "evidence": "validation:target"},
              {"claim": "file_changed", "path": "src/calc.py"}]

    def call(name, args, id):
        return reply(tool_calls=[{"name": name, "args": args, "id": id}], input_tokens=500, output_tokens=60)

    read = call("ReadFile", {"path": "src/calc.py"}, "r1")
    write = call("WriteFile", {"path": "src/calc.py", "content": fixed}, "w1")
    check = call("RunValidation", {"id": "target"}, "v1")
    finish = call("Finish", {"claims": claims, "summary": "divide raises on zero"}, "f1")
    lazy = call("Finish", {"claims": claims, "summary": "fixed"}, "f0")

    def validate(spec, workspace, sandbox_cfg, log=None):
        ws = Path(workspace)
        ok = (ws / "src" / "calc.py").read_text() == fixed and (ws / "tests" / "test_calc.py").read_text() == test
        must = {t: "ok" if ok else "FAIL" for t in spec.get("must_pass", [])}
        return {"id": f"validation:{spec['id']}", "layer": "C", "status": "pass" if ok else "fail",
                "reason": "" if ok else "exit code 1; unittest outcome FAILED",
                "evidence": {"must_pass": must, "tests_run": 7, "failures": 0 if ok else 1, "output_tail": ""}}

    class Crash(BaseException):
        pass

    base.mkdir(parents=True)
    path = base / "contract.json"
    path.write_text(json.dumps(contract), encoding="utf-8")

    def run(name, script, *, preflight=lambda: (True, "ok"), model=None, resume=False):
        cfg = load_config()
        cfg["roles"]["coder"]["model"] = "fake:scripted"
        return run_code_task(contract_path=path, run_id=name, runs_dir=base / "runs", cfg=cfg,
                             models={"coder": model or StrictScriptedChatModel(script=list(script))},
                             validate=validate, preflight=preflight, resume=resume)

    run("f1", [read, write, check, finish])                         # DONE at once
    run("f2", [lazy, write, finish])                                # DONE in the second attempt
    run("f3", [lazy, lazy])                                         # FAILED_ACCEPTANCE (stagnant)
    run("f4", [], preflight=lambda: (False, "no sandbox"))          # BLOCKED before any model call

    def die(messages):
        raise Crash()
    try:
        run("f5", [], model=CallableChatModel(respond=die))         # the process dies in the first model call
    except Crash:
        pass
    run("f5", [write, finish], resume=True)                         # and the run is resumed: DONE

    runs = base / "runs"
    out = {n: runs / n for n in ("f1", "f2", "f3", "f4", "f5")}

    def copy(src, name):
        shutil.copytree(runs / src, runs / name)
        return runs / name

    f5c = copy("f5", "f5c")                                         # f5 with a line cut by a crash in the middle of its log
    lines = (f5c / "events.jsonl").read_text(encoding="utf-8").splitlines()
    (f5c / "events.jsonl").write_text("\n".join(lines[:3] + [CUT] + lines[3:]) + "\n", encoding="utf-8")
    out["f5c"] = f5c
    for name, change in (("f6a", {"usd_billed": 0.05, "usd_complete": False}),      # a partial total
                         ("f6b", {"usd_billed": None}),                              # no usd_billed at all
                         ("f6c", {"usd_complete": None})):                           # no usd_complete
        d = copy("f1", name)
        result = json.loads((d / "result.json").read_text(encoding="utf-8"))
        for k, v in change.items():
            if v is None:
                result.pop(k, None)
            else:
                result[k] = v
        (d / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        out[name] = d
    f7 = copy("f1", "f7")                                           # a run that never got a result
    (f7 / "result.json").unlink()
    out["f7"] = f7
    return out


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    return build(ROOT, tmp_path_factory.mktemp("runs") / "b")


def script(name, *args):
    return subprocess.run([sys.executable, str(ROOT / "scripts" / name), *map(str, args)], cwd=ROOT,
                          env={**os.environ, "PYTHONPATH": str(ROOT)}, capture_output=True, text=True, timeout=300)


def report(*args):
    r = script("pilot_report.py", *args)
    assert r.returncode == 0, r.stderr[-500:]
    return r.stdout


def assert_report(text, expected):
    """The parsed report equals the expected one: the same keys in the same order, numbers within 1e-6."""
    def same(a, b, where):
        if isinstance(b, dict):
            assert isinstance(a, dict) and list(a) == list(b), (where, list(a) if isinstance(a, dict) else a, list(b))
            for k in b:
                same(a[k], b[k], f"{where}.{k}")
        elif isinstance(b, list):
            assert isinstance(a, list) and len(a) == len(b), (where, a, b)
            for i, (x, y) in enumerate(zip(a, b)):
                same(x, y, f"{where}[{i}]")
        elif isinstance(b, float) and a is not None:
            assert a == pytest.approx(b, abs=1e-6), (where, a, b)
        else:
            assert a == b and type(a) is not bool or isinstance(b, bool) and a is b, (where, a, b)
    same(json.loads(text), json.loads(expected), "report")


# ---- the two inspectors keep printing what they always printed ----------------------------------------------------

@pytest.mark.parametrize("name", ["f1", "f2", "f3", "f5"])
def test_audit_run_still_prints_what_it_always_printed(runs, name):
    r = script("audit_run.py", runs[name])
    assert r.returncode == 0, r.stderr[-500:]
    assert r.stdout == GOLDEN[name]["audit"]


@pytest.mark.parametrize("name", ["f1", "f2", "f3", "f5"])
def test_failure_trace_still_prints_what_it_always_printed(runs, name):
    r = script("failure_trace.py", runs[name])
    assert r.returncode == 0, r.stderr[-500:]
    assert r.stdout == GOLDEN[name]["trace"]


# ---- what changes: each of these was a crash ------------------------------------------------------------------------

def test_a_cut_line_in_the_middle_of_the_log_adds_one_line_and_changes_nothing_else(runs):
    audit, trace = script("audit_run.py", runs["f5c"]), script("failure_trace.py", runs["f5c"])
    assert (audit.returncode, trace.returncode) == (0, 0), (audit.stderr[-400:], trace.stderr[-400:])
    assert audit.stdout == GOLDEN["f5"]["audit"] + "events skipped: 1\n"
    assert trace.stdout == GOLDEN["f5"]["trace"].replace("##### f5\n", "##### f5c\n", 1) + "events skipped: 1\n"
    assert CUT in (runs["f5c"] / "events.jsonl").read_text(encoding="utf-8").splitlines()[:-1]        # in the middle


def test_a_run_blocked_before_any_model_call_is_audited(runs):
    audit, trace = script("audit_run.py", runs["f4"]), script("failure_trace.py", runs["f4"])
    assert audit.returncode == 0, audit.stderr[-500:]
    assert audit.stdout == BLOCKED_AUDIT
    assert (trace.returncode, trace.stdout) == (0, "##### f4\n")


def test_a_directory_without_a_result_is_reported_and_the_next_one_is_still_traced(runs):
    alone = script("failure_trace.py", runs["f7"])
    assert (alone.returncode, alone.stdout) == (0, "##### f7: no result.json\n"), alone.stderr[-400:]
    both = script("failure_trace.py", runs["f7"], runs["f1"])
    assert both.returncode == 0 and both.stdout == "##### f7: no result.json\n" + GOLDEN["f1"]["trace"]


# ---- the report -----------------------------------------------------------------------------------------------------

ORDER = ["f1", "f2", "f3", "f4", "f5", "f5c", "f6a", "f6b", "f6c", "f7"]


def test_the_report_over_every_fixture_with_supervision_is_exactly_this(runs, tmp_path):
    sup = tmp_path / "supervision.json"
    sup.write_text(json.dumps({"f1": 5, "f2": 10.5, "f3": 0, "nobody": 99}), encoding="utf-8")   # f3: 0 minutes is data
    assert_report(report(*[runs[n] for n in ORDER], "--supervision", sup), REPORTS["all"])


def test_without_a_supervision_file_the_minutes_are_null_never_zero(runs):
    text = report(*[runs[n] for n in ORDER])
    assert_report(text, REPORTS["all_no_supervision"])
    data = json.loads(text)
    assert all(r["supervision_minutes"] is None for r in data["runs"])
    assert data["summary"]["supervision_minutes"] == {"runs_with_data": 0, "total": None, "mean": None}


def test_with_no_done_run_the_cost_per_success_and_the_attempt_statistics_are_null(runs):
    assert_report(report(runs["f3"], runs["f4"]), REPORTS["no_done"])


def test_when_no_cost_is_known_nothing_is_counted_as_zero(runs):
    text = report(runs["f6a"], runs["f6b"], runs["f6c"], runs["f7"])
    assert_report(text, REPORTS["all_unknown"])
    s = json.loads(text)["summary"]
    assert (s["usd_known_total"], s["cost_per_success"], s["cost_complete"], s["usd_unknown_runs"]) == (None, None, False, 4)


def test_a_report_over_done_runs_only_is_complete(runs):
    assert_report(report(runs["f1"], runs["f5"]), REPORTS["only_done"])


def test_a_cut_line_is_counted_in_events_skipped(runs):
    data = json.loads(report(runs["f5"], runs["f5c"]))
    assert [r["events_skipped"] for r in data["runs"]] == [0, 1] and data["summary"]["events_skipped"] == 1


def test_a_run_given_with_a_trailing_slash_keeps_its_id_and_an_unused_supervision_entry_is_ignored(runs, tmp_path):
    sup = tmp_path / "s.json"
    sup.write_text(json.dumps({"f1": 7, "nobody": 3}), encoding="utf-8")
    data = json.loads(report(str(runs["f1"]) + "/", "--supervision", sup))
    assert data["runs"][0]["run_id"] == "f1" and data["runs"][0]["supervision_minutes"] == 7
    assert data["summary"]["supervision_minutes"] == {"runs_with_data": 1, "total": 7, "mean": 7}


def test_an_argument_that_is_not_a_run_is_refused(runs, tmp_path):
    (tmp_path / "empty").mkdir()
    for bad in (tmp_path / "empty", tmp_path / "missing"):
        r = script("pilot_report.py", runs["f1"], bad)
        assert r.returncode == 2 and r.stdout == "" and r.stderr.startswith("refused:") and "not a run directory" in r.stderr, \
            (bad.name, r.returncode, r.stderr[-300:])


def test_a_supervision_file_that_is_not_valid_is_refused(runs, tmp_path):
    for i, content in enumerate(["not json", "[1, 2]", '{"f1": -1}', '{"f1": "ten"}', '{"f1": true}', '{"f1": null}']):
        f = tmp_path / f"s{i}.json"
        f.write_text(content, encoding="utf-8")
        r = script("pilot_report.py", runs["f1"], "--supervision", f)
        assert r.returncode == 2 and r.stdout == "" and r.stderr.startswith("refused:") and "supervision" in r.stderr, \
            (content, r.returncode, r.stderr[-300:])
    missing = script("pilot_report.py", runs["f1"], "--supervision", tmp_path / "nope.json")
    assert missing.returncode == 2 and missing.stderr.startswith("refused:") and "supervision" in missing.stderr
