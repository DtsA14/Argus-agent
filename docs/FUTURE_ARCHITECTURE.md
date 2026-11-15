# Argus — Pending Architecture Specification

> **Status: draft spec for a future project (Atha, 2026-10-15).** These are proposed decisions from discussion with
> GPT, **not** a description of what the repository implements. **The status of every ADR and milestone against the
> code is kept in one place: [`docs/Reconciliation.md`](Reconciliation.md)** (status updated 2026-11-11, direction 2026-11-15; M3 and the M6 MVP
> done, including a first repository outside Argus; M5, M9 (staging only) and ADR-002/004/005/006/007 partial, for code tasks; M4, M7, M8,
> ADR-001/003 and the capability packs not started). No code from this file without a reality check and a reviewed plan.
>
> **Direction (2026-11-15, Atha): "a specialist in its properties, a generalist on its surface."** Argus's strength is
> **"an agent you can leave alone: its work is proven, its cost is locked."** The specialism is the property, not a domain:
> every job ends with evidence that can be checked, inside a hard budget, with no human or Claude in the middle except
> approvals that are meant to be there. The surface is one door, the chat (`router/chat.py`), and capabilities are added to
> it one at a time on the same core, each only when it can carry a gate or a confirmation card. The code job is where the
> property is proven first; research is one surface capability, not a pillar.
>
> This replaces "general-purpose agent, starting with deep research" (2026-11-03) and "production coding agent"
> (2026-10-28). The hierarchical pipeline (job → planner → research/code/deploy tasks) is still not justified by evidence:
> three probes (`pilots/from_research_v0`, `research_need_v0`, `chain_probe_v0`) did not need a planner; M4, M7, M8, the
> capability packs and production stay deferred until evidence asks for them. The earlier direction notes are kept in
> `Reconciliation.md` section 7 and in [`reviews/RECONCILIATION_2026-11-11.md`](reviews/RECONCILIATION_2026-11-11.md).
> Section 1 below was rewritten for this direction (the original is in git history, `7d2532d:docs/FUTURE_ARCHITECTURE.md`);
> sections 2 to 9 are unchanged and are read through it: an ADR or milestone is built when it makes work more proven,
> cost more locked, or Argus easier to leave alone.
>
> The one-time instructions for Claude's first review ("Instructions for Claude" and "Expected response", sections 0
> and 10 of the original) were carried out by [`reviews/M6_GAP_ANALYSIS.md`](reviews/M6_GAP_ANALYSIS.md),
> [`reviews/M6_PLAN.md`](reviews/M6_PLAN.md) and the reconciliation reports, and were removed on 2026-10-22; the
> original text is in git history (`bf5416d:docs/FUTURE_ARCHITECTURE.md`). "M4 slice 1" in older review files meant the
> single general-task agent, **not** this file's M4 (parallel multi-agent).

## 1. Vision and scope

Argus is an agent you can leave alone: its work is proven and its cost is locked. It is a specialist in those properties and
a generalist on its surface.

- **Core (the specialism).** Proven work: acceptance criteria fixed before execution, deterministic gates where they exist,
  verdicts with evidence, and nothing counted as done because a model said so. Locked cost: a reservation before every
  request, a ledger entry for every attempt, a cap per job, crash-resume that never buys the same result twice. Left alone:
  from request to result without a human or another model in the middle, except approvals that are deliberate.
- **Surface (the generalism).** One door, the chat. A capability (code, research, and later others such as everyday tasks,
  images, video, games, deployment) is added one at a time, and only when it can carry the core: a gate that can fail it, or
  a confirmation card bound to the exact action. Actions with an effect outside (sending a message, a production deploy, a
  transaction, deleting data) always need a human approval.

Execution strategy: hybrid local + API + cloud. Tool discovery is semi-autonomous: Argus may find tools, read docs,
inspect schemas, and test in a sandbox, but discovery does not grant trust or permissions. Every tool must be
registered and pass policy checks before production execution.

Near-term priority: make the code job something that can be left alone (a verdict that cannot be forged, `argus apply`,
approval on the final patch), measured as the share of issues that reach staging without Claude stepping in. Then widen the
surface from the chat, one capability at a time. Open work is in `PENDING.md`; status is in `Reconciliation.md`.

## 2. Agreed architecture decisions

### ADR-001 — Capability Registry and Policy Enforcement

Every built-in or discovered tool must be registered and pass policy checks before execution. A discovered tool is not
automatically trusted. Registry metadata should include stable ID/version, capability/provider, input/output schemas,
requirements, cost model, permissions, filesystem/network scope, time/resource limits, verification strategy, trust
status, and provenance. Policy uncertainty fails closed.

### ADR-002 — Typed Workflow with Dynamic Planning

The planner can construct/revise plans dynamically, but execution uses a typed, validated workflow with explicit
dependencies and legal state transitions. Each task should include `task_id`, `workflow_id`, `project_id`,
`capability_id`, tool/version, typed input and expected output, dependencies, budget, permissions, timeout/retry
policy, idempotency identity, state, attempts, timestamps, and errors. Independent tasks may run in parallel under
concurrency, budget, and policy limits. Invalid plans do not execute.

### ADR-003 — Layered Memory

Separate:
- **Execution state:** task/workflow state, checkpoints, attempts, outputs, recovery metadata.
- **Knowledge memory:** tool docs, provider constraints, tested procedures, failure notes.
- **Project memory:** requirements, decisions, project structure, approved preferences, relevant context.

SQLite is acceptable for local MVP state. Keep storage interfaces evolvable. Entries need IDs, versions, timestamps,
provenance, and retention rules. Memory must not grant permissions or directly mutate execution state.

### ADR-004 — Durable Execution, Idempotency, Budget Enforcement

Persist task state/checkpoints; use stable task identity based on relevant inputs, tool versions, config, and
dependency outputs; reuse only valid matching results; reserve budget before execution and reconcile actual costs;
bound retries by error type and policy. If a request may have reached a paid provider but the response is lost,
record `unknown_after_crash` and reconcile before retrying. Use provider idempotency keys when supported. Do not
promise universal exactly-once execution; use deduplication, reconciliation, and provider-specific support.

### ADR-005 — Artifact Store and Project Workspace

Separate artifact bytes from metadata. MVP can use a restricted local filesystem plus SQLite metadata behind storage
interfaces that can later support object storage. Metadata: `artifact_id`, `project_id`, `task_id`, version,
parent/source artifact, URI, SHA-256, media type, size, created time, provenance, validation status, retention policy.
New output must not silently overwrite old versions. Enforce workspace path jail and allowed write scope. Keep large
binaries out of SQLite. Publishing/sharing requires authorization.

### ADR-006 — Quality Gates and Acceptance Criteria

Define acceptance criteria before execution. The planner may propose missing criteria but must label assumptions and
must not silently lower the bar. Prefer deterministic code checks; use model judgment for subjective criteria.
Software: build/tests/static checks; images: file validity/dimensions/prompt criteria; video:
duration/resolution/encoding/audio/sequence; games: build/startup/crash/smoke tests. Failed mandatory gates mean task
is not complete; return evidence.

### ADR-007 — Security, Trust Boundaries, Policy-Based Approval

Treat discovered tools, external docs, project files, and model output as untrusted. Apply least privilege. Isolate
code in sandbox with filesystem, resource, and network restrictions. Keep secrets out of prompts and ordinary logs;
expose only to authorized processes. Approval is required for sensitive actions not already explicitly authorized and
must bind to a specific action/parameter scope. Changed parameters require re-evaluation. Unclear policy/approval
means deny.

Policy decision fields: decision (`allow`, `deny`, `require_approval`), principal, action, resource, scope,
policy_version, reason, optional approval_id, timestamp, audit correlation ID. Example risk levels: low-risk permitted
reads/tests can run automatically; dependency installs/new tools require sandbox and policy checks; external data
transfer/publication may require approval; production changes and attempts to bypass controls are denied by default
except through separately authorized/audited paths. Approval does not replace sandboxing.

## 3. Proposed logical architecture

1. Task intake: goal, constraints, budget, deadline, acceptance criteria.
2. Orchestrator: workflow lifecycle, dependencies, cancellation, state transitions.
3. Dynamic planner: turns goals into typed workflows and proposes bounded revisions.
4. Workflow validator: schemas, dependencies/cycles, budget, permission, acceptance checks.
5. Capability registry: tools, versions, schemas, requirements, costs, trust, verification.
6. Policy engine + approval service: authorization and least privilege.
7. Execution adapters: local processes, sandbox tools, model APIs, MCP, cloud jobs.
8. Durable state/memory: execution, knowledge, project memory.
9. Artifact manager: bytes, metadata, versions, checksums, provenance.
10. Evaluator: deterministic checks plus model-based evaluation where needed.
11. Observability/budget ledger: calls, cost, latency, retries, decisions, failures.

These are logical boundaries, not necessarily separate services. Prefer a modular monolith until evidence justifies
distribution. Treat a capability such as `image.generate` as distinct from any one provider/model implementation.

## 4. Workflow and state-machine expectations

Claude should inspect existing code and propose concrete state machines. At minimum distinguish `pending`, `ready`,
`running`, `waiting_for_approval`, `succeeded`, `failed`, `cancelled`, and `unknown_after_crash`. Only the orchestrator
changes authoritative state.

Execution flow:
1. Parse goal and constraints.
2. Define/propose acceptance criteria.
3. Generate typed plan.
4. Validate plan and reserve budget.
5. Resolve registered capabilities and versions.
6. Check policy; request approval when required.
7. Execute ready tasks within concurrency/budget limits.
8. Persist outputs and checkpoints.
9. Run quality gates and attach evidence.
10. Create a bounded revision plan if a gate fails.
11. Complete only if mandatory gates pass; otherwise return blocked/failed with evidence.

## 5. M3–M9 roadmap proposal

- **M3:** reliable evaluation, evidence grounding, malformed-output handling, calibration.
- **M4:** parallel multi-agent scheduling with dependencies and bounded resources.
- **M5:** observability/benchmark; compare single-agent and multi-agent on quality, success, latency, cost per
  successful task, recovery, and human intervention.
- **M6:** repository-to-PR agent: issue/requirement → repo analysis → plan → code changes → sandbox tests → bounded
  recovery → reviewable diff/PR proposal. No auto-merge/deploy by default.
- **M7:** formal capability registry, policy enforcement, MCP/tool adapters where appropriate.
- **M8:** tool discovery, documentation/schema inspection, sandbox validation, procedural memory, revalidation of
  stale procedures.
- **M9:** controlled deployment: staging, health checks, rollback, then production only under explicit
  policy/authorization.
- **Later:** image, video/audio, game creation capability packs. Prioritize by measured value/provider readiness, not
  all at once.

## 6. M6 MVP acceptance criteria

- Accept a scoped issue and repository target.
- Produce a typed plan and explicit acceptance criteria.
- Restrict reads/writes to authorized workspace.
- Run code/tests in isolation.
- Enforce per-task and per-run cost ceilings.
- Persist state and resume after controlled interruption.
- Avoid duplicate paid operations when safely reconcilable/deduplicable.
- Preserve artifacts, diffs, logs, provenance.
- Reject unauthorized tool calls and out-of-scope filesystem/network access.
- Report pass/fail per criterion with evidence.
- Produce reviewable diff/PR proposal, without automatic merge/deploy by default.
- Include deterministic tests for success, tool failure, timeout, crash recovery, budget exhaustion, denied
  permission, malformed model output, and failed quality gate.

Set numeric thresholds after baseline measurements; do not invent unsupported targets.

## 7. Data-model topics

Inspect existing schemas first and avoid duplicate sources of truth. Propose tables or equivalent persisted structures
as needed for projects, workflows, tasks, task_dependencies, capability_registry, tool_versions, policy_decisions,
approvals, budget_reservations/cost ledger, artifacts, memory, evaluation_runs/findings, and audit_events. Specify
keys, foreign keys, unique constraints, indexes, lifecycle, retention, transactions, and migrations. Do not add every
table if a smaller MVP model suffices.

## 8. Failure modes

Explicitly design detection, state transition, recovery/termination, audit evidence, and tests for:
- Crash before/after external request submission
- Provider timeout/rate limit and ambiguous paid-call result
- Budget conflict/overrun
- Invalid/cyclic workflow
- Tool schema/version change
- Malicious tool docs, prompt injection in files/web/tool output
- Sandbox escape and unauthorized network access
- Missing/corrupt artifact
- Stale memory/procedure
- Evaluator disagreement/malformed verdict
- Retry loops/planner oscillation
- Revoked approval or changed action parameters
- Concurrent writes to project files

## 9. Observability and evaluation

Measure task success against acceptance criteria, evaluator false-pass/false-reject, cost per successful task, budget
violations, latency, recovery after injected failures, duplicate external calls/artifacts, human
intervention/approval rate, policy denials, and single-agent vs multi-agent outcomes. An LLM claiming success is not
proof.
