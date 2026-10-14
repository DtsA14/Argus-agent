"""Synthesize: merge this iteration's worker results into laporan.md.

The harness copies the Top 3 and the trend from the workers' validated values; nothing a model writes can change
them. Only the recommendations come from a writer: a fixed template (impl: fake) or a model (impl: llm, phase 3b).
Either way they go through the same rendering and are saved with their provenance (laporan.provenance.json:
each recommendation with the facts it references), which the evaluator re-checks against the data.
Contract: docs/MILESTONE3_PLAN.md, section 3.6.
"""
import json
from typing import List

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from pydantic import BaseModel, Field

from harness.crash import Crasher
from harness.errors import LLMCallFailed, ReservationExhausted
from harness.llm import is_truncated
from harness.steps import llm_step_key, message_from_json, message_to_json, reservation_from_ledger

from .facts import FORMAT_HELP, MAX_RECS, MIN_RECS, build_facts, fact_line, render_line, round_half_up, \
    validate_recommendations

PROVENANCE = "laporan.provenance.json"


def this_iteration(state):
    """(top3, trend) values from this iteration's results, by contract output name; [] for a failed worker."""
    iteration = state.get("iteration", 0)
    by_output = {r["output"]: r.get("value") for r in (state.get("results") or {}).values()
                 if r.get("iteration") == iteration}
    return by_output.get("top3") or [], by_output.get("trend") or []


def report_text(top3, trend, recs):
    lines = ["# Laporan Penjualan", "", "## Top 3 Produk"]
    lines += [f"- {n}: {v}" for n, v in top3]
    lines += ["", "## Tren Bulanan"]
    lines += [f"- {m}: {v}" for m, v in trend]
    lines += ["", "## Rekomendasi"]
    lines += [render_line(i, r) for i, r in enumerate(recs, 1)]
    return "\n".join(lines) + "\n"


def provenance_text(recs, writer):
    return json.dumps({"writer": writer, "recommendations": recs}, ensure_ascii=False, indent=2) + "\n"


def write_report(gate, run_dir, report_name, top3, trend, recs, writer):
    """Report first, then its provenance; both jailed to the run dir and written atomically (safe to repeat)."""
    gate.call("write_file", run_dir, report_name, report_text(top3, trend, recs))
    gate.call("write_file", run_dir, PROVENANCE, provenance_text(recs, writer))


def template_recommendations(top3, trend):
    """The fake writer: two fixed recommendations built from facts, in the canonical number format."""
    facts, recs = build_facts(top3, trend), []
    share = facts.get("top3.top2_share_of_top3_pct")
    if share:
        p1, p2 = facts["top3.1.product"]["value"], facts["top3.2.product"]["value"]
        recs.append({"text": f"{p1} and {p2} make up {round_half_up(share['value'], 1)}% of the revenue of the "
                             f"three best-selling products.",
                     "action": f"Offer a {p1} + {p2} bundle.",
                     "facts": ["top3.1.product", "top3.2.product", share["id"]]})
    growth = facts.get("trend.first_to_last_growth_pct")
    if growth:
        (m1, v1), (m2, v2) = trend[0], trend[-1]
        recs.append({"text": f"Total monthly revenue went from {int(v1)} in {m1} to {int(v2)} in {m2} "
                             f"({round_half_up(growth['value'], 1)}%).",
                     "action": "Raise stock ahead of demand." if growth["value"] > 0 else "Review prices and promotions.",
                     "facts": [f"trend.{m1}.revenue", f"trend.{m2}.revenue", growth["id"]]})
    return recs


def make_synthesize(gate, run_dir, log, report_name="laporan.md"):
    """impl: fake. Template recommendations, no model call."""

    def synthesize(state):
        top3, trend = this_iteration(state)
        write_report(gate, run_dir, report_name, top3, trend, template_recommendations(top3, trend), "template")
        return {"tokens_used": 1000}

    return synthesize


# ---- impl: llm (phase 3b) -------------------------------------------------------------------------

class Recommendation(BaseModel):
    text: str = Field(description="The insight, one sentence, with numbers only in the canonical format.")
    action: str = Field(description="The concrete action to take, one sentence.")
    facts: List[str] = Field(description="Ids of every fact this recommendation uses (each number must come from one).")


class SubmitRecommendations(BaseModel):
    """Submit the recommendations. Call this exactly once."""
    recommendations: List[Recommendation] = Field(description=f"{MIN_RECS} to {MAX_RECS} recommendations.")


def writer_system():
    return f"""You write the recommendations of a sales report for a small business owner.

Use only the facts in the table you are given. Each recommendation has an insight (text), a concrete action, and
the ids of the facts it uses. Every number you write, in the text or in the action, must be the value of a fact
you list; write no other numbers, not even in phrases like "top 3" (write "three" instead).
Number format: {FORMAT_HELP}. Percentages are the table's values, written with 0 or 1 decimal.
Give {MIN_RECS} to {MAX_RECS} recommendations that are specific and actionable, not a restatement of the data.
Do not claim causes, costs, margins or outside statistics that are not in the table.
Submit them with the SubmitRecommendations tool, exactly once. The harness checks every number; if it rejects
your submission you get the errors and can submit again."""


def writer_prompt(goal, facts):
    return "Goal: " + goal + "\n\nFacts (id = value):\n" + "\n".join(fact_line(f) for f in facts.values())


def make_llm_synthesize(caller, gate, memo, log, run_dir, *, tokens, usd, attempts=3, crasher=None,
                        report_name="laporan.md"):
    """impl: llm. The writer model fills in the recommendations; the harness validates every number against the
    fact table (built from this iteration's worker results), assembles the report and saves the provenance.
    Each model reply is committed to the memo before it is used, so a resumed run never buys it again."""
    crasher = crasher or Crasher()
    tools = [SubmitRecommendations]
    sys_msg = SystemMessage(writer_system())

    def synthesize(state):
        iteration = state.get("iteration", 0)
        top3, trend = this_iteration(state)
        meta = {"node": "synthesize", "iteration": iteration}
        res = reservation_from_ledger(log, tokens=tokens, usd=usd, node="synthesize", task=None, iteration=iteration)

        def done(recs, event, **fields):
            write_report(gate, run_dir, report_name, top3, trend, recs or [], str(caller.ref) if recs else "none")
            log.emit(event, **fields, **meta)
            return {"tokens_used": res.used_tokens, "usd_used": res.used_usd}

        if not top3 or not trend:   # nothing to ground recommendations in: do not pay for a model call
            return done([], "synthesize_skipped", reason="a required worker output is missing")

        facts = build_facts(top3, trend)
        messages = [sys_msg, HumanMessage(writer_prompt(state.get("goal", ""), facts))]
        errors = []
        for attempt in range(attempts):
            key = llm_step_key("synthesize", None, iteration, attempt, messages, tools, caller.ref)
            cached = memo.get(key)
            if cached is not None:
                msg = message_from_json(cached)
                log.emit("step_replayed", kind="llm", step=attempt, **meta)
            else:
                try:
                    msg = caller.call(messages, res, tools=tools, meta={**meta, "step": attempt})
                except ReservationExhausted as e:
                    return done([], "synthesize_failed", reason=f"node_reservation: {e}")
                except LLMCallFailed as e:
                    return done([], "synthesize_failed", reason=f"llm_failed: {e}")
                crasher.point("synthesize@after_llm", step=attempt, **meta)   # reply not yet committed
                memo.put(key, message_to_json(msg))
                log.emit("step_committed", kind="llm", step=attempt, **meta)
            messages.append(msg)

            if is_truncated(msg):   # may be cut off mid-argument: never validated or used, not retried (2e)
                return done([], "synthesize_failed", reason=f"output_truncated at step {attempt}")

            calls = list(msg.tool_calls or [])
            if len(calls) != 1 or calls[0].get("name") != "SubmitRecommendations":
                errors = [f"call only the SubmitRecommendations tool, exactly once; got {[c.get('name') for c in calls]}"]
            else:
                recs, errors = validate_recommendations(calls[0].get("args"), facts)
                if not errors:
                    return done(recs, "recs_accepted", step=attempt, count=len(recs))
            log.emit("recs_invalid", step=attempt, errors=[str(e)[:200] for e in errors[:10]], **meta)
            feedback = "Rejected by the harness:\n- " + "\n- ".join(errors) + "\nFix these and call SubmitRecommendations again."
            if calls:   # every tool_use must be answered before the next turn
                messages += [ToolMessage(feedback, tool_call_id=c.get("id") or f"call_{attempt}_{i}")
                             for i, c in enumerate(calls)]
            else:
                messages.append(HumanMessage(feedback))
        return done([], "synthesize_failed", reason=f"recommendations invalid after {attempts} attempts: "
                                                   + "; ".join(errors)[:300])

    return synthesize
