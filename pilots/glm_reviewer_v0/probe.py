"""GLM as a code reviewer, smallest experiment (pilots/self_review_v0 follow-up, Atha 2026-11-07). The judge prompt found
0/5 of the review bugs of #326; here GLM-5.3 (role code_judge: OpenRouter, Baidu fp8 pin) gets a bug-hunting prompt, the
whole changed file instead of the diff alone, and one refutation call per finding. No tools. Every call goes through
LLMCaller; the ledger is kept in this folder. Claude scores the verified findings against SPEC_RATE_LIMIT_RETRY section 5.

  .venv-verify/bin/python pilots/glm_reviewer_v0/probe.py     # asks for the OpenRouter key (not shown); needs a terminal

Input: diff of b65ec4f8 (#326 before its review fixes), harness/llm.py and tests/test_gateway.py at that commit, and the
spec sections 1-4 (the issue, without section 5, which lists the review findings).

Exit codes: 0 done, 1 an API refusal, 2 refused before sending.
"""
import getpass
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from langchain_core.messages import HumanMessage, SystemMessage  # noqa: E402

from harness.errors import LLMCallFailed  # noqa: E402
from harness.events import EventLog  # noqa: E402
from harness.llm import LLMCaller, Reservation, reconcile_ledger  # noqa: E402
from runner import load_config  # noqa: E402

COMMIT = "b65ec4f8"
MAX_FINDINGS = 6
PER_CALL = Reservation(tokens=70000, usd=0.05)

HUNT = (
    "You are a senior engineer reviewing a pull request for correctness bugs. Do not summarise the change and do not "
    "check it only against the issue: hunt for inputs, states and sequences under which the code as written behaves "
    "wrongly. Look in particular at: edge cases and boundary values (zero, negative, NaN, infinity, empty, missing), "
    "error paths and mixed sequences of different errors, interactions between the new code and the existing code "
    "around it, configuration values the code accepts without checking, and tests that do not test what they claim. "
    "Trace the code before you report: a finding must name a concrete input or sequence and the wrong result. Before "
    "you claim a test has a side effect (sleeping, network), check the helpers it calls in the files you are given. "
    "Reply with at most 8 findings, most severe first, as one JSON array in a ```json fence, each item "
    '{"file": ..., "line_or_function": ..., "summary": ..., "scenario": ...}. An empty array is a valid answer.')

VERIFY = (
    "You are checking one claimed bug in a pull request. Try to refute it: trace the code you are given for the "
    "scenario it names. Reply with one JSON object in a ```json fence: "
    '{"verdict": "REAL" | "NOT_A_BUG" | "UNSURE", "reason": "<at most three sentences, citing the code>"}.')


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout


def context():
    spec = git("show", f"{COMMIT}:docs/reviews/SPEC_RATE_LIMIT_RETRY.md")
    spec = spec.split("\n## 5", 1)[0]
    return "\n\n".join([
        "# The issue (spec sections 1-4)\n\n" + spec,
        f"# The diff of the pull request\n\n```diff\n{git('show', '--format=', COMMIT)}```",
        f"# harness/llm.py after the change (whole file)\n\n```python\n{git('show', f'{COMMIT}:harness/llm.py')}```",
        f"# tests/test_gateway.py after the change (whole file)\n\n```python\n"
        f"{git('show', f'{COMMIT}:tests/test_gateway.py')}```",
    ])


def text_of(msg):
    c = msg.content
    if isinstance(c, list):
        c = "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in c)
    return str(c)


def fenced_json(text):
    m = re.findall(r"```json\s*(.*?)```", text, re.S)
    try:
        return json.loads(m[-1]) if m else None
    except ValueError:
        return None


def main():
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        if not sys.stdin.isatty():
            print("refused: run it in a terminal; the key is typed, never passed", file=sys.stderr)
            return 2
        key = getpass.getpass("Type or paste the OpenRouter API key, then Enter (not shown): ").strip()
    if not key or any(c.isspace() for c in key):
        print(f"refused: the key is empty or has whitespace (got {len(key)} characters)", file=sys.stderr)
        return 2
    cfg = load_config()
    role = "code_judge"
    cfg["budget"]["max_usd"] = PER_CALL.usd * (1 + MAX_FINDINGS)
    ctx = context()
    os.environ["OPENROUTER_API_KEY"] = key
    out = HERE / "out"
    out.mkdir(exist_ok=True)
    try:
        log = EventLog(HERE / "events.jsonl")
        caller = LLMCaller(cfg, role, log)
        reply = text_of(caller.call([SystemMessage(HUNT), HumanMessage(ctx)], PER_CALL,
                                    meta={"node": "review", "task": "hunt", "iteration": 0, "step": 0}))
        (out / "hunt.md").write_text(reply, encoding="utf-8")
        findings = fenced_json(reply)
        if not isinstance(findings, list):
            print("hunt: no JSON array in the reply; see out/hunt.md")
            findings = []
        print(f"hunt: {len(findings)} findings")
        results = []
        for i, f in enumerate(findings[:MAX_FINDINGS]):
            claim = "# The claimed bug\n\n" + json.dumps(f, indent=2, ensure_ascii=False)
            v = text_of(caller.call([SystemMessage(VERIFY), HumanMessage(ctx + "\n\n" + claim)], PER_CALL,
                                    meta={"node": "review", "task": f"verify{i}", "iteration": 0, "step": 0}))
            (out / f"verify{i}.md").write_text(v, encoding="utf-8")
            verdict = fenced_json(v) or {"verdict": "UNPARSED"}
            results.append({"finding": f, "check": verdict})
            print(f"  {i}: {verdict.get('verdict')}: {str(f.get('summary', ''))[:100]}")
        (out / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        _, totals = reconcile_ledger(log.read())
        print(f"cost ${totals['usd']:.6f}")
        return 0
    except LLMCallFailed as e:
        print(f"FAIL: the API refused: {str(e)[:300]}")
        return 1
    finally:
        os.environ.pop("OPENROUTER_API_KEY", None)


if __name__ == "__main__":
    sys.exit(main())
