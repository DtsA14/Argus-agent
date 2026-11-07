# Screening of the research-need candidates: result (2026-11-05)

Method (CANDIDATES.md "Penyaringan"): one DeepSeek call per candidate (deepseek-flash, thinking, no tools, via
LLMCaller, reservation $0.02 each), asked to write the code and to say what FastAPI 0.162.0 / Starlette 1.10.0 do.
Replies in `screen_replies/` (`run1_truncated/`: K2 and K4 of the first run, cut by a 4000 output cap that thinking used
up; rerun with 12000), ledger in `screen_events.jsonl`. Cost $0.0240 for six calls (K1, K3, K2, K4 and the two cut ones).
Run by Atha (the key is typed or read by his shell; Claude never touches it).

| | model's answer | probe (up1 → up2) | verdict |
|---|---|---|---|
| K1 `null` vs omitted | Pydantic model + `model_fields_set`; says 0.143 and 0.162 both distinguish them | works on both versions | **knows**; code correct on both |
| K2 two query models | says two models are allowed in 0.162.0, not in 0.143.2; optional model supported in 0.162.0 | 422 / `AssertionError` on up1, 200 on up2 | **knows exactly** (including the up1 limit); code correct on up2 |
| K3 prefix `/ledger` | `FastAPI(root_path=...)`, redirects through `request.url_for`; "cannot say whether anything is deprecated in 0.162.0" | `root_path=` warns `FastAPIDeprecationWarning` (a `UserWarning`) on up2, behaviour correct | **gap in knowledge, behaviour passes**; only a warning |
| K4 TestClient stream | infinite-generator SSE endpoint and a test that closes early; "cannot verify the 1.8.0 → 1.10.0 delta" | on 1.10 `client.stream()` returns early and closing cancels the app; on 1.8 such a test would hang | **admits the gap, code correct on 1.10** (it only hangs on the old version) |

Reading (n = 4, one reply each: an anecdote, not a measurement):
- The pre-registered rule said a candidate goes on to the two-arm pilot when the answer is wrong by the probe. By the
  knowledge criterion K3 and K4 are gaps; by the behaviour a hidden grader would test, all four replies pass on up2.
  A two-arm pilot on them would most likely repeat pilot 015: both arms correct, the research only costs money.
- The one place research would change the outcome is K3, and only for style (a deprecation warning that
  `-W error::DeprecationWarning` does not even catch), not correctness.
- K2 is the clearest result: the model knew a feature released 13 days earlier (after its likely cutoff, or it
  generalised from the earlier single-model API), down to the older version's restriction.
- Thinking uses most of the output budget: a 4000 cap cut two of four replies; the cap for such calls is 12000.

Decision for PENDING: the research-before-code path has no evidence for a planner that chains research → code
(pilot 015 and this screening, five anecdotes in all). Stop looking for such an issue until a real failure of the
code-only arm shows up in normal use; record the failure then. The hierarchical planner is not justified from this line.
