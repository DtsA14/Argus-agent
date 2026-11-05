"""Screening of the research-need candidates (pilots/research_need_v0/CANDIDATES.md): one DeepSeek call per candidate,
no tools, through LLMCaller (reservation $0.02 each, the ledger kept in this folder). The model is asked to write the code
and to say what FastAPI 0.162.0 / Starlette 1.10.0 do; Claude then compares the replies with the probes
(probe_params.py, probe_deprecations.py). Same model setup as the code arm of the pilots (deepseek-flash, thinking).

  python pilots/research_need_v0/screen.py        # asks for the DeepSeek key (not shown); needs a terminal
  DEEPSEEK_API_KEY=$(cat <key file>) python pilots/research_need_v0/screen.py     # without typing it

Exit codes: 0 all four answered, 1 an API refusal, 2 refused before sending.
"""
import getpass
import os
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

SYSTEM = ("You are a senior Python engineer. Answer from what you know; you have no tools and no internet. "
          "Be concise: code first, then the requested explanation in at most five sentences.")
CONTEXT = ("The app is argus-ledger: a FastAPI app (FastAPI 0.162.0, Starlette 1.10.0, Pydantic 2.14, Python 3.12) "
           "that serves the cost ledgers of jobs, read-only, with `create_app(jobs_dir)` and TestClient tests. ")

PROMPTS = {
    "K1": CONTEXT + ("Add `POST /jobs/{job_id}/note` taking a JSON body with a `note` key: a string sets the note, an "
                     "explicit JSON null clears it, and leaving the key out leaves the note unchanged. Write the "
                     "endpoint. Then explain how FastAPI 0.162.0 treats an explicit JSON null versus an omitted key "
                     "for the parameter you declared, and whether FastAPI 0.143 treated them differently."),
    "K2": CONTEXT + ("Add filtering and paging to `GET /jobs`: optional `state`, `limit` (default 20), `offset` (default "
                     "0). Keep the filter and the paging as two separate Pydantic models declared with `Query()`, so "
                     "that both can be reused on `GET /jobs.csv`. Write the code. Then say whether two Pydantic "
                     "query-parameter models can be declared on one endpoint in FastAPI 0.162.0 and in 0.143.2, and "
                     "whether such a model can itself be optional (`Model | None = None`)."),
    "K3": CONTEXT + ("The app will be served at https://host/ledger/ by a reverse proxy that strips the `/ledger` "
                     "prefix. Every redirect (`RedirectResponse('/login')`, `'/ui'`) and every link in the HTML must "
                     "work under that prefix. Show the changes (app creation and one redirect). Say which parameter "
                     "or server option of FastAPI 0.162.0 you use for the prefix and whether anything about it is "
                     "deprecated in 0.162.0."),
    "K4": CONTEXT + ("Add `GET /jobs/stream` (`text/event-stream`, one event per job). Write a pytest with Starlette "
                     "1.10.0's TestClient that reads the first event and closes the response without waiting for the "
                     "stream to finish. Say what changed in `TestClient.stream` between Starlette 1.8.0 and 1.10.0 "
                     "that matters for this test."),
}


def text_of(msg):
    c = msg.content
    if isinstance(c, list):
        c = "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in c)
    return str(c)


def main():
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()        # set by Atha for this one command, e.g. from his key file
    if not key:
        if not sys.stdin.isatty():
            print("refused: run it in a terminal; the key is typed, never passed", file=sys.stderr)
            return 2
        key = getpass.getpass("Type or paste the DeepSeek API key, then Enter (not shown): ").strip()
    if not key or any(c.isspace() for c in key):
        print(f"refused: the key is empty or has whitespace (got {len(key)} characters)", file=sys.stderr)
        return 2
    cfg = load_config()
    role = "drafter"
    cfg["roles"][role] = {**cfg["roles"][role], "model": "deepseek:deepseek-flash", "max_output_tokens": 4000,
                          "params": {"extra_body": {"thinking": {"type": "enabled"}}, "reasoning_effort": "low"}}
    cfg["budget"]["max_usd"] = 0.02 * len(PROMPTS)
    os.environ["DEEPSEEK_API_KEY"] = key
    out = HERE / "screen_replies"
    out.mkdir(exist_ok=True)
    try:
        log = EventLog(HERE / "screen_events.jsonl")
        caller = LLMCaller(cfg, role, log)
        for name, prompt in PROMPTS.items():
            res = Reservation(tokens=20000, usd=0.02)
            reply = caller.call([SystemMessage(SYSTEM), HumanMessage(prompt)], res,
                                meta={"node": "screen", "task": name, "iteration": 0, "step": 0})
            (out / f"{name}.txt").write_text(text_of(reply), encoding="utf-8")
            print(f"{name}: {len(text_of(reply))} characters")
        _, totals = reconcile_ledger(log.read())
        print(f"cost ${totals['usd']:.6f}")
        return 0
    except LLMCallFailed as e:
        print(f"FAIL: the API refused: {str(e)[:300]}")
        return 1
    finally:
        os.environ.pop("DEEPSEEK_API_KEY", None)


if __name__ == "__main__":
    sys.exit(main())
