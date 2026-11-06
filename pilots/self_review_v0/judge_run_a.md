# Judge j1 of job j20261106_200000_sr0a

Advisory only: this verdict changes nothing in the job (docs/reviews/SPEC_JUDGE.md).

**Status**: JUDGED
**Verdict**: PASS
**Model**: openrouter:z-ai/glm-5.3 (pinned to baidu/fp8)
**Cost**: $0.0255 of a $0.1000 cap

## Summary

Implements R1-R4 as specified: a 429 waits rate_limit_delay_s doubling with jitter, capped at rate_limit_max_delay_s, with Retry-After winning and capped too; other transient errors keep base_delay unchanged. rate_limit_attempts (4) applies when the last error was 429, the loop is bounded by max(attempts, rate_limit_attempts) so no unbounded retry. Gateway 429s (paid and free) charge 0 tokens/USD with delivery and http_status preserved and the reservation untouched; direct providers stay worst-case. Settings are validated in __init__ (ConfigError before anything is sent) and config.yaml gets the approved 30/120/4. The new G1-G8 tests pin the real behavior (bounds, caps, attempt counts, charging, event pairing, validation) and would kill every mutant listed in the spec; existing tests are updated mechanically (3 to 4 attempts, zeroed delays in helpers) without weakening any invariant. R4 items (event order, per-attempt reservation checks, non-transient no-retry) are untouched.

## Findings

- `tests/test_rate_limit_retry.py::test_a_gateway_rate_limit_is_not_charged_so_four_attempts_fit_a_one_attempt_cap`: Sizes the reservation through the private caller._worst_usd(100, caller.max_output); a public worst-case helper would keep the test from breaking on internal renames.
- `harness/llm.py`: Edge case to be aware of (spec-approved): a persistent direct-provider 429 can now make up to rate_limit_attempts (4) worst-case charges per call instead of 3 (R2 applies to all providers, G6 keeps direct charging). A reservation sized for 3 worst cases refuses the 4th attempt before sending, so overspend stays contained.

## Read

- changes.patch: sha256 01161f2c15794bef58114c982ef446bbcb0f76bb43989c8c7592010129c5245a
- tests.md: sha256 ec89e00e8bbff78b419f9d2622c157e59586cc7eb16f2d1758a17bb5e62d88a1
- claims.md: sha256 30b3777a569feac9616487aaba40be01f2e5fd1bea3842c74d7e8c1e0c0cfba9
- draft: sha256 cb04c980309e28d15dfa206f7c621b4b66ae6d85d1fee8ecb2fd3c5d8f546134
