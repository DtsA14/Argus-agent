Ledger issue 023: GET /scoreboard/models?kind= limits it to one kind of job

Extend `GET /scoreboard/models` (ledger issues 021 and 022, already in the code) with an optional query parameter `kind`. Without it the answer does not change.

With `kind=code`, `kind=research` or `kind=issue`, only the calls of the jobs of that kind count, using the kind rule the scoreboard already has (`job.json`'s `kind` when it is exactly that string). `models` and `total` are computed over those jobs only; a model with no call among them is not listed. A job whose kind is any other value belongs to no filter, only to the unfiltered answer.

Any other value of `kind`, including an empty one, answers HTTP 400 with `{"detail": "unknown kind: <value>"}` and changes nothing. The login and `Host` rules are the same as for the endpoint without the parameter.

Example: job A (kind `code`) has one call on model M costing 100 nano; job B (kind `issue`) has one call on model M costing 40 and one on model N costing 7. `?kind=code` answers one entry (M, 1 call, 100) and total 100; `?kind=issue` answers M (1, 40) and N (1, 7) and total 47; no parameter answers M (2, 140), N (1, 7), total 147.

Add tests for each case above, for the 400, and that the three filtered totals plus the `other` jobs add up to the unfiltered total. Update the README section.
