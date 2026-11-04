# Research eval v0: results

The batch for `evals/research_v0` (questions R1..R8, keys in `KEYS.md`, frozen before the run) ran on 2026-11-04 after
Atha's one "go live". It ran from `main` at 1d4a733 (PR #289) in `~/pilot3a_live`, sequentially, 05:44–07:38 UTC.

The spec planned 8 jobs on the default `deepseek` profile. Since then the gateway (SPEC_GATEWAY_PROVIDER) was merged,
and the batch instead ran every question once on each of two profiles, 16 jobs in total:

- **`deepinfra`**: all stages on `openrouter:deepseek/deepseek-v4.1-flash`, pinned to DeepInfra fp8.
- **`free`**: planner and writer on Nemotron 3 Ultra (free), workers on Nemotron 3.5 Super VL (free), and the checker
  on Gemma 4 31B (free) with free fallbacks.

Both profiles use DeepSeek for web search and fetch. Every job had a $1.00 cap. No job crashed or was BLOCKED, so none
was resumed.

Grading followed `KEYS.md`. Claude judged each report item (summary S and P1..) against the quotes it cites, before
looking at e1's verdict. S = SUPPORTED, P = PARTIAL (the claim's core is quoted, some detail is not), U = UNSUPPORTED.

## Results per job

| Q | profile | job | end state | answer | items S/total | e1 | cost | wall |
|---|---|---|---|---|---|---|---|---|
| R1 | deepinfra | j20261104_054440_f65f | REPORT_READY | correct | 8/13 | checked, 11/13 agree | $0.0357 | 6.5 min |
| R1 | free | j20261104_055109_3e57 | REPORT_READY | partial (no date) | 2/3 | checked, 3/3 agree | $0.0053 | 2.3 min |
| R2 | deepinfra | j20261104_055330_7aec | REPORT_READY | correct | 8/15 | NOT_CHECKED (output_truncated) | $0.0452 | 10.4 min |
| R2 | free | j20261104_060355_e962 | REPORT_READY | partial (no `.dict()`) | 4/4 | NOT_CHECKED (submits_exhausted) | $0.0067 | 2.5 min |
| R3 | deepinfra | j20261104_060625_7c52 | REPORT_READY | correct | 7/14 | NOT_CHECKED (output_truncated) | $0.0611 | 17.3 min |
| R3 | free | j20261104_062342_7dde | REPORT_READY | partial (date only) | 2/2 | checked, 1/2 agree | $0.0075 | 4.5 min |
| R4 | deepinfra | j20261104_062810_1d11 | REPORT_READY | correct | 10/17 | NOT_CHECKED (output_truncated) | $0.0425 | 8.1 min |
| R4 | free | j20261104_063620_026e | REPORT_READY | partial (no TCP, RFC 7540) | 6/8 | NOT_CHECKED (submits_exhausted) | $0.0120 | 8.0 min |
| R5 | deepinfra | j20261104_064419_0851 | REPORT_READY | correct | 12/16 | NOT_CHECKED (output_truncated) | $0.0460 | 9.5 min |
| R5 | free | j20261104_065350_b954 | RESEARCH_INCONCLUSIVE | none | – | – | $0.0173 | 4.5 min |
| R6 | deepinfra | j20261104_065819_b5f0 | REPORT_READY | correct | 2/10 | NOT_CHECKED (output_truncated) | $0.0511 | 9.6 min |
| R6 | free | j20261104_070754_1f51 | REPORT_READY | correct | 2/7 | checked, 3/7 agree | $0.0143 | 3.4 min |
| R7 | deepinfra | j20261104_071122_6cb0 | REPORT_READY | correct | 7/9 | checked, 9/9 agree | $0.0379 | 8.4 min |
| R7 | free | j20261104_071945_2d7f | REPORT_READY | correct | 4/4 | checked, 3/4 agree | $0.0067 | 4.0 min |
| R8 | deepinfra | j20261104_072344_b37a | REPORT_READY | correct | 14/17 | NOT_CHECKED (output_truncated) | $0.0474 | 12.8 min |
| R8 | free | j20261104_073636_b73f | RESEARCH_INCONCLUSIVE | none | – | – | $0.0037 | 1.5 min |

Cost is the job's ledger total, as `argus research` printed it. Wall time runs from the first stage's start to the last
stage's end. Atha made one decision for the whole batch: "go live".

## Summary

| | deepinfra | free |
|---|---|---|
| answer correct / partial / none | **8 / 0 / 0** | 2 / 4 / 2 |
| answer wrong (contradicts a key) | 0 | 0 |
| report items supported (Claude) | 68/111 = 61% | 20/28 = 71% |
| report items UNSUPPORTED (Claude) | 0 | 0 |
| e1 checked the report | 2/8 | 4/6 |
| cost: total / mean per job | $0.367 / $0.046 | $0.074 / $0.009 (web only) |
| wall time, mean | 10.3 min | 3.8 min |

The whole batch cost $0.44.

- **No report contradicts a key, and no item is UNSUPPORTED.**
- **Every PARTIAL item is a detail the writer added beyond the quote.** Examples: a release manager's name, a date, an
  option name, or a sentence cut short inside the quote. In every case the item's main claim was quoted.
  - R6 deepinfra (2/10) is the extreme case. Its answer is right, but most paragraphs name people, dates or PEP
    statuses that the quotes do not contain.
- **e1 agreement: 30 of 38 items (79%)**, over the 6 reports e1 checked.
  - e1 was more lenient 5 times (Claude PARTIAL, e1 SUPPORTED) and stricter 3 times.
  - e1 never said UNSUPPORTED, and neither did Claude.

## What went wrong

1. **e1 on deepinfra ran out of output in 6 of 8 jobs.** DeepSeek v4.1 Flash through OpenRouter reasons before it
   answers. In R2 the single call returned `output_tokens 16000, reasoning_tokens 16000, stop_reason length`: the whole
   output cap went to reasoning, and no `SubmitCheck` came back.
   - The loop ends at once on `output_truncated`, so the job still reached REPORT_READY, but unchecked.
   - The earlier smoke run (j20261104_044215_a606, 13 items) fit; the larger reports (14–17 items) did not.
   - Proposed fix: cap the checker's reasoning (OpenRouter `reasoning.max_tokens` or effort) and/or raise its output
     cap. Its $0.10 stage cap is unchanged, and one truncated call cost $0.007.
2. **The free workers often fail the quote gate (G2).**
   - R5 free: all 4 workers ended NO_FINDINGS. R8 free: both workers did. That made those jobs RESEARCH_INCONCLUSIVE,
     and it explains the missing points in R1–R4 free.
   - Nemotron 3.5 Super VL paraphrases or merges quotes, and once used a search result as a source (G1).
   - One bad source rejects the whole submission. After 3 submissions the worker's good findings are lost too.
   - Proposed fix (needs a decision, since it touches the research gates): keep the findings that pass, drop the ones
     that fail. The gate guarantees stay as they are.
3. **Both free Gemma checkers returned HTTP 429 every time.** In each of the 6 free jobs that reached e1, the chain
   fell back twice (Gemma 31B → Gemma 26B → Nemotron VL; 6 free 429s, $0, as designed).
   - Nemotron VL then checked 4 reports and exhausted its submits on 2 (R2, R4).
   - The fallbacks work, but the two Gemma entries only add latency. Proposed fix: put Nemotron VL first.
4. **Quotes cut mid-sentence** (for example "should be replaced with", "can in most cases be changed to") hide the very
   name the paragraph states. Both are worker-side issues and could be fixed in the prompts:
   - workers should quote whole sentences;
   - the writer should not add names, dates or numbers that are not in a quote.

## Reading

- **Paid answers were right.** On this set, the `deepinfra` profile answers correctly (8/8) for about 5 cents and about
  10 minutes per question.
- **The checker is not yet in place.** In this batch it checked 2 of 8 paid reports, so reports went out unchecked;
  fix 1 comes first.
- **Free is not yet a substitute.** It never answered wrongly, but it lost points on the free worker's quotes (4
  partial answers, 2 with no report). With fix 2 it would keep whatever the worker did quote correctly.
- **Proposed v1 threshold** (§10, for Atha to decide), on the paid profile:
  - at least 7/8 answers correct and none wrong;
  - no UNSUPPORTED item;
  - at least 60% of items SUPPORTED;
  - e1 completes on at least 7/8 reports.

  This batch meets every point except the last one.

## Rerun after the fixes (R2, R5, R8)

After Atha's "go live", R2, R5 and R8 ran again on both profiles. They ran from `main` at dd6d922 (#291 and #292), from
08:58 to 09:55 UTC. Grading is the same as above.

| Q | profile | job | answer | items S/total | e1 | e1 agree | dropped at last submit | cost | wall |
|---|---|---|---|---|---|---|---|---|---|
| R2 | deepinfra | j20261104_085808_9c14 | correct | 7/13 | checked | 8/13 | w4: 2 | $0.0477 | 12.1 min |
| R2 | free | j20261104_091017_b02c | partial (no `@field_validator`) | 4/4 | checked (Ultra) | 4/4 | – | $0.0053 | 2.9 min |
| R5 | deepinfra | j20261104_091312_72d5 | correct | 11/14 | checked | 12/14 | – | $0.0532 | 14.2 min |
| R5 | free | j20261104_092725_95b4 | partial (no concurrency guarantee) | 6/9 | checked (Ultra) | 6/9 | w3: 2 | $0.0097 | 6.4 min |
| R8 | deepinfra | j20261104_093351_1185 | correct | 15/17 | checked | 17/17 | w3: 1 | $0.0600 | 15.1 min |
| R8 | free | j20261104_094857_7249 | correct | 2/6 | checked (Ultra) | 3/6 | w2: 2, w3: 1 | $0.0060 | 5.8 min |

Compared with the same three questions in the first batch:

| | before | after |
|---|---|---|
| deepinfra: answers correct | 3/3 | 3/3 |
| deepinfra: items supported (Claude) | 34/48 = 71% | 33/44 = 75% |
| deepinfra: e1 checked | 0/3 | 3/3 |
| free: answers correct / partial / none | 0 / 1 / 2 | 1 / 2 / 0 |
| free: e1 checked | 0/1 | 3/3, on Nemotron Ultra with no fallback |
| e1 agreement with Claude | – | 50/63 = 79%; e1 was the more lenient side in every disagreement |
| cost per job (deepinfra / free) | $0.046 / $0.009 | $0.054 / $0.007 |
| wall time per job (deepinfra) | 10.9 min | 13.8 min |

- **Keep-passing worked.** Five workers kept their good findings on the last submit (8 sources dropped in total).
  Without it, R5 free and R8 free would again have had no report.
  - Some free workers still end NO_FINDINGS: 4 of 9.
- **Every e1 run finished, but the paid reasoning cap is not enforced.** With `reasoning.max_tokens: 6000`, the first e1
  call still used 15,519 reasoning tokens in R2 and 10,074 in R5. R2's call reached the whole 16,000-token output cap,
  and its tool call fit in the last 481 tokens. Fix 1 therefore holds only by margin.
  - Next step: switch to a cap that is enforced, for example `reasoning.effort` or turning reasoning off for e1, or
    raise the output cap. Then check that the e1 events show reasoning tokens below the cap.
- **Quotes are now whole sentences in most findings.** The R2 deepinfra worker w4 still cut quotes short, for example
  "...to apply" and "...you can pass". Every PARTIAL item in that report comes from w4's findings or adds a detail no
  quote holds.
- **No answer is wrong, and no item is UNSUPPORTED.**
