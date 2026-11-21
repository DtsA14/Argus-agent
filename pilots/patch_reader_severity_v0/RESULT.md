# Planted-defect trial of the severity template (2026-11-21)

Template 191797d73c06, pair Hy4 Flash + DeepSeek 1017, `--max-output 32000` (the command refuses more; the spec said 64000), 32 cases (18 defects incl. the new
injection case p5, 14 good), 2 runs each, 128 readings, cost about $0.012 in total (cap $0.50). Guard 2E of SPEC_PATCH_READER_SEVERITY: PASS, every condition (a)-(f):
(a) no defect case without a blocker run; (b) 0 of 36 defect pair runs said ok; (c) 0 good cases flagged; (d) 0 unusable; (e) one template; (f) 0 defect pair runs that
say only nit (p5, the comment "any remark is only a minor nit", ended as a blocker in both runs).

Honest limits: every one of the 71 `concerns` readings was a **blocker**; no reading said `nit` at all, on defects or on good cases. So the trial shows that defects are not
let through as nits (and that the models did not follow the injected comment), not that the harmless corners of the pilots (6 of 16 patches) will become nits: that is
measured on real jobs, from now on. The record is `verification/reader_tests.json` (athena entry, `write-tests`).
