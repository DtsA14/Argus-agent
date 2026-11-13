"""Knowledge-cutoff check for the agent model (Fable's order 2026-11-13): did DeepSeek see these issues and their fixes in training?
Not part of the harness; a human runs it on purpose (the key is typed, never passed).

  python pilots/outside_v2/knowledge_check.py        # from the repo root with .venv-verify; asks for the DeepSeek key (not shown)

No tools, no web, no repository: the model gets only the repo name, the issue number and the issue title, and is asked (1) whether it remembers,
(2) the year-month the issue was closed, (3) the number of the PR that fixed it, (4) what the fix changed. The truth comes from GitHub (TRUTH below).
The mechanical signal is (2): a model cannot know the closing month of an issue that closed after its training data ends, and a guess lands on the
right month about 1 time in 24. (3) is weaker: in more-itertools the fixing PR is often issue+1, so a guess can hit. (4) is read by a person against
the real patch. Controls: a nonexistent issue (the answer must be "no"), and an old issue the model should know (boltons #297, PR #302, 2022-12).
Same model and thinking mode as the agent (deepseek-flash, thinking on, effort low). Every call goes through LLMCaller (reservation, ledger).
Costs a few cents at most (budget cap $0.20). Output: pilots/outside_v2/knowledge_check.json (no key in it).
"""
import getpass
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from langchain_core.messages import HumanMessage, SystemMessage  # noqa: E402

from harness.errors import LLMCallFailed  # noqa: E402
from harness.events import EventLog  # noqa: E402
from harness.llm import LLMCaller, Reservation, reconcile_ledger  # noqa: E402
from runner import load_config  # noqa: E402

BO, MI = "mahmoud/boltons", "more-itertools/more-itertools"
# label, repo, issue, title (as on GitHub), closed (YYYY-MM), fixing PR. Closing dates and PRs from GitHub (candidates.jsonl, gh api, 2026-11-13).
TRUTH = [
    ("bo-322", BO, 322, "Function to format a list with commas and a final 'and'/'or'", "2025-12", 388),
    ("bo-393", BO, 393, "Bug: `research` fails to traverse identical small tuples.", "2026-01", 394),
    ("bo-383c", BO, 383, "Supporting more PathLike in path-related methods", "2026-07", 416),
    ("mi-1257", MI, 1257, None, "2026-09", 1261),
    ("mi-1277", MI, 1277, None, "2026-09", 1278),
    ("mi-1284", MI, 1284, None, "2026-09", 1285),
    ("mi-1304c", MI, 1304, "ichunked(..., 0) raises islice's ValueError on a nonempty iterable", "2026-09", 1305),
    ("mi-1344c", MI, 1344, "numeric_range equality and hashing overflow for lengths above sys.maxsize", "2026-11", 1345),
]
CONTROLS = [
    ("old-bo-297", BO, 297, "daterange(start, stop, inclusive=True) returns an infinite iterator when start and stop are identical", "2022-12", 302),
    ("none-bo-99999", BO, 99999, "Add a frobnicate() helper to boltons.iterutils", None, None),
]
SYSTEM = ("You answer from memory only. You have no tools and no internet. If you do not remember a specific fact, say so; "
          "never guess a date or a number to look helpful. Reply with one JSON object and nothing else.")


def title_of(label, repo, n):
    """The two more-itertools titles not typed above come from candidates.jsonl."""
    for line in (ROOT / "pilots/outside_v1/candidates.jsonl").read_text().splitlines():
        d = json.loads(line)
        if d["repo"] == repo and d["issue"] == n:
            return d["title"]
    raise SystemExit(f"no title for {label}")


def ask(repo, n, title):
    return (f"GitHub repository {repo}, issue #{n}, titled: {title!r}.\n"
            'Reply as JSON: {"remember": "yes" | "partly" | "no", "closed_year_month": "YYYY-MM" or null, '
            '"fixing_pr_number": integer or null, "fix": "what the fix changed, one or two sentences, or empty"}.\n'
            'Use "no" and nulls when you do not actually remember this issue; do not infer from the title.')


def main():
    if not sys.stdin.isatty():
        print("refused: run it in a terminal; the key is typed, never passed", file=sys.stderr)
        return 2
    key = getpass.getpass("Type or paste the DeepSeek API key, then Enter (not shown): ").strip()
    if not key or any(c.isspace() for c in key):
        print("refused: the key is empty or has whitespace", file=sys.stderr)
        return 2
    cfg = load_config()
    role = "drafter"
    cfg["roles"][role] = {**cfg["roles"][role], "model": "deepseek:deepseek-flash", "max_output_tokens": 4096,
                          "params": {"extra_body": {"thinking": {"type": "enabled"}}, "reasoning_effort": "low"}}
    cfg["budget"]["max_usd"] = 0.20
    os.environ["DEEPSEEK_API_KEY"] = key
    rows = []
    try:
        with tempfile.TemporaryDirectory() as d:
            log = EventLog(Path(d) / "events.jsonl")
            caller = LLMCaller(cfg, role, log)
            self_report = caller.call([SystemMessage("Answer briefly and honestly."),
                                       HumanMessage("What is your training-data cutoff (year and month)? One line; say if you are unsure.")],
                                      Reservation(tokens=20000, usd=0.02), meta={"node": "check", "task": "cutoff_self", "iteration": 0, "step": 0})
            print("self-reported cutoff:", str(self_report.content).strip()[:200])
            for i, (label, repo, n, title, closed, pr) in enumerate(TRUTH + CONTROLS, start=1):
                title = title or title_of(label, repo, n)
                msg = caller.call([SystemMessage(SYSTEM), HumanMessage(ask(repo, n, title))], Reservation(tokens=20000, usd=0.02),
                                  meta={"node": "check", "task": "cutoff_probe", "iteration": i, "step": 0})
                raw = str(msg.content).strip()
                try:
                    ans = json.loads(raw[raw.index("{"):raw.rindex("}") + 1])
                except ValueError:
                    ans = {"unparsed": raw[:300]}
                rows.append({"label": label, "repo": repo, "issue": n, "title": title, "truth_closed": closed, "truth_pr": pr, "answer": ans,
                             "month_right": ans.get("closed_year_month") == closed if closed else None,
                             "pr_right": ans.get("fixing_pr_number") == pr if pr else None})
                print(f"{label:14} remember={ans.get('remember')} closed={ans.get('closed_year_month')} (truth {closed}) pr={ans.get('fixing_pr_number')} (truth {pr})")
            _, totals = reconcile_ledger(log.read())
            out = {"model": "deepseek:deepseek-flash", "self_reported_cutoff": str(self_report.content).strip(), "usd": totals["usd"], "rows": rows}
            (ROOT / "pilots/outside_v2/knowledge_check.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
            print(f"cost ${totals['usd']:.6f}; wrote pilots/outside_v2/knowledge_check.json")
            return 0
    except LLMCallFailed as e:
        print(f"FAIL: the API refused: {str(e)[:300]}")
        return 1
    finally:
        os.environ.pop("DEEPSEEK_API_KEY", None)


if __name__ == "__main__":
    from harness import redact as _redact
    _redact.install()                     # no registered key value reaches the terminal (FIX-C D7), chained tracebacks included
    sys.exit(main())
