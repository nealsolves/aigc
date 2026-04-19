> Superseded on 2026-04-15.
> Active file: `docs/plans/AIGC V0.9.0 IMPLEMENTATION_PLAN.md`.
> Status: historical input only for PR-01 source-of-truth review.
> Do not use this file as the active `v0.9.0` implementation plan.

# AIGC `v0.9.0` Implementation Plan

Date: 2026-04-15

## 1. Title and intent

This document is the canonical implementation plan for `v0.9.0` beta.

Intent:

- Ship `v0.9.0` as the beta where workflow governance becomes real for application teams, not just available in principle.
- Make the primary release story brutally simple: a normal Python team can drop AIGC into a real local workflow the week of release, get a first success quickly, hit a real failure, understand it, fix it, and succeed again.
- Keep the architecture honest:
  - AIGC remains an SDK, not a hosted orchestrator, transport, or runtime platform.
  - The host continues to own orchestration, transport, retries, credentials, business state, tool execution, and provider SDK usage.
  - AIGC continues to own policy loading, ordered governance checks, workflow constraints, evidence correlation, optional adapter normalization, and audit artifacts.
- Preserve additive migration, fail-closed behavior, public-API-only examples, optional adapters, and beta framing.

## 2. Summary

- `v0.9.0` is the feature-complete beta where workflow governance becomes real for users, not just for maintainers.
- The release is judged first by time-to-first-success, clarity of failure handling, and practical adoption through docs, starter assets, demo flows, presets, and public examples.
- The default user story is a simple local workflow in a host-owned Python app using ordinary `AIGC.open_session(...)` session semantics.
- Bedrock and A2A support remain in scope, but they are advanced optional integration tracks, not the center of the release narrative.
- `v0.9.0` is only successful if app teams can adopt it quickly through the golden path without reading internal code, hand-authoring advanced manifests for the default path, or absorbing the full conceptual model up front.
- Invocation-only users must keep working. Workflow adoption must be additive, not a forced rewrite.
- Security stays fail-closed. Missing required evidence, ambiguous identity, unsupported bindings, invalid transitions, malformed or stale session tokens, and governance ambiguity are rejection paths, not warnings.

## 3. Product narrative for `v0.9.0`

`v0.9.0` is the beta release where AIGC stops being merely a set of workflow-capable primitives and becomes a practical workflow-governance SDK that app teams can adopt quickly.

The product narrative for this beta is:

- Start local.
- Start with a real host app.
- Start with `workflow init`, starter scaffolds, and thin presets.
- Start with a small `2`-step or `3`-step governed workflow.
- Start with public APIs only.
- Learn through one clear success path and one clear failure-and-fix path.

The release does not succeed because the workflow engine exists. It succeeds because the default adopter can do the following in a clean environment within `15` minutes:

1. Install the package.
2. Initialize workflow assets.
3. Choose a minimal or standard scaffold.
4. Paste a starter flow into a local host app.
5. Run it and get a first PASS.
6. Inspect the workflow trace and audit artifact.
7. Trigger a common failure on purpose.
8. Use `workflow lint` or `workflow doctor` to understand the failure.
9. Fix the issue without reading internal code.
10. Re-run and succeed again.

Advanced workflow DSL authoring, Bedrock normalization, A2A normalization, and richer operator tooling remain important, but they are secondary learning tracks. They must not displace the golden path.

## 4. Golden path first-adopter journey

### Default first-adopter journey

1. Install `aigc` in a fresh Python environment.
2. Run `aigc workflow init` and select either `minimal` or `standard`.
3. Generate starter policy and workflow assets without hand-authoring advanced manifests.
4. Copy a starter `2`-step or `3`-step workflow into a local host application that already owns orchestration and provider calls.
5. Open a session through `AIGC.open_session(...)`.
6. Run the workflow and produce:
   - a successful governed invocation result
   - a workflow trace
   - a workflow artifact plus correlated invocation artifacts
7. Break one common thing on purpose:
   - participant identity mismatch
   - invalid transition
   - unsupported protocol binding
   - missing required evidence
   - malformed or stale session token
   - scaffold or setup mistake
8. Run `aigc workflow lint` for static issues and `aigc workflow doctor` for runtime or evidence issues.
9. Read a plain-English explanation plus a stable machine-readable reason code.
10. Fix the problem using public docs and starter guidance.
11. Re-run successfully.
12. Decide whether to stay local, add approvals, or later adopt Bedrock or A2A recipes.

### What the release centers on

- Local workflow first.
- Presets and starter scaffolds first.
- `workflow doctor` and `workflow lint` first.
- Invocation-only migration first.
- Adapters later.

### What the default adopter should not need

- No hosted AIGC service.
- No hidden orchestration layer.
- No module-level `open_session(...)` contract change.
- No Bedrock or A2A dependency for first success.
- No `_internal` imports.
- No internal-code reading.
- No manual construction of every workflow artifact from scratch.
- No hand-authored advanced workflow DSL for the default path.

## 5. Locked decisions

### Scope and boundary

- `v0.9.0` includes workflow governance, workflow evidence, validator hooks, human approval checkpoints, workflow CLI commands, starter scaffolds, thin presets, migration assets, and optional Bedrock and A2A adapters.
- `v0.9.0` does not include a hosted orchestrator, queue runner, transport layer, credential broker, runtime platform, remote session manager, model-serving subsystem, or hidden execution engine.
- The host owns orchestration, transport, retries, credentials, business state, tool execution, and provider SDK usage.
- AIGC owns policy loading, ordered governance checks, workflow constraints, evidence correlation, optional adapter normalization, and audit artifacts.
- Adapters accept host-supplied parsed payloads plus request metadata. They do not own HTTP clients, auth flows, streaming sockets, provider retries, or transport sessions.

### Public surface and migration posture

- Invocation-only users keep working on supported APIs.
- Workflow adoption remains instance-scoped through `AIGC.open_session(...)`.
- `v0.9.0` does not introduce a new module-level `open_session(...)` public API.
- Public examples, quickstarts, starter assets, presets, and demo code must use only public APIs and must never import from `aigc._internal`.
- Hand-authored workflow DSL is supported but treated as advanced mode.
- Starter packs, init scaffolds, and thin presets are the default adoption path.
- Thin presets must stay honest. They compile to ordinary session plus policy plus manifest behavior and must not hide host orchestration ownership or create alternate enforcement semantics.

### Evidence model

- Invocation artifacts remain one artifact per invocation attempt.
- Workflow or session evidence stays separate from invocation evidence.
- Invocation artifacts gain only additive workflow-correlation metadata.
- Raw external payloads are not persisted by default.
- Workflow evidence stores normalized metadata, checksums, integrity metadata, explicit failure reasons, and export metadata unless the host explicitly opts into richer persistence.

### Workflow lifecycle and artifact status

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

State-to-status mapping at finalize time:

| Lifecycle state | Emitted workflow artifact status |
| --- | --- |
| `COMPLETED` | `COMPLETED` |
| `FAILED` | `FAILED` |
| `CANCELED` | `CANCELED` |
| `OPEN` or `PAUSED` | `INCOMPLETE` |

Additional rules:

- `FINALIZED` is a lifecycle state only and is never serialized as an artifact status.
- `finalize()` from `OPEN` or `PAUSED` is allowed and emits `INCOMPLETE`.
- Once `FINALIZED`, the session rejects new authorization and completion attempts.

### `SessionPreCallResult` contract

- `SessionPreCallResult` wraps a valid invocation `PreCallResult` plus immutable `session_id`, `step_id`, `participant_id`, and workflow-bound replay protection.
- The wrapper is single-use.
- A wrapped token cannot be completed through module-level `enforce_post_call(...)`; it must be completed through the owning `GovernanceSession`.
- Session completion validates both underlying invocation integrity and workflow-step binding before post-call enforcement proceeds.

### Context-manager semantics

- `GovernanceSession` is a context manager.
- `__exit__` never suppresses exceptions.
- Clean exit from a non-terminal session auto-finalizes to `INCOMPLETE`.
- Exception exit records failure context, transitions the session to `FAILED` if needed, emits a `FAILED` workflow artifact, and re-raises.
- Clean exit from a `COMPLETED` or `CANCELED` session finalizes normally.

### Workflow composition and budget semantics

- Participants merge by stable `id`.
- Role sets compose by restriction, never by widening union.
- Transition, handoff, protocol, and authority-bearing rules remain explicit after composition and may only narrow.
- Ambiguous or widening merges fail validation.
- `max_steps` counts authorized workflow steps.
- `max_total_tool_calls` counts normalized tool-use units across the session.
- Local governed steps count invocation `tool_calls`.
- Adapter-observed tool usage counts one normalized unit per deduplicated `tool_observed` event identity.
- Authorization checks remaining budget conservatively before a step starts.
- Completion checks actual usage and fails closed if policy was exceeded.

### Bedrock contract lock

- Governed Bedrock handoffs require alias-backed participant identity.
- Alias evidence may come from trusted host-supplied collaborator registry metadata and, where available, collaborator invocation evidence.
- `collaboratorName` and equivalent trace names are descriptive evidence only and cannot be the sole binding key for governed authorization.
- If policy requires trace and trace is missing, the adapter rejects the event stream.
- AIGC governs only host-visible handoff and evidence boundaries, not hidden Bedrock-internal orchestration.

### A2A contract lock

- `v0.9.0` supports A2A `1.0` over JSON-RPC and HTTP+JSON only.
- gRPC is out of scope for `v0.9.0` normalization and must fail with a typed protocol violation.
- Compatibility is validated from `supportedInterfaces[].protocolVersion`, not descriptive Agent Card version text.
- Host-supplied `A2A-Version` metadata is validated only where the in-scope binding uses it.
- Wire task states must validate as normative ProtoJSON `TASK_STATE_*` values.
- Informal or descriptive task-state names are rejected at the boundary.
- Internal shorthand is allowed only after successful wire-level validation.

### Diagnostics, explainability, and evidence trust

- `workflow doctor` and `workflow lint` are core product surface, not optional nice-to-have tooling.
- Diagnostics must emit stable machine-readable reason codes and plain-English messages.
- Common blocker coverage must include:
  - identity mismatch
  - invalid transition
  - unsupported binding
  - missing required protocol evidence
  - malformed or stale session token
  - scaffold or setup mistake
- External protocol evidence is untrusted until validated against the relevant adapter or validator contract.
- Provider metadata is descriptive unless policy explicitly marks a validated host-backed source authoritative for a governed decision.
- Ambiguous or incomplete identity evidence fails closed whenever policy requires authoritative binding.

### Beta framing

- `v0.9.0` is a feature-complete beta.
- `1.x` stability guarantees do not begin until `1.0.0`.
- Beta success is measured by real adopter success and failure-handling clarity, not by surface area alone.

## 6. Release principles for beta adoptability

- Golden path is the product. The first story is a local host-owned workflow that works quickly and teaches itself through docs, scaffolds, and diagnostics.
- Default before advanced. Minimal and standard scaffolds, thin presets, and starter recipes come before adapter-heavy stories, advanced DSL authoring, or operator-deep flows.
- Additive migration only. Existing invocation-only users get value without a rewrite, and can adopt workflow governance in small steps.
- Public API only. No quickstart, starter, preset, recipe, or demo may depend on `_internal` imports or maintainer-only knowledge.
- Honest ergonomics. Presets save typing but do not hide orchestration, retries, transport, credentials, or business-state ownership.
- Failure must be understandable. A common first-adopter mistake must produce a stable reason code, a plain-English explanation, and an obvious next action.
- Docs must behave like product. The quickstart, starter index, migration guide, and troubleshooting path are release-critical assets and must be verified from a clean environment.
- Security remains fail-closed. Better onboarding is not permission to weaken identity requirements, protocol validation, evidence integrity, or restrictive composition.
- Optional means optional. Bedrock, A2A, and observability extras must not bloat or block the base install or the default quickstart.

## 7. Rewritten implementation sequence (step-by-step, PR style)

**Step 1. PR-01 Source-of-Truth Cleanup and Canonical Reset**

- Branch: `feat/v0.9-01-source-of-truth`
- Goal: make one implementation plan and one release truth active before more work lands.
- Implement:
  - Publish this rewrite as the canonical `v0.9.0` plan.
  - Mark competing artifacts as `superseded` or `historical input`, including:
    - `docs/plans/AIGC V0.9.0 IMPLEMENTATION_PLAN.md`
    - `implementation_plan.md`
    - `implementation_status.md`
    - `docs/plans/AIGC v0.9.0 Practical Implementation Plan.docx`
    - `docs/plans/AIGC v0.9.0 to v1.0.0 PLAN.md`
    - `docs/plans/AIGC v1.0 Development Plan.pdf`
  - Update `implementation_status.md` to track the active `v0.9.0` beta train instead of stale release targets.
  - Update `RELEASE_GATES.md` so `v0.9.0` beta gates and `v1.0.0` promotion gates match this plan.
  - Add CI checks that fail if more than one active `v0.9.0` plan exists or if superseded artifacts are unlabeled.
  - Correct canonical release-truth facts, including release framing and live baseline references.
- Tests:
  - markdown lint
  - supersession-label checks
  - release-truth checks
  - no runtime delta
- Exit:
  - contributors have one active release plan, one active set of release gates, and CI-enforced source-of-truth discipline.

**Step 2. PR-02 Contract Freeze**

- Branch: `feat/v0.9-02-contract-freeze`
- Goal: lock the hard architectural contract before implementation branches widen.
- Implement:
  - Publish and freeze the locked decisions in Section `5`.
  - Freeze:
    - workflow lifecycle and artifact status mapping
    - `SessionPreCallResult` semantics
    - context-manager semantics
    - restrictive composition rules
    - `AIGC.open_session(...)` instance-scoped adoption
    - invocation-artifact and workflow-artifact separation
    - Bedrock alias-backed identity requirements
    - A2A `1.0` wire-level validation rules
  - Add sentinel tests for symbols and commands that are intentionally absent before later steps land.
  - Add protocol-boundary assertions for Bedrock and A2A fail-closed rules.
- Tests:
  - contract-doc lint
  - lifecycle and public-surface sentinel tests
  - protocol-boundary assertion tests
  - release-truth checker tests
- Exit:
  - the hard contract is frozen early enough that later adoption work builds on it instead of renegotiating it.

**Step 3. PR-03 Golden-Path Contract Freeze**

- Branch: `feat/v0.9-03-golden-path-contract`
- Goal: freeze the default adopter experience before too much surface area ossifies.
- Implement:
  - Freeze the default CLI and starter surface for:
    - `aigc policy init`
    - `aigc workflow init`
    - `aigc workflow lint`
    - `aigc workflow doctor`
    - `aigc workflow trace`
    - `aigc workflow export`
  - Freeze the default scaffold profiles:
    - `minimal`
    - `standard`
    - `regulated-high-assurance`
  - Freeze required starter workflow coverage:
    - local multi-step review flow
    - approval checkpoint flow
    - source-required flow
    - tool-budget flow
  - Freeze the rule that hand-authored workflow DSL is advanced mode and not required for the default path.
  - Freeze public-import-only rules for all examples, presets, starter packs, demo code, and docs snippets.
  - Freeze the docs order required for first adopters.
  - Freeze minimum diagnostic coverage and stable reason-code requirements for first-user failures.
- Tests:
  - CLI shape tests
  - starter-asset shape tests
  - public-import boundary tests
  - docs-order checks
- Exit:
  - the default first-user path is an explicit contract, not a late packaging exercise.

**Step 4. PR-04 Minimal Working Session Flow**

- Branch: `feat/v0.9-04-minimal-session-flow`
- Goal: land the smallest real governed workflow path using ordinary session semantics.
- Implement:
  - Add workflow evidence schema and additive invocation-correlation metadata.
  - Add `GovernanceSession` core with deterministic lifecycle and finalize behavior.
  - Add `AIGC.open_session(...)` as the public workflow entrypoint.
  - Add session-aware step enforcement:
    - `enforce_step(...)`
    - `enforce_step_pre_call(...)`
    - `enforce_step_post_call(...)`
    - `SessionPreCallResult`
  - Support a local `2`-step or `3`-step workflow with host-owned orchestration and provider calls.
  - Produce one workflow artifact plus correlated invocation artifacts for a passing run.
- Tests:
  - lifecycle tests
  - context-manager tests
  - replay-prevention tests
  - invocation-correlation tests
  - first-pass local workflow smoke tests
- Exit:
  - AIGC can govern a simple local workflow end to end without adapters, hidden orchestration, or internal APIs.

**Step 5. PR-05 Starter Scaffolds, Presets, and Builder Ergonomics**

- Branch: `feat/v0.9-05-starters-and-presets`
- Goal: make the default path copy-pasteable before richer engine work dominates the release.
- Implement:
  - Ship `aigc workflow init` and `aigc policy init` scaffolds for `minimal`, `standard`, and `regulated-high-assurance`.
  - Ship at least two copy-paste starter examples that run against the Step `4` session flow.
  - Ship starter workflows for:
    - local multi-step review flow
    - approval checkpoint flow
    - source-required flow
    - tool-budget flow
  - Ship thin preset builders that compile to ordinary session plus policy plus manifest behavior with no hidden runtime layer.
  - Ensure the default path does not require manually constructing every workflow artifact from scratch.
  - Publish initial migration helpers that show the smallest safe diff from invocation-only governance to session-based workflow governance.
- Tests:
  - scaffold generation tests
  - starter smoke tests
  - preset parity tests
  - public-import-only tests
  - clean install smoke for base package
- Exit:
  - a new user can start from scaffolds and starters instead of a blank page, and an existing user can see a practical migration path immediately.

**Step 6. PR-06 Doctor, Lint, and Plain-English Diagnostics**

- Branch: `feat/v0.9-06-doctor-and-lint`
- Goal: make first failures understandable before advanced workflow surface expands.
- Implement:
  - Add `aigc workflow lint` for static validation of schema, transitions, bindings, budgets, starter integrity, and public-import safety.
  - Add `aigc workflow doctor` for runtime and evidence diagnosis.
  - Emit stable machine-readable reason codes plus plain-English messages.
  - Cover at minimum:
    - identity mismatch
    - invalid state transition
    - unsupported binding
    - missing required protocol evidence
    - malformed or stale session token
    - scaffold or setup mistake
  - Require blocker explanations and next-action guidance for common failures.
  - Validate UX on intentional failure cases using starter assets, not maintainer-only fixtures.
- Tests:
  - lint rule tests
  - doctor JSON shape tests
  - reason-code stability tests
  - common failure/fix path tests
  - public-doc wording checks for top failure cases
- Exit:
  - the first adopter can hit a real failure and recover without reading internal code or reverse-engineering evidence manually.

**Step 7. PR-07 Quickstart, Demo, and Docs Proof Checkpoint**

- Branch: `feat/v0.9-07-adoption-proof`
- Goal: stop the train early if the golden path is not actually working.
- Implement:
  - Publish the workflow quickstart, starter recipe index, invocation-only migration guide, workflow CLI guide, and troubleshooting guide in first-adopter order.
  - Build the release demo around the golden path:
    - one `start here` flow
    - one intentional failure-and-fix flow
    - one governed-vs-ungoverned comparison
    - one workflow trace view
    - one audit and export visibility flow
    - no fake backend behavior
  - Run clean-environment docs-to-working-app validation for the default path.
  - Run public-import-only validation across examples, docs snippets, starter packs, and demo code.
  - Validate that the default path requires no internal-code reading and no hand-authored advanced manifests.
- Tests:
  - clean-environment docs-to-app smoke tests
  - quickstart time-budget run
  - demo smoke tests
  - failure/fix end-to-end tests
  - `_internal` import boundary tests
- Exit:
  - this is the first stop-ship checkpoint; no later public surface expansion proceeds until the golden path works from docs alone.

**Step 8. PR-08 Workflow Engine Hardening**

- Branch: `feat/v0.9-08-engine-hardening`
- Goal: deepen the workflow engine after the default adoption path is already real.
- Implement:
  - Enforce ordered sequence, allowed transitions, participants, roles, handoffs, protocol constraints, approvals, `max_steps`, and `max_total_tool_calls`.
  - Freeze restrictive composition behavior and reject widening merges.
  - Add deterministic workflow failure reasons and reason-code mappings that align with `workflow doctor`.
  - Add human approval checkpoints with auditable pause and resume semantics.
  - Add `ValidatorHook` with typed, versioned input and output contracts, timeout semantics, stale-result handling, bounded retry rules, and auditable provenance.
  - Ensure preset output and hand-authored DSL flow through the same enforcement engine.
- Tests:
  - state-machine tests
  - restrictive-composition tests
  - budget accounting tests
  - approval checkpoint tests
  - validator hook timeout, retry, and stale-result tests
  - reason-code parity tests
- Exit:
  - the engine is hard enough for broader beta use without displacing the already-proven first-adopter path.

**Step 9. PR-09 Export, Trace, CLI, and Operator Polish**

- Branch: `feat/v0.9-09-exports-and-ops`
- Goal: round out workflow visibility and portability after the core adoption path and engine are stable.
- Implement:
  - Add `aigc workflow trace` and `aigc workflow export`.
  - Reconstruct workflow timelines from workflow artifacts plus invocation evidence.
  - Support operator and audit export modes with integrity metadata, sink outcomes, and verification guidance.
  - Surface sink failures explicitly and preserve fail-closed semantics where policy marks sinks as required.
  - Add optional structured events, optional metrics, and optional OpenTelemetry-friendly mapping without making them base-install critical.
  - Keep existing invocation and compliance tooling working.
- Tests:
  - export verification tests
  - trace reconstruction tests
  - sink-failure handling tests
  - JSON output shape tests
  - optional observability sanity tests
- Exit:
  - operators can inspect, trace, and export governed workflows without turning AIGC into a monitoring platform.

**Step 10. PR-10 Optional Adapters and Advanced Recipes**

- Branches:
  - `feat/v0.9-10-bedrock-adapter`
  - `feat/v0.9-10-a2a-adapter`
- Goal: add advanced integration tracks without blocking or redefining the primary release story.
- Implement Bedrock:
  - Add `BedrockTraceAdapter` for host-supplied parsed trace parts plus trusted collaborator metadata.
  - Support observational normalization and governed binding tiers, with alias-backed identity mandatory for governed binding.
  - Fail closed on missing required trace, missing alias evidence, or ambiguous collaborator identity.
- Implement A2A:
  - Add `A2AAdapter` for parsed Agent Card, request metadata, and task envelopes.
  - Validate `supportedInterfaces[].protocolVersion`.
  - Accept only normative `TASK_STATE_*` boundary values.
  - Reject unsupported gRPC transport with typed protocol violations.
  - Keep transport, auth, retries, and remote-session ownership in the host.
  - Publish adapter docs and recipes as advanced follow-on documentation, not first-run documentation.
- Tests:
  - fixture-only adapter tests
  - Bedrock alias-binding tests
  - missing-trace and ambiguous-identity tests
  - A2A boundary validation tests
  - transport-negative tests
  - no live network or cloud calls
- Exit:
  - adapters are real, honest, and fail-closed, but the primary quickstart remains excellent without them.

**Step 11. PR-11 Public API Freeze and Beta Release**

- Branch: `feat/v0.9-11-beta-freeze` then `release/v0.9.0`
- Goal: freeze the beta surface only after the golden path, diagnostics, engine, and advanced tracks are proven.
- Implement:
  - Add public API snapshot tests for documented `v0.9.0` symbols.
  - Lock CLI help text and machine-readable JSON shapes for workflow commands.
  - Verify all golden-path stop-ship gates.
  - Verify security gates and adapter-boundary rules.
  - Verify export portability and integrity compatibility.
  - Validate package metadata, extras packaging, and beta release notes.
  - Publish explicit beta framing that `1.x` stability guarantees begin at `1.0.0`, not `0.9.0`.
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
  - `v0.9.0` is publishable as a feature-complete beta whose default workflow-adoption path is proven, not assumed.

## 8. Golden path checkpoint and stop-ship gates

The first stop-ship checkpoint occurs after Step `6` and must be completed in Step `7`, before later engine hardening, export polish, or adapter work dominates the train.

This checkpoint exists to stop the release from shipping an internally coherent workflow architecture that is still too hard to adopt.

### Stop-ship requirements

- Clean-environment docs-to-working-app run passes for the default local workflow path.
- Quickstart completes within a `15`-minute budget for a maintainer who has not been editing the implementation in the same shell session.
- At least two copy-paste starter examples produce a first PASS using only public APIs.
- At least one intentional failure-and-fix path is tested end to end.
- `workflow doctor` and `workflow lint` both explain that failure clearly enough for a first adopter to recover.
- No internal-code reading is required to complete the path.
- No hand-authoring of advanced manifests is required for the default path.
- Public-import-only validation passes across examples, starter packs, docs snippets, presets, and demo code.
- The default path does not require Bedrock or A2A.
- The default path proves workflow trace visibility and workflow artifact visibility.

### Failure cases that must be validated at this checkpoint

- broken scaffold or setup
- invalid transition
- participant identity mismatch
- unsupported binding
- missing required evidence
- malformed or stale session token
- approval-required block with clear next action

### Consequence

- If this checkpoint fails, no additional public surface should be frozen until the default first-adopter path is repaired.

## 9. Adapter strategy and sequencing

- Local simple host workflow is the primary `v0.9.0` release story.
- Bedrock and A2A are optional advanced integration tracks.
- Adapter docs and recipes must exist, but they are advanced follow-on material, not required reading for first success.
- Adapter implementation must not block the primary quickstart, starter scaffolds, or migration path from being excellent.
- Adapter work starts only after:
  - the source of truth is clean
  - the hard contract is frozen
  - the golden-path contract is frozen
  - the minimal session flow is real
  - starter scaffolds and presets work
  - doctor and lint explain common failures
  - the first stop-ship checkpoint passes

### Bedrock strategy

- Bedrock support is optional.
- AIGC normalizes host-visible evidence only.
- Governed participant binding requires alias-backed identity and fail-closed handling of ambiguity.
- Bedrock docs must state clearly what the host must provide for observational normalization versus governed binding.

### A2A strategy

- A2A support is optional.
- `v0.9.0` supports only in-scope `1.0` JSON-RPC and HTTP+JSON bindings.
- Wire-contract correctness is mandatory.
- Transport ownership remains in the host.

### Release posture

- Adapter completeness does not excuse a weak local workflow quickstart.
- A strong adapter story is secondary to a strong local workflow adoption story.

## 10. Documentation and demo deliverables

Documentation is ordered by first-adopter priority, not by architecture category.

### Required documentation

1. Workflow quickstart
2. Starter recipe index
3. Migration from invocation-only to workflow
4. Workflow CLI guide
5. Troubleshooting and `workflow doctor` / `workflow lint` guide
6. SDK boundary
7. Public API stability
8. Supported environments
9. Operations runbook
10. Adapter docs as advanced follow-on docs

### Documentation obligations

- The quickstart must answer: how do I get my first governed workflow running?
- The troubleshooting guide must answer: what broke, why did it break, and how do I fix it?
- The migration guide must answer: how do I get value from workflow governance without rewriting my existing invocation-only integration?
- The starter recipe index must point first to local host-owned flows before any adapter-backed recipes.
- The SDK boundary doc must say clearly what the host owns and what AIGC owns.
- The public API stability doc must identify the beta surface and explicitly exclude `_internal`.
- All docs snippets, examples, and recipes must use public imports only.

### Required demo flows

- One `start here` flow that follows the quickstart.
- One intentional failure-and-fix flow using `workflow doctor` or `workflow lint`.
- One governed-vs-ungoverned comparison that shows why workflow governance adds value.
- One workflow trace view.
- One audit and export visibility flow.
- No fake backend behavior. Demo behavior must reflect real host-owned execution and real AIGC governance decisions.

## 11. Adoption acceptance criteria

### First adopter acceptance matrix

| Scenario | Required outcome |
| --- | --- |
| Fresh install -> minimal workflow scaffold -> first PASS | A clean environment can install base `aigc`, run `workflow init`, paste the starter into a local host app, and produce a passing workflow plus correlated evidence. |
| Fresh install -> standard workflow scaffold -> first PASS | A clean environment can complete the standard path without Bedrock or A2A and without hand-authoring advanced manifests. |
| Broken config -> doctor identifies exact issue | `workflow doctor` emits a stable reason code, a plain-English blocker explanation, and a next-action hint. |
| Invalid transition -> lint or doctor explains why | The user is told what transition is invalid, what rule blocked it, and what valid next step is expected. |
| Approval-required path blocks correctly and explains next action | The workflow pauses fail-closed, records auditable checkpoint state, and tells the operator what approval action is required. |
| Invocation-only migration path works without rewrite | An existing invocation-only integration can adopt session governance in a small diff and continue using supported invocation APIs. |
| Docs-to-working-app path succeeds from clean environment | The documented quickstart works from scratch without maintainer intervention, local tribal knowledge, or `_internal` imports. |
| Public examples run without internal imports | All public examples, starter packs, presets, and demo code pass import-boundary validation. |
| First adopter does not need Bedrock or A2A to get value | The local path is fully useful on its own. Adapter docs are optional follow-on reading. |
| Quickstart remains within the `15`-minute budget | The default path is measured, repeatable, and within budget. |

### Migration story that must be real

Day `1`:

- Stay on invocation-only governance if that is all the app needs.
- Add starter docs and `workflow init` to understand the path without rewriting the app.
- Optionally wrap one existing path in `AIGC.open_session(...)` and keep host orchestration unchanged.

Day `3`:

- Convert one simple `2`-step or `3`-step local flow to governed workflow sessions.
- Use `minimal` or `standard` scaffold plus starter recipes instead of hand-authoring the full DSL.
- Use `workflow doctor` and `workflow lint` to resolve the first real failure.

Later:

- Add approval checkpoints, source requirements, or tool budgets.
- Hand-author or extend workflow DSL only when the team needs more than the starter or preset path.
- Evaluate Bedrock or A2A recipes only if the host actually needs those protocols.

### Adoption criteria

- Existing invocation-only users do not need rewrites to remain supported.
- Existing invocation-only integrations can get immediate value from session-level evidence and simple governed multi-step flows before committing to advanced DSL authoring.
- A new adopter can complete the default path without reading internal code.
- The default adopter path works without Bedrock or A2A.
- The default adopter path works through starter packs, init scaffolds, thin presets, docs, demo, and diagnostics rather than handwritten maintainer-only setup.

## 12. Security acceptance criteria

- Missing required protocol evidence fails closed.
- Workflow composition can only narrow authority, never widen it implicitly.
- Bedrock governed handoffs require alias-backed identity.
- A2A validation enforces the actual `1.0` wire contract and in-scope binding rules.
- Session tokens are single-use and workflow-bound.
- Invocation evidence remains one artifact per invocation attempt and separate from workflow evidence.
- Workflow evidence is additive and does not replace invocation evidence.
- External protocol evidence is untrusted until validated against the relevant adapter contract.
- Provider metadata is descriptive unless policy explicitly marks validated host-backed evidence authoritative.
- Invalid transitions, participant mismatches, unsupported bindings, malformed or stale tokens, and missing required evidence are hard blocks, not warnings.
- Approval checkpoints and validator outcomes are deterministic, auditable, and fail closed where policy requires them.
- Raw external payloads are not persisted by default.
- Evidence integrity, signing compatibility, and optional tamper-evident chaining compatibility are preserved.
- Public examples and docs must not weaken the security model by relying on `_internal` shortcuts or hidden orchestration.
- Optional adapters and optional observability surfaces do not weaken the base install or its fail-closed guarantees.

## 13. Release gates for `v0.9.0` beta

`v0.9.0` beta ships only if all of the following are true:

- One canonical implementation plan is active and stale plan truth is CI-enforced as superseded or historical.
- Release-truth checks are green against live repo facts.
- Locked contract decisions are published and test-backed.
- The golden-path contract is frozen before later public surface expansion.
- A clean environment can complete the workflow quickstart in `15` minutes or less.
- At least two copy-paste starter examples are green and use only public imports.
- At least one failure-and-fix path is tested end to end and validated for clarity.
- `workflow doctor` and `workflow lint` provide stable reason codes and plain-English explanations for common first-adopter failures.
- The docs-to-working-app path succeeds without internal-code reading or manual advanced manifest authoring.
- `aigc policy init`, `aigc workflow init`, `aigc workflow lint`, `aigc workflow doctor`, `aigc workflow trace`, and `aigc workflow export` pass snapshot and UX validation.
- Public examples, presets, starter packs, docs snippets, and demo code pass `_internal` import boundary checks.
- Invocation-only migration is documented, tested, and works without rewrite.
- Workflow artifact schema, invocation-correlation metadata, and backward compatibility for invocation-only users are locked.
- Restrictive composition tests prove that permission-bearing fields narrow rather than widen.
- Bedrock tests prove that name-only collaborator evidence is insufficient where policy requires authoritative identity.
- A2A tests prove acceptance of normative `TASK_STATE_*` wire values and rejection of shorthand boundary values.
- Operator and audit export verification passes, including sink-failure reporting and integrity verification guidance.
- Optional observability surfaces pass sanity checks without becoming required for the base install.
- Package smoke passes for the base install and optional extras.
- The release is explicitly labeled Beta, with `1.x` stability deferred to `1.0.0`.

## 14. Promotion gates for `v1.0.0`

`v1.0.0` promotion is blocked until beta learning shows that the `v0.9.x` path is not only correct, but adoptable in practice.

### Minimum promotion gates

- Minimum `14`-day soak on `v0.9.x`.
- Zero open `P0` or `P1` correctness or security defects.
- No unresolved public API or CLI snapshot drift.
- No pending migration-breaking changes.
- At least two real adopter validations of the public workflow surface.

### Required beta adoption metrics and review

The team must collect, review, and act on:

- time to first successful workflow
- time to first understandable failure and fix
- percentage of adopters using invocation-only migration versus brand-new workflow setup
- percentage of adopters completing the golden path without manually editing advanced manifests
- most common `workflow doctor` and `workflow lint` failure reasons
- whether first adopters needed Bedrock or A2A at all
- top blockers discovered during beta

### Required outcomes before `1.0.0`

- The measured golden path is consistently successful for real adopters, not just maintainers.
- The most common beta blockers have documented fixes or product changes, not just known-issue notes.
- Invocation-only migration remains practical and stable.
- Adapter usage patterns are understood well enough to keep them honest and optional.
- The team has evidence that the first-adopter path works without internal-code reading and without hidden bootstrap steps.

## 15. Bottom line

`v0.9.0` ships as a feature-complete beta only if workflow governance is easy to start, easy to diagnose, and honest about its boundaries.

The release story is not "workflow primitives exist." The release story is:

- a Python app team can govern a small real workflow quickly
- they can start from docs and copy-paste starters
- they can understand a real failure and recover
- they can migrate additively from invocation-only usage
- they do not need Bedrock or A2A for first success

All of that must happen without weakening fail-closed security, evidence integrity, restrictive composition, protocol correctness, or the host-owned orchestration boundary.
