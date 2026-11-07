# Judge j1 of job j20261106_200000_sr0b

Advisory only: this verdict changes nothing in the job (docs/reviews/SPEC_JUDGE.md).

**Status**: JUDGED
**Verdict**: PASS
**Model**: openrouter:z-ai/glm-5.3 (pinned to baidu/fp8)
**Cost**: $0.0314 of a $0.1000 cap

## Summary

Faithful R1-R4. A 429 waits rate_limit_delay_s*2^(n-1)*(0.5+rand) capped at rate_limit_max_delay_s; Retry-After wins and is capped too; other transients keep base_delay. A 429 gets rate_limit_attempts per the latest error, loop bounded by max(attempts, rate_limit_attempts), so it terminates; 429,429,500 stops at `attempts`. Gateway 429s (paid and free) are charged none with the reservation untouched; direct providers and non-429 gateway errors stay worst-case. Ledger order, reservation checks, non-transient raises, memo/checkpoint untouched. Bad settings raise ConfigError before anything is sent. New tests genuinely cover G1-G8 and by inspection would catch every listed mutant. Existing-test updates (3->4 attempts, 6->8 refusals, zeroed delays, budget-arm key deletion following the prompt_cache precedent) track the behaviour change, not weaken tests. verification/rate_limit_mutants.py is absent, matching the draft's scope.

## Findings

- `tests/test_gateway.py::test_a_rate_limit_is_retried_on_the_same_model_only_and_never_by_the_sdk`: Every other helper in this patch zeroes rate_limit_delay_s/rate_limit_max_delay_s, but this file's config()/caller() were not touched. Unless they already inject a fake sleep, this test now really sleeps three 429 waits (~105-255 s) per run - still correct, just slow, and at risk under any pytest timeout.

## Read

- changes.patch: sha256 01161f2c15794bef58114c982ef446bbcb0f76bb43989c8c7592010129c5245a
- tests.md: sha256 ec89e00e8bbff78b419f9d2622c157e59586cc7eb16f2d1758a17bb5e62d88a1
- claims.md: sha256 30b3777a569feac9616487aaba40be01f2e5fd1bea3842c74d7e8c1e0c0cfba9
- draft: sha256 cb04c980309e28d15dfa206f7c621b4b66ae6d85d1fee8ecb2fd3c5d8f546134
