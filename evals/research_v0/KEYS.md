# Research eval set v0: answer keys (SPEC_RESEARCH_JOB §10)

Written by Claude on 2026-11-04 **before any run**, together with `questions/R1.txt`..`R8.txt`, and frozen in the same
commit as the stages (PR C). Nothing here changes after the batch starts; a key found wrong after the run is noted in
the results, not edited here. The keys are from what Claude knows (knowledge to June 2026), not from the job's sources.

Mix (§10): official documentation facts (R1, R3, R8), a library API change (R2), comparisons (R4, R5), a question whose
correct answer is "no evidence" (R6), and one topic that is not code (R7).

## How a job is graded (by Claude, after the batch)

- **Answer** against the key: `correct` (every *must* point, nothing that contradicts a key point), `partial` (some
  *must* points, no contradiction), `wrong` (a contradiction, or a *wrong if* below), `none` (no report: PLAN_FAILED,
  SYNTHESIS_FAILED, BLOCKED; RESEARCH_INCONCLUSIVE counts as `correct` only for R6).
- **Supported paragraphs:** for every item of the report (summary S and P1..), does what it states follow from the
  quotes it cites? Claude's own check, item by item, without looking at e1's flag first. Reported as a percentage.
- **e1 agreement:** Claude's verdict per item (SUPPORTED/PARTIAL/UNSUPPORTED) against e1's; agreement rate and the
  disagreements listed.
- **Cost, time, Atha's decisions:** from `job.json` and the ledgers (`argus status`), wall time from the job's stage
  times, decisions = the one "go live" for the batch plus anything else Atha had to decide.

No threshold for v1 is set now (§10); it is proposed after the numbers.

## Keys

### R1: Python 3.13.0 (official documentation)
- *must:* released **7 October 2024**.
- *must:* at least two of: an experimental **free-threaded build** without the GIL (PEP 703); an experimental **JIT
  compiler** (PEP 744); (not experimental, but accepted as context) the new interactive interpreter (REPL).
- *wrong if:* a different date, or free threading / the JIT described as non-experimental (default) in 3.13.

### R2: Pydantic v2 migration (library API change)
- *must:* `.dict()` → **`model_dump()`**; `.parse_obj()` → **`model_validate()`**; `@validator` → **`@field_validator`**.
- *accepted extra:* `@root_validator` → `@model_validator`; `.json()` → `model_dump_json()`; the old names are deprecated,
  still available in v2 with warnings.
- *wrong if:* any of the three mapped to another name.

### R3: NumPy 2.0.0 (official documentation)
- *must:* released **16 June 2024**.
- *must:* at least two of: an **ABI break** (C extensions built against NumPy 1.x must be rebuilt); **removed or moved
  names** in the main namespace (aliases such as `np.float_`, `np.NaN` removed; NumPy 2.0 "Python API cleanup",
  NEP 52); **type promotion rules changed** (NEP 50, scalar precision kept); the **default integer on Windows** is now
  64-bit.
- *wrong if:* a different release date, or "fully backward compatible".

### R4: HTTP/3 vs HTTP/2 (comparison)
- *must:* HTTP/3 runs over **QUIC over UDP**; HTTP/2 over **TCP** (usually with TLS).
- *must:* HTTP/3 avoids **TCP head-of-line blocking** between streams (loss on one stream does not stall the others).
- *must:* HTTP/3 is **RFC 9114** (June 2022); HTTP/2 is **RFC 9113** (2022, obsoletes RFC 7540; RFC 7540 alone is
  accepted as `partial` for this point). QUIC itself is RFC 9000 (accepted extra).
- *accepted extra:* TLS 1.3 built into QUIC; faster connection setup (0-RTT/1-RTT); QPACK instead of HPACK.
- *wrong if:* HTTP/3 said to run over TCP, or HTTP/2 over UDP.

### R5: PostgreSQL MERGE vs INSERT ... ON CONFLICT (comparison)
- *must:* `INSERT ... ON CONFLICT` since **9.5**; `MERGE` since **15**.
- *must:* ON CONFLICT is an insert that, on a conflict with a **unique index/constraint** (the arbiter), does nothing or
  updates the existing row, and is **atomic under concurrency** (insert-or-update guaranteed); MERGE joins a source with
  a target and runs `WHEN MATCHED` / `WHEN NOT MATCHED` actions that can **INSERT, UPDATE or DELETE**, but does not give
  that guarantee (concurrent inserts can still raise a unique violation).
- *accepted extra:* MERGE follows the SQL standard; RETURNING for MERGE since 17.
- *wrong if:* swapped versions, or MERGE said to need a unique constraint the way ON CONFLICT does.

### R6: Python 4.0 date (no evidence: the correct answer is that there is none)
- *must:* says there is **no official release date** (no announcement by the Steering Council or the PSF); the job may
  end RESEARCH_INCONCLUSIVE, or with a report whose answer is "no date has been announced".
- *accepted extra:* core developers have said there are no plans for a Python 4 / the next versions are 3.x.
- *wrong if:* any date or year given as the planned release of Python 4.0.

### R7: WHO free sugars (not code)
- *must:* free sugars **below 10% of total energy intake** (strong recommendation, WHO guideline 2015).
- *must:* a further reduction to **below 5%** (conditional recommendation), about **25 g (6 teaspoons) a day** for an
  adult of normal body mass index (the grams may be missing for `partial`).
- *accepted extra:* applies to adults and children; free sugars = added sugars plus those naturally in honey, syrups and
  fruit juices, not those in whole fruit, vegetables and milk.
- *wrong if:* the percentages swapped or a different limit given as WHO's.

### R8: PEP 723 (official documentation / standard)
- *must:* **inline script metadata**: a single-file script declares its own metadata (dependencies, Python version) so
  tools can run it.
- *must:* the block is **comment lines** opened by `# /// script` and closed by `# ///`, each line in between starting
  with `#`, holding **TOML**; keys **`dependencies`** and **`requires-python`** (and a `[tool]` table).
- *accepted extra:* accepted in January 2024; now a PyPA specification ("Inline script metadata"); tools such as uv,
  pipx, Hatch and PDM run such scripts.
- *wrong if:* the block described as a separate file, a docstring, or `pyproject.toml` content outside comments.

## Running the batch (only after Atha's one "go live" for the whole set, 2026-11-03 decision 5)

8 jobs, each with the default cap ($1.00; 8 × $1.00 = $8 cap in total, estimate ≤ $2.40), sequential, from a clean
`main` at the merged PR C commit:

```bash
for q in evals/research_v0/questions/R*.txt; do
  .venv-verify/bin/python scripts/argus.py research --question-file "$q" --key-file "$KEY_FILE" --yes
done
```

Each job id is recorded next to its question in the results (`docs/reviews/RESEARCH_EVAL_V0.md`, written after the
run). A job that stops (BLOCKED, crash) is resumed once with `argus resume <job>`; it is not restarted as a new job.
