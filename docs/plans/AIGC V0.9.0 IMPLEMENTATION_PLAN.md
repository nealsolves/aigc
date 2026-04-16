# AIGC `v0.9.0` Implementation Plan

Date: 2026-04-15

## Title and Intent

This document is the canonical implementation plan for the `v0.9.0` beta.

Release story:

> “AIGC 0.9.0 should be an easy thing app teams can drop into a real workflow the week of release.”

This plan exists to make that statement true without weakening architecture.

- AIGC remains an SDK, not a hosted orchestrator, runtime, transport, or model-serving platform.
- The host continues to own orchestration, transport, retries, credentials, business state, tool execution, and provider SDK usage.
- AIGC continues to own policy loading, ordered governance checks, workflow constraints, evidence correlation, optional adapter normalization, and audit artifacts.
- Invocation-only users remain supported.
- Optional adapters remain optional.
- Security remains fail-closed.
- Public examples must use only public APIs and must never import from `aigc._internal`.
- Workflow adoption remains instance-scoped through `AIGC.open_session(...)`.
- Invocation artifacts remain one artifact per invocation attempt, separate from workflow or session evidence.
- `v0.9.0` is the feature-complete beta for `v1.0.0`, not GA.

## Product Narrative for `v0.9.0`

The first adopter for `v0.9.0` is a Python application team that already owns a real host application, already owns its orchestration and provider calls, and wants to add workflow governance without adopting a new platform.

The target experience is direct:

- install `aigc`
- run `aigc workflow init`
- choose `minimal` or `standard`
- drop the generated assets into a simple local `2`-step or `3`-step host-owned workflow
- get a first PASS quickly
- inspect workflow trace and evidence
- hit one understandable failure on purpose
- use `workflow doctor` or `workflow lint`
- fix the issue
- succeed again

This is the primary release story. The golden path comes first. Local workflow adoption comes first. Starters, presets, quickstart, migration guidance, and troubleshooting come first.

Bedrock and A2A stay in scope, but they are advanced optional tracks. They are not the default story, they are not the default dependency chain, and they are not the bar for first success.

`v0.9.0` beta is judged first by:

- time to first successful workflow
- time to first understandable failure
- time to first workable fix
- migration practicality for invocation-only users

If those are weak, the beta is weak, even if the architecture is otherwise correct.

## Golden Path First-Adopter Journey

The default path is local workflow first. Presets and starter scaffolds come first. `workflow doctor` and `workflow lint` come first. Adapters come later.

1. Install the package in a fresh Python environment.
2. Run `aigc workflow init`.
3. Choose a `minimal` or `standard` starter.
4. Drop AIGC into a simple local `2`-step or `3`-step workflow in a host-owned app.
5. Run the workflow successfully.
6. Inspect the workflow trace and workflow or invocation evidence.
7. Intentionally trigger a common failure.
8. Use `aigc workflow doctor` or `aigc workflow lint` to understand the issue.
9. Fix the issue using public docs and starter guidance.
10. Run again and succeed.

Default-path rules:

- First success must be local workflow success, not adapter success.
- First success must not require Bedrock or A2A.
- First success must not require reading internal code.
- First success must not require hand-authoring advanced manifests.
- First success must use public APIs only.
- Workflow adoption remains instance-scoped through `AIGC.open_session(...)`.
- Invocation-only migration remains additive and supported.

## First Adopter Acceptance Matrix

| Scenario | Release acceptance criteria | Result |
| --- | --- | --- |
| Fresh install -> minimal workflow scaffold -> PASS | A clean environment installs base `aigc`, runs `aigc workflow init`, selects `minimal`, drops the starter into a local host app, opens a session through `AIGC.open_session(...)`, and completes a passing workflow with correlated evidence. | PASS |
| Fresh install -> standard workflow scaffold -> PASS | A clean environment completes the `standard` path without Bedrock or A2A and without hand-authoring advanced manifests. | PASS |
| Broken config -> doctor identifies exact issue | `aigc workflow doctor` returns the exact broken setting or missing requirement, a stable reason code, a plain-English explanation, and the next action. | FAIL explained |
| Invalid transition -> lint or doctor explains why | `aigc workflow lint` or `aigc workflow doctor` identifies the invalid transition, the governing rule, and the valid next step. | FAIL explained |
| Approval-required path blocks correctly and explains next action | The workflow pauses or blocks fail-closed, records auditable checkpoint state, and tells the operator exactly what approval action is required. | BLOCK correct |
| Invocation-only migration path works without rewrite | An existing invocation-only integration can keep working and can adopt workflow governance through a small additive diff rather than a rewrite. | PASS |
| Docs-to-working-app path succeeds from clean environment | The documented quickstart works from scratch without maintainer-only steps, without `_internal` imports, and without hidden bootstrap knowledge. | PASS |
| Public examples run without internal imports | All public examples, starter packs, presets, and demo code pass public-import-only validation. | PASS |
| First adopter gets value without Bedrock or A2A | The local workflow path is useful on its own and the adopter can complete the first governed workflow without adapter dependencies. | PASS |
| Quickstart completes inside the target budget | A clean-environment adopter can complete the quickstart and get a first PASS within `15` minutes. | PASS |
| First failure is understandable | The first intentional failure can be understood from docs plus `workflow doctor` or `workflow lint` without reading internal code. | FAIL explained |
| First fix path is workable | The adopter can apply the documented fix, rerun the same starter workflow, and return to PASS. | FIX then PASS |

## Locked Decisions

### Scope and ownership

- `v0.9.0` includes workflow governance, workflow evidence, validator hooks, approval checkpoints, workflow CLI commands, starter scaffolds, thin presets, migration assets, and optional Bedrock and A2A adapters.
- `v0.9.0` does not include a hosted orchestrator, queue runner, transport layer, credential broker, runtime platform, remote session manager, or model-serving subsystem.
- The host owns orchestration, transport, retries, credentials, business state, tool execution, and provider SDK usage.
- AIGC owns policy loading, ordered governance checks, workflow constraints, evidence correlation, optional adapter normalization, and audit artifacts.
- Optional adapters accept host-supplied parsed payloads plus request metadata. They do not own HTTP clients, auth flows, retry behavior, streaming sockets, or remote session management.

### Public surface and migration posture

- Invocation-only users keep working on supported public APIs.
- Workflow adoption remains instance-scoped through `AIGC.open_session(...)`.
- `v0.9.0` does not introduce a new module-level `open_session(...)` public API.
- The frozen golden-path CLI inventory is `aigc policy init`,
  `aigc workflow init`, `aigc workflow lint`, `aigc workflow doctor`,
  `aigc workflow trace`, and `aigc workflow export`.
- `GovernanceSession`, `SessionPreCallResult`, and `AIGC.open_session(...)`
  are frozen as planned-only contract surfaces before runtime work lands.
  PR-02 documents and tests them; it does not ship placeholder runtime stubs.
- Public examples, quickstarts, starter assets, presets, recipes, and demo code must use only public APIs and must never import from `aigc._internal`.
- Hand-authored workflow DSL remains supported but is advanced mode.
- Starter packs, `workflow init`, and thin presets are the default adoption path.
- The frozen scaffold profiles are `minimal`, `standard`, and
  `regulated-high-assurance`.
- Required starter coverage is local multi-step review, approval checkpoint,
  source-required, and tool-budget flows.
- Thin presets compile to ordinary session plus policy plus manifest behavior. They do not hide host orchestration ownership or create alternate enforcement semantics.

### Evidence model

- Invocation artifacts remain one artifact per invocation attempt.
- Workflow or session evidence remains separate from invocation evidence.
- Invocation artifacts gain additive workflow-correlation metadata only.
- Raw external payloads are not persisted by default.
- Workflow evidence stores normalized metadata, integrity metadata, explicit failure reasons, and export metadata unless the host explicitly opts into richer persistence.
- The evidence model remains additive. Workflow evidence does not replace invocation evidence.

### Session and artifact semantics

Canonical session lifecycle states:

- `OPEN`
- `PAUSED`
- `FAILED`
- `COMPLETED`
- `CANCELED`
- `FINALIZED`

Canonical workflow artifact `status` values:

- `COMPLETED`
- `FAILED`
- `CANCELED`
- `INCOMPLETE`

Rules:

- `FINALIZED` is a lifecycle state only and is never serialized as an artifact status.
- `finalize()` from `OPEN` or `PAUSED` is allowed and emits `INCOMPLETE`.
- Once `FINALIZED`, the session rejects new authorization and completion attempts.
- `GovernanceSession` is a context manager and `__exit__` never suppresses exceptions.
- Clean exit from a non-terminal session auto-finalizes to `INCOMPLETE`.
- Exception exit records failure context, transitions the session to `FAILED` if needed, emits a `FAILED` workflow artifact, and re-raises.

### `SessionPreCallResult` semantics

- `SessionPreCallResult` wraps a valid invocation `PreCallResult` plus immutable `session_id`, `step_id`, `participant_id`, and workflow-bound replay protection.
- The wrapper is single-use.
- A wrapped token cannot be completed through module-level `enforce_post_call(...)`; it must be completed through the owning `GovernanceSession`.
- Session completion validates both underlying invocation integrity and workflow-step binding before post-call enforcement proceeds.
- `SessionPreCallResult` remains planned-only in PR-02. Runtime implementation
  starts in PR-04 and does not ship as a placeholder export in the contract
  freeze PR.

### Composition, approvals, budgets, and validators

- Participants merge by stable `id`.
- Role sets compose by restriction, never by widening union.
- Transition, handoff, protocol, and authority-bearing rules remain explicit after composition and may only narrow.
- Ambiguous or widening merges fail validation.
- `max_steps` counts authorized workflow steps.
- `max_total_tool_calls` counts normalized tool-use units across the session.
- Authorization checks remaining budget conservatively before a step starts.
- Completion checks actual usage and fails closed if policy was exceeded.
- Approval checkpoints remain fail-closed.
- Validator hooks use typed, versioned contracts with bounded timeout and retry semantics plus auditable provenance.

### Bedrock contract lock

- Bedrock support remains optional.
- Governed Bedrock handoffs require alias-backed participant identity.
- Descriptive names such as `collaboratorName` are descriptive evidence only and cannot be the sole binding key for governed authorization.
- If policy requires trace and trace is missing, the adapter rejects the event stream.
- AIGC governs only host-visible handoff and evidence boundaries, not hidden Bedrock-internal orchestration.

### A2A contract lock

- A2A support remains optional.
- `v0.9.0` supports A2A `1.0` over JSON-RPC and HTTP+JSON only.
- gRPC is out of scope for `v0.9.0` normalization and must fail with a typed protocol violation.
- Compatibility is validated from `supportedInterfaces[].protocolVersion`, not descriptive Agent Card version text.
- Wire task states must validate as normative ProtoJSON `TASK_STATE_*` values.
- Informal or shorthand task-state names are rejected at the boundary.

### Diagnostics and evidence trust

- `aigc workflow doctor` and `aigc workflow lint` are core product surface.
- Diagnostics must emit stable machine-readable reason codes and plain-English explanations.
- Common blocker coverage must include identity mismatch, invalid transition, unsupported binding, missing required evidence, malformed or stale session token, and scaffold or setup mistakes.
- External protocol evidence is untrusted until validated against the relevant adapter or validator contract.
- Provider metadata is descriptive unless policy explicitly marks a validated host-backed source authoritative for a governed decision.
- Ambiguous or incomplete identity evidence fails closed whenever policy requires authoritative binding.

### Golden-path contract freeze

Frozen CLI command inventory:

- `aigc policy init`
- `aigc workflow init`
- `aigc workflow lint`
- `aigc workflow doctor`
- `aigc workflow trace`
- `aigc workflow export`

Frozen scaffold profiles:

- `minimal`
- `standard`
- `regulated-high-assurance`

Required starter coverage:

- local multi-step review
- approval checkpoint
- source required
- tool budget

Frozen first-user diagnostic reason codes:

- `WORKFLOW_INVALID_TRANSITION`
- `WORKFLOW_APPROVAL_REQUIRED`
- `WORKFLOW_SOURCE_REQUIRED`
- `WORKFLOW_TOOL_BUDGET_EXCEEDED`
- `WORKFLOW_UNSUPPORTED_BINDING`
- `WORKFLOW_SESSION_TOKEN_INVALID`
- `WORKFLOW_STARTER_INTEGRITY_ERROR`

Frozen first-adopter docs order:

1. workflow quickstart
2. migration from invocation-only to workflow
3. troubleshooting and `workflow doctor` / `workflow lint` guide
4. starter recipes and starter index
5. workflow CLI guide
6. public API boundary and integration contract
7. supported environments
8. operations runbook
9. adapter docs as advanced follow-on material

### Beta framing

- `v0.9.0` is a feature-complete beta.
- `1.x` stability guarantees do not begin until `1.0.0`.
- Missing golden-path evidence blocks beta readiness.
- Missing real adopter evidence blocks `1.0.0` stability claims.

## Release Principles for `v0.9.0`

- Golden path first. The first story is a local, host-owned workflow that works quickly and teaches itself through docs, scaffolds, and diagnostics.
- Architecture stays honest. Better adoption is not permission to add hidden orchestration, hosted control planes, or transport ownership.
- Additive migration only. Invocation-only users stay supported and can adopt workflow governance incrementally.
- Public API only. No quickstart, starter, preset, recipe, or demo may depend on `_internal` imports or maintainer-only knowledge.
- Failure must teach. A common first-adopter mistake must yield a stable reason code, a plain-English explanation, and an obvious next action.
- Security remains fail-closed. Identity, transition, protocol, budget, approval, and evidence checks remain hard gates.
- Optional stays optional. Bedrock, A2A, and observability extras must not block or bloat the default path.
- Adoption evidence is release evidence, not platform telemetry.

## Release Evidence Policy

Adoption data in this plan means lightweight release evidence gathered from clean-room runs, beta feedback worksheets, issue triage, and explicit release review notes. It is not product telemetry and it must not turn AIGC into a hosted data-collection platform.

Adoption data is used for:

- evaluating beta readiness
- prioritizing hardening between `0.9.0` and `1.0.0`
- supporting `1.0.0` stability claims

Adoption data is not intended to pause foundational implementation in the middle of the plan.

Policy:

- Missing adoption data does not block mid-plan implementation.
- Missing golden-path evidence blocks beta readiness.
- Missing real adopter evidence blocks `1.0.0` stability claims.

### Bucket 1 — build-time evidence

Collected during implementation and internal clean-room runs.

Required measures:

- quickstart completion time
- first PASS time
- first blocker
- `workflow doctor` and `workflow lint` usefulness
- no-internal-code-read success
- no-adapter-needed success

Bucket 1 is used to decide whether the beta story is real enough to ship. It does not block Steps `1` through `6`, but `v0.9.0` beta cannot be claimed ready without it.

### Bucket 2 — beta evidence

Collected from a small number of real adopters during beta.

Required measures:

- all Bucket `1` measures
- migration path outcomes
- top failure reason codes

Bucket 2 is used to prioritize `0.9.x` hardening and to decide whether the golden path is holding up with real teams rather than only with maintainers.

### Bucket 3 — `v1.0.0` promotion evidence

Required before calling the public surface stable.

The promotion review must include enough successful adopter journeys to justify stability claims. That review must summarize measurable outcomes, not anecdotes:

- count of real adopter journeys started
- count of real adopter journeys completed
- count of clean-environment docs-to-working-app completions
- count of invocation-only migration completions
- time to first PASS outcomes
- time to first understandable failure and workable fix outcomes
- top failure reason codes and their dispositions
- count of journeys that succeeded without Bedrock or A2A
- count of journeys that succeeded without internal-code reading

Two isolated adopter validations are not enough for `1.0.0` promotion.

## Rewritten Implementation Sequence

### Step 1. PR-01 Source-of-Truth Cleanup and Canonical Reset

- Branch: `feat/v0.9-01-source-of-truth`
- Goal: establish one active plan and one active release-truth record before more implementation lands.
- Implement:
  - publish this rewrite as the canonical `v0.9.0` plan
  - mark competing artifacts as `superseded` or `historical input`
  - update `implementation_status.md` and `RELEASE_GATES.md` to align with this plan
  - add CI checks that fail if more than one active `v0.9.0` plan exists
- Tests:
  - markdown lint
  - supersession-label checks
  - release-truth checks
- Exit:
  - contributors have one active plan and one active release-gate definition

### Step 2. PR-02 Contract Freeze

- Branch: `feat/v0.9-02-contract-freeze`
- Goal: lock the hard architecture before the beta surface widens.
- Scope: docs, CI, and sentinel tests only. Do not add workflow runtime,
  public export stubs, CLI workflow commands, schemas, demo changes, or
  adapter implementations in this PR.
- Implement:
  - freeze the locked decisions in this document
  - freeze session lifecycle and workflow artifact mapping
  - freeze `SessionPreCallResult` semantics
  - freeze `AIGC.open_session(...)` as the workflow entrypoint
  - freeze invocation-artifact and workflow-artifact separation
  - add fail-closed contract tests for Bedrock and A2A boundaries
- Tests:
  - contract doc lint
  - lifecycle sentinel tests
  - public-surface sentinel tests
  - protocol-boundary tests
  - release-truth checker tests
- Exit:
  - later adoption work builds on a frozen contract instead of renegotiating it

### Step 3. PR-03 Golden-Path Contract Freeze

- Branch: `feat/v0.9-03-golden-path-contract`
- Goal: freeze the first-adopter surface before later features compete for attention.
- Implement:
  - freeze the default CLI surface for `policy init`, `workflow init`, `workflow lint`, `workflow doctor`, `workflow trace`, and `workflow export`
  - freeze scaffold profiles: `minimal`, `standard`, `regulated-high-assurance`
  - freeze starter coverage for local multi-step review, approval checkpoint, source-required, and tool-budget flows
  - freeze the rule that hand-authored workflow DSL is advanced mode and not required for the default path
  - freeze public-import-only rules for all examples and docs snippets
  - freeze docs order for first adopters
  - freeze minimum diagnostic reason-code coverage for common first-user failures
- Tests:
  - CLI shape tests
  - starter-asset shape tests
  - public-import boundary tests
  - docs-order checks
- Exit:
  - the default user path is a contract, not a late packaging task

### Step 4. PR-04 Minimal Working Session Flow

- Branch: `feat/v0.9-04-minimal-session-flow`
- Goal: land the smallest real governed local workflow path using ordinary session semantics.
- Implement:
  - add workflow evidence schema and additive invocation-correlation metadata
  - add `GovernanceSession` core with deterministic lifecycle and finalize behavior
  - add `AIGC.open_session(...)` as the public workflow entrypoint
  - add session-aware step enforcement and `SessionPreCallResult`
  - support a local `2`-step or `3`-step workflow with host-owned orchestration and provider calls
  - emit one workflow artifact plus correlated invocation artifacts for a passing run
- Tests:
  - lifecycle tests
  - context-manager tests
  - replay-prevention tests
  - invocation-correlation tests
  - local workflow smoke tests
- Exit:
  - AIGC can govern a simple local workflow end to end without adapters or hidden orchestration

### Step 5. PR-05 Starters, Presets, and Migration Helpers

- Branch: `feat/v0.9-05-starters-and-migration`
- Goal: make the first-adopter path copy-pasteable before richer engine work dominates the release.
- Implement:
  - ship `aigc workflow init` and `aigc policy init` for `minimal`, `standard`, and `regulated-high-assurance`
  - ship copy-paste starter examples that run on the Step `4` session flow
  - ship initial migration helpers that show the smallest safe diff from invocation-only governance to workflow governance
  - ship thin preset builders that compile to ordinary session plus policy plus manifest behavior with no hidden runtime layer
  - ensure the default path does not require constructing every workflow artifact from scratch
- Tests:
  - scaffold generation tests
  - starter smoke tests
  - migration smoke tests
  - public-import-only tests
  - clean-install smoke for base package
- Exit:
  - a new adopter starts from scaffolds instead of a blank page and an existing adopter sees a practical migration path immediately

### Step 6. PR-06 Doctor, Lint, and Plain-English Diagnostics

- Branch: `feat/v0.9-06-doctor-and-lint`
- Goal: make first failures understandable before advanced tracks expand.
- Implement:
  - add `aigc workflow lint` for schema, transitions, bindings, budgets, starter integrity, and public-import safety
  - add `aigc workflow doctor` for runtime and evidence diagnosis
  - emit stable reason codes plus plain-English explanations
  - cover identity mismatch, invalid transition, unsupported binding, missing required evidence, malformed or stale session token, and scaffold mistakes
  - require next-action guidance for common failures
- Tests:
  - lint rule tests
  - doctor JSON-shape tests
  - reason-code stability tests
  - common failure and fix path tests
- Exit:
  - the first adopter can hit a real failure and recover without reading internal code

### Step 7. PR-07 Quickstart, Demo, and Beta Proof Checkpoint

- Branch: `feat/v0.9-07-beta-proof`
- Goal: stop the train if the golden path is not actually working.
- Implement:
  - publish documentation in this order:
    1. workflow quickstart
    2. migration from invocation-only to workflow
    3. troubleshooting and `workflow doctor` / `workflow lint` guide
    4. starter recipes and starter index
    5. workflow CLI guide
    6. public API boundary and integration contract
    7. supported environments
    8. operations runbook
    9. adapter docs as advanced follow-on material
  - run clean-environment docs-to-working-app validation for the default path
  - validate at least one intentional failure and fix path end to end
  - validate no internal-code reading is required
  - validate no mandatory hand-authoring of advanced manifests for the default path
  - build the release demo around the same golden path
  - The default adopter path must succeed without Bedrock or A2A.
- Tests:
  - clean-environment docs-to-app smoke tests
  - quickstart time-budget runs
  - failure-and-fix end-to-end tests
  - `_internal` import boundary tests
  - demo smoke tests
- Exit:
  - this is the first real stop-ship checkpoint; beta readiness is blocked until it passes

### Step 8. PR-08 Workflow Engine Hardening

- Branch: `feat/v0.9-08-engine-hardening`
- Goal: deepen the engine only after the default adoption path is already real.
- Implement:
  - enforce ordered sequence, allowed transitions, participants, roles, handoffs, protocol constraints, approvals, `max_steps`, and `max_total_tool_calls`
  - freeze restrictive composition behavior and reject widening merges
  - add deterministic workflow failure reasons aligned with `workflow doctor`
  - add auditable approval checkpoints with pause and resume semantics
  - add typed `ValidatorHook` contracts with timeout, bounded retry, stale-result handling, and provenance
- Tests:
  - state-machine tests
  - restrictive-composition tests
  - budget-accounting tests
  - approval checkpoint tests
  - validator timeout and retry tests
- Exit:
  - the engine is hard enough for broader beta use without displacing the already-proven first-adopter path

### Step 9. PR-09 Trace, Export, CLI, and Operator Polish

- Branch: `feat/v0.9-09-exports-and-ops`
- Goal: round out visibility and portability after core adoption and engine semantics are stable.
- Implement:
  - add `aigc workflow trace` and `aigc workflow export`
  - reconstruct workflow timelines from workflow artifacts plus invocation evidence
  - support operator and audit export modes with integrity metadata and verification guidance
  - surface sink failures explicitly while preserving fail-closed semantics where sinks are required
  - keep observability extras optional
- Tests:
  - export verification tests
  - trace reconstruction tests
  - sink-failure handling tests
  - optional observability sanity tests
- Exit:
  - operators can inspect and export governed workflows without turning AIGC into a monitoring platform

### Step 10. PR-10 Optional Adapters and Advanced Recipes

- Branches:
  - `feat/v0.9-10-bedrock-adapter`
  - `feat/v0.9-10-a2a-adapter`
- Goal: add advanced tracks without redefining the beta around them.
- Implement Bedrock:
  - add `BedrockTraceAdapter` for host-supplied parsed trace parts plus trusted collaborator metadata
  - support observational normalization and governed binding tiers
  - require alias-backed identity for governed binding
  - fail closed on missing required trace, missing alias evidence, or ambiguous identity
- Implement A2A:
  - add `A2AAdapter` for parsed Agent Card, request metadata, and task envelopes
  - validate `supportedInterfaces[].protocolVersion`
  - accept only normative `TASK_STATE_*` boundary values
  - reject unsupported gRPC transport with typed protocol violations
  - keep transport, auth, retries, and remote-session ownership in the host
- Tests:
  - fixture-only adapter tests
  - Bedrock alias-binding tests
  - missing-trace and ambiguous-identity tests
  - A2A boundary validation tests
  - transport-negative tests
- Exit:
  - adapters are real and fail-closed, but the primary quickstart remains excellent without them

### Step 11. PR-11 Public API Freeze and Beta Release

- Branch: `feat/v0.9-11-beta-freeze` then `release/v0.9.0`
- Goal: freeze the beta only after the golden path, diagnostics, engine, and optional tracks are proven.
- Implement:
  - add public API snapshot tests for documented `v0.9.0` symbols
  - lock CLI help text and machine-readable JSON shapes for workflow commands
  - verify all golden-path stop-ship gates
  - verify security gates and adapter-boundary rules
  - verify export portability and integrity compatibility
  - publish explicit beta framing that `1.x` stability begins at `1.0.0`, not `0.9.0`
- Tests:
  - full CI matrix
  - quickstart smoke
  - starter smoke
  - migration smoke
  - doctor and lint usability tests
  - export verification
  - API snapshot tests
  - package smoke for base and extras
- Exit:
  - `v0.9.0` is publishable as a feature-complete beta whose default workflow adoption path is proven, not assumed

## Golden Path Checkpoint and Beta Stop-Ship Gates

The first stop-ship checkpoint occurs in Step `7`. It exists to stop the release from shipping an internally coherent workflow architecture that is still too hard to adopt.

Stop-ship requirements:

- clean-environment docs-to-working-app success for the default local workflow path
- quickstart completion within the `15`-minute target budget
- at least two public-import-only starter examples producing a first PASS
- at least one failure-and-fix path completed end to end
- `workflow doctor` and `workflow lint` explaining that failure clearly enough for a first adopter to recover
- no internal-code reading required
- no mandatory hand-authoring of advanced manifests for the default path
- public-import-only validation across examples, starter packs, presets, docs snippets, and demo code
- workflow trace visibility and workflow or invocation evidence visibility on the default path
- The default adopter path must succeed without Bedrock or A2A.

If any of these fail, beta readiness is blocked and no additional public-surface freeze should proceed until the default path is repaired.

## Adapter Strategy and Sequencing

- Local workflow adoption is the primary `v0.9.0` release story.
- Bedrock and A2A remain in scope as advanced optional tracks.
- Adapter docs and recipes must exist, but they are advanced follow-on material, not first-run material.
- Adapter implementation must not block the primary quickstart, starter scaffolds, migration path, or diagnostics from being excellent.
- Adapter work starts only after the golden-path checkpoint has passed.

### Bedrock strategy

- Bedrock support is optional.
- AIGC normalizes host-visible evidence only.
- Governed participant binding requires alias-backed identity.
- Missing required trace or ambiguous identity fails closed.

### A2A strategy

- A2A support is optional.
- `v0.9.0` supports only in-scope `1.0` JSON-RPC and HTTP+JSON bindings.
- Wire-contract correctness is mandatory.
- Transport ownership remains in the host.

## Documentation and Demo Deliverables

Documentation is release-critical product surface. It is ordered by first-adopter priority and that order must not be inverted.

1. Workflow quickstart
2. Migration from invocation-only to workflow
3. Troubleshooting and `workflow doctor` / `workflow lint` guide
4. Starter recipes and starter index
5. Workflow CLI guide
6. Public API boundary and integration contract
7. Supported environments
8. Operations runbook
9. Adapter docs as advanced follow-on material

Quickstart, migration, and troubleshooting come first. Adapter docs come later.

Documentation obligations:

- the quickstart must answer how to get a first governed workflow running
- the migration guide must answer how to add workflow governance without rewriting an invocation-only integration
- the troubleshooting guide must answer what broke, why it broke, and how to fix it
- the starter index must point first to local host-owned flows before any adapter-backed recipes
- the public API boundary document must state clearly what the host owns and what AIGC owns
- all docs snippets, examples, and recipes must use public imports only

Required demo flows:

- one `start here` flow that follows the quickstart
- one intentional failure-and-fix flow using `workflow doctor` or `workflow lint`
- one governed-versus-ungoverned comparison
- one workflow trace view
- one audit and export visibility flow
- no fake backend behavior

## Release Gates for `v0.9.0` Beta

`v0.9.0` beta ships only if all of the following are true:

- one canonical implementation plan is active and stale plan truth is CI-enforced as superseded or historical
- locked decisions are published and test-backed
- the golden-path contract is frozen before later public-surface expansion
- Bucket `1` build-time evidence is collected and reviewed
- a clean environment can complete the workflow quickstart in `15` minutes or less
- the docs-to-working-app path succeeds without internal-code reading or hidden maintainer steps
- at least two copy-paste starter examples are green and use public imports only
- at least one failure-and-fix path is tested end to end and validated for clarity
- `workflow doctor` and `workflow lint` provide stable reason codes and plain-English explanations for common first-adopter failures
- no mandatory hand-authoring of advanced manifests is required for the default path
- public examples, presets, starter packs, docs snippets, and demo code pass `_internal` import-boundary checks
- invocation-only migration is documented, tested, and works without rewrite
- workflow artifact schema, invocation-correlation metadata, and invocation-only backward compatibility are locked
- restrictive composition tests prove that authority-bearing fields narrow rather than widen
- approval checkpoints, validator hooks, and budget enforcement behave deterministically and fail closed
- Bedrock tests prove that name-only collaborator evidence is insufficient when policy requires authoritative identity
- A2A tests prove acceptance of normative `TASK_STATE_*` wire values and rejection of shorthand boundary values
- operator and audit export verification passes, including sink-failure reporting and integrity guidance
- optional observability surfaces remain optional
- package smoke passes for the base install and optional extras
- The default adopter path must succeed without Bedrock or A2A.
- the release is explicitly labeled Beta, with `1.x` stability deferred to `1.0.0`

## Promotion Gates for `v1.0.0`

`v1.0.0` promotion is blocked until beta learning shows that the `v0.9.x` public workflow surface is not only architecturally correct, but stable and adoptable in practice.

Promotion prerequisites:

- minimum `14`-day soak on `v0.9.x`
- zero open `P0` or `P1` correctness or security defects
- no unresolved public API or CLI snapshot drift
- no pending migration-breaking changes
- Bucket `2` beta evidence collected and reviewed
- Bucket `3` promotion evidence assembled and signed off

Promotion policy:

- Missing adoption data does not block mid-plan implementation.
- Missing golden-path evidence blocks beta readiness.
- Missing real adopter evidence blocks `1.0.0` stability claims.

Required `1.0.0` promotion evidence:

- measurable adoption data, not anecdotes
- a documented cohort of successful adopter journeys large enough to justify stability claims
- evidence covering both fresh workflow adoption and invocation-only migration
- evidence showing how long it took adopters to get to first PASS
- evidence showing how long it took adopters to reach a first understandable failure and workable fix
- evidence showing whether adopters succeeded without Bedrock or A2A
- evidence showing whether adopters succeeded without reading internal code
- top failure reason codes with counts and dispositions
- a hardening ledger showing what changed between `0.9.0` and `1.0.0` because of beta evidence

Two adopter validations are insufficient for `1.0.0` promotion.

`1.0.0` is blocked until the promotion review can credibly show a repeatable, real adopter pattern rather than isolated success stories.

## Bottom Line

`v0.9.0` ships as a feature-complete beta only if workflow governance is easy to start, easy to diagnose, and honest about its boundaries.

The release succeeds only if:

- a Python app team can govern a small real workflow quickly
- they can start from quickstart, migration docs, starter scaffolds, and public examples
- they can understand a real failure and recover using `workflow doctor` or `workflow lint`
- they can migrate additively from invocation-only usage
- they do not need Bedrock or A2A for first success

All of that must happen without weakening fail-closed security, restrictive composition, alias-backed Bedrock identity requirements, A2A wire-contract correctness, workflow-bound single-use token semantics, the additive evidence model, or the public-API-only rule.
