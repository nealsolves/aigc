> Superseded on 2026-04-15.
> Active file: `docs/plans/AIGC V0.9.0 IMPLEMENTATION_PLAN.md`.
> Status: historical input only for PR-01 source-of-truth review.
> Do not use this file as the active `v0.9.0` implementation plan.

# AIGC `v0.9.0` Draft Implementation Plan

Date: 2026-04-14

Intended role:
- This draft is the proposed canonical replacement for the current `v0.9.0` implementation plan.
- It incorporates the issues raised in the reviewed planning and audit documents while preserving the AIGC SDK boundary.
- It keeps `v0.9.0` focused on workflow governance, adoption readiness, and fail-closed security instead of turning the SDK into a hosted orchestration or model-serving platform.

## Summary

- `v0.9.0` is the feature-complete beta for the future `v1.0.0` GA line.
- Baseline is shipped `v0.3.3`: invocation governance is stable, `976` tests collect as of 2026-04-14, and the current doc-parity checker passes even though some baseline facts are stale.
- `v0.9.0` adds workflow governance, optional Bedrock normalization, optional A2A normalization, human review checkpoints, and workflow inspection/export tooling.
- `v0.9.0` only counts as feature-complete if it is also adoption-ready through public examples, starter scaffolding, thin presets built on ordinary session semantics, and operator-grade diagnostics/export paths.
- Adoption must be additive: invocation-only users keep working, adapters stay optional, and examples use only public APIs.
- Security must stay fail-closed: missing protocol evidence, ambiguous identity, unsupported bindings, and governance ambiguity are all rejection paths, not warnings.

## What This Draft Fixes

- Locks the A2A 1.0 contract at the actual wire contract.
- Makes Bedrock governed participant binding alias-backed and fail-closed.
- Replaces permissive workflow composition with restrictive composition.
- Locks workflow lifecycle, artifact status values, and their mapping before schema work begins.
- Pulls public API, CLI-shape, and release-truth checks into the first third of the train.
- Adds an earlier adoption and ergonomics feedback loop before too much workflow surface area ossifies.
- Strengthens policy and workflow scaffolding, starter packs, and blocker diagnostics so adoption work is not deferred to late packaging.
- Strengthens `ValidatorHook` semantics around typed outputs, timeout handling, retry limits, stale-result handling, and audit capture.
- Strengthens operator posture with clearer observability, export modes, sink-failure semantics, and workflow evidence portability.
- Strengthens evidence integrity with explicit signing, integrity metadata, and optional tamper-evident chaining compatibility.
- Names the stale and competing planning artifacts that Step 1 must archive, rewrite, or mark as superseded.
- Resolves open design ambiguities around `SessionPreCallResult`, budget counting, context-manager exit behavior, and workflow adoption through `AIGC.open_session(...)`.

## Locked Decisions

### 1. Scope

- `v0.9.0` includes workflow governance, workflow evidence, validator hooks, human approval checkpoints, workflow CLI commands, and optional Bedrock/A2A adapters.
- `v0.9.0` does not include a hosted orchestrator, queue runner, transport layer, credential broker, Rust/Tonic runtime, Wasm plugin sandbox, model-serving optimizations, multimodal generation pipeline, or inference-side benchmarking program.
- If model-serving, plugin isolation, or multimodal platform work is pursued later, it must land as a separate roadmap outside the AIGC SDK contract.

### 2. SDK Boundary

- The host owns orchestration, transport, sessions, retries, credentials, business state, tool execution, and provider SDK usage.
- AIGC owns policy loading, ordered governance checks, workflow constraints, evidence correlation, optional adapter normalization, and audit artifacts.
- Adapters accept host-supplied parsed payloads plus request metadata. They do not own HTTP clients, streaming sockets, auth flows, or provider retries.

### 3. Public Surface and Migration

- The intended `v0.9.0` beta public additions are `GovernanceSession`, `SessionPreCallResult`, `AgentIdentity`, `AgentCapabilityManifest`, `ValidatorHook`, `BedrockTraceAdapter`, `A2AAdapter`, and workflow CLI commands.
- Existing invocation APIs remain supported and backward compatible.
- Workflow adoption is instance-scoped through `AIGC.open_session(...)`.
- No new module-level `open_session(...)` convenience is added in `v0.9.0`; instance scope keeps signer, sink, loader, and runtime policy explicit.

### 4. Evidence Model

- Invocation artifacts remain one-per-invocation-attempt evidence.
- Workflow artifacts are separate session-level evidence and never replace invocation artifacts.
- Invocation artifacts only gain additive workflow correlation metadata.
- External raw payloads are not persisted by default. Workflow evidence stores hashes, normalized metadata, integrity metadata, and explicit failure reasons unless a host opts into richer persistence.

### 5. Workflow Lifecycle and Artifact Status

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

State-to-status mapping:

| State at finalize time | Emitted artifact status |
| --- | --- |
| `COMPLETED` | `COMPLETED` |
| `FAILED` | `FAILED` |
| `CANCELED` | `CANCELED` |
| `OPEN` or `PAUSED` | `INCOMPLETE` |

Additional rules:

- `FINALIZED` is a lifecycle state only. It is never serialized as an artifact status.
- Calling `finalize()` from `OPEN` or `PAUSED` is allowed and emits `INCOMPLETE`.
- Once `FINALIZED`, the session rejects all new authorization and completion attempts.

### 6. `SessionPreCallResult` Contract

- `SessionPreCallResult` wraps a valid invocation `PreCallResult` plus immutable `session_id`, `step_id`, `participant_id`, and workflow-bound replay protection.
- The wrapper is single-use.
- A wrapped token cannot be completed through module-level `enforce_post_call(...)`; it must be completed through the owning `GovernanceSession`.
- Session completion validates both the underlying `PreCallResult` integrity and the workflow step binding before post-call enforcement proceeds.

### 7. Context-Manager Semantics

- `GovernanceSession` is a context manager.
- `__exit__` never suppresses exceptions.
- Clean exit from a non-terminal session auto-finalizes to `INCOMPLETE`.
- Exception exit records failure context, transitions the session to `FAILED` if not already terminal, emits a `FAILED` workflow artifact, and re-raises.
- Clean exit from a `COMPLETED` or `CANCELED` session finalizes normally.

### 8. Workflow Composition Semantics

- Participants merge by stable `id`.
- Role sets compose by restriction, never union-based expansion.
- Transition and handoff rules remain explicit after composition; ambiguous or widening merges fail validation.
- Protocol constraints compose by named protocol section and may only narrow the allowed surface.
- Child workflow policies cannot widen the parent role envelope, transition envelope, handoff graph, or protocol allowance set.

### 9. Budget Semantics

- `max_steps` counts authorized workflow steps.
- `max_total_tool_calls` counts normalized tool-use units across the full session.
- Local governed steps count from invocation `tool_calls`.
- Adapter-observed tool usage counts one unit per normalized `tool_observed` event, deduplicated by event identity hash.
- Authorization checks remaining budget conservatively before a step starts.
- Completion checks actual consumed budget and fails closed if the step or observed adapter traffic exceeded policy.

### 10. Bedrock Contract Lock

- Governed Bedrock handoffs require alias-backed participant identity.
- Alias evidence may come from host-supplied collaborator registry metadata and, where available, collaborator invocation evidence.
- `collaboratorName` is descriptive evidence only and cannot be the sole binding key for governed authorization.
- If policy requires trace and trace is missing, the adapter rejects the event stream.
- AIGC governs only host-visible handoff and evidence boundaries, not hidden Bedrock-internal orchestration.

### 11. A2A Contract Lock

- `v0.9.0` supports A2A 1.0 over JSON-RPC and HTTP+JSON only.
- gRPC remains out of scope for `v0.9.0` normalization and must fail with a typed protocol violation.
- Protocol compatibility is validated from `supportedInterfaces[].protocolVersion`, not descriptive Agent Card version metadata.
- Host-supplied `A2A-Version` request metadata is validated only where the in-scope binding uses version negotiation.
- Wire task states must parse and validate as normative ProtoJSON `TASK_STATE_*` values.
- Informal or descriptive task-state names are not acceptable at the boundary.
- Internal shorthand names are allowed only after successful wire-level validation.
- Pre-1.0 method names are not supported.

### 12. Presets and Ergonomics

- Thin convenience presets may be provided for common patterns such as supervisor-collaborator, review-required, and governed remote handoff.
- Presets compile to ordinary `GovernanceSession` plus policy plus manifest behavior and do not create hidden orchestration, a second execution layer, or alternate enforcement semantics.

### 13. Hooks, Observability, and Explainability

- Hook inputs and outputs are canonicalized, typed, versioned, and auditable.
- Observability surfaces are additive and optional. Structured events, optional metrics, and optional OpenTelemetry-friendly mapping may assist operators but never replace invocation or workflow audit artifacts.
- Public diagnostics must explain blocked policy, workflow, approval, and validator outcomes in plain English while still carrying stable machine-readable reason codes.

### 14. Boundary Validation and Public Adoption Assets

- Strict protocol validation occurs at the adapter boundary before any internal shorthand or convenience mapping.
- `v0.9.0` quickstarts, starter templates, migration guides, and public examples must use only public APIs and imports.

### 15. Evidence Trust Posture

- External protocol evidence is untrusted until the relevant adapter or validator has validated it against the in-scope contract.
- Provider metadata is descriptive unless policy explicitly marks a specific host-backed field or registry source authoritative for a governed decision.
- Ambiguous or incomplete identity evidence fails closed whenever policy requires authoritative participant binding.

## Workstreams

**Step 1. PR-01 Release Contract, Canonical Reset, and Truth Baseline**

- Branch: `feat/v0.9-01-release-contract`
- Goal: make `v0.9.0` the active release train and explicitly clean up competing planning truth.
- Implement: create or accept `ADR-0011` for `v0.9.0` beta scope, SDK boundary, and non-goals.
- Implement: declare one canonical `v0.9.0` plan path and explicitly mark the following as superseded, archived, or historical input:
  - `docs/plans/AIGC V0.9.0 IMPLEMENTATION_PLAN.md`
  - `implementation_plan.md`
  - `implementation_status.md`
  - `docs/plans/AIGC v0.9.0 Practical Implementation Plan.docx`
  - `docs/plans/AIGC v0.9.0 to v1.0.0 PLAN.md`
  - `docs/plans/AIGC v1.0 Development Plan.pdf`
- Implement: either promote this draft into the canonical path or rewrite the existing canonical-path file to match this contract exactly; do not leave two active `v0.9.0` plans in-tree.
- Implement: where deletion is not practical, require explicit `superseded` or `historical input` labeling and links to the canonical replacement.
- Implement: rewrite `implementation_status.md` so it tracks the active `v0.9.0` train instead of `0.2.0`.
- Implement: update `RELEASE_GATES.md` with `v0.9.0` beta gates and `v1.0.0` promotion gates.
- Implement: correct live baseline facts in canonical docs, including current test count and release framing.
- Implement: add CI checks that fail if more than one active `v0.9.0` plan exists or if superseded plan artifacts are left unlabeled.
- Tests: markdown lint, doc parity, explicit supersession-label checks, release-truth CI checks, no runtime delta.
- Exit: contributors have one active implementation train, one active release gate file, CI-enforced source-of-truth discipline, and no stale tracker pretending to describe the current target.

**Step 2. PR-02 Contract Freeze and Early Contract Gates**

- Branch: `feat/v0.9-02-contract-freeze`
- Goal: lock the workflow, protocol, and public-surface contract before any schema or adapter code lands.
- Implement: publish the locked decisions from this draft in canonical docs:
  - lifecycle and artifact status mapping
  - `SessionPreCallResult` semantics
  - context-manager semantics
  - restrictive workflow composition
  - Bedrock alias-backed identity requirements
  - A2A 1.0 wire-level rules
  - explicit `AIGC.open_session(...)` adoption model
- Implement: add staged public-surface tests, CLI-shape tests, and starter-asset shape tests in two modes:
  - assert absence for symbols and commands intentionally not landed yet
  - flip to assert presence in the PR that introduces each public contract
  - freeze command names and top-level UX envelopes for `aigc policy init`, `aigc workflow init`, `aigc workflow doctor`, `aigc workflow lint`, `aigc workflow trace`, and `aigc workflow export`
  - freeze public example import boundaries and thin preset builder names at a shape level before implementation details expand
- Implement: add protocol-boundary assertions:
  - Bedrock collaborator names are descriptive only; governed binding requires alias-backed evidence
  - A2A boundary validation accepts only normative `TASK_STATE_*` wire enum values and rejects informal names
- Implement: tighten release-truth checks so stale doc facts do not pass parity:
  - either derive collected test count from the live suite
  - or remove test count from parity and validate it with a dedicated truth check
- Tests: contract doc lint, public-surface sentinel tests, CLI parser shape tests, starter-shape tests, protocol-boundary assertion tests, release-truth checker tests.
- Exit: all beta-surface contracts, starter shapes, and protocol-boundary assertions are frozen before schema work begins.

**Step 3. PR-03 Workflow Evidence Schema**

- Branch: `feat/v0.9-03-workflow-evidence`
- Goal: add session-level evidence without breaking invocation artifact consumers.
- Implement: create `workflow_artifact.schema.json` with locked `status` values and deterministic field ordering.
- Implement: include `workflow_schema_version`, `workflow_id`, `session_id`,
  `policy_file`, `policy_version`, `status`, `started_at`, `finalized_at`,
  `participants`, `steps`, `handoffs`, `approvals`,
  `invocation_audit_checksums`, `failure_summary`, `artifact_checksum`,
  `integrity`, `export_version`, `metadata`, and optional `signature`.
- Implement: define `integrity` metadata to carry canonical checksum, signing metadata when present, and optional tamper-evident chain references when enabled; reuse existing signing and chaining primitives where possible instead of inventing a second integrity system.
- Implement: add additive `metadata.workflow` correlation fields to invocation artifacts.
- Implement: keep raw external payload persistence disabled by default; schema should model checksums and normalized metadata instead of requiring raw provider bodies.
- Implement: define explicit sink outcome fields so operator exports can distinguish emitted, skipped, and failed sink writes instead of silently dropping that state.
- Tests: schema compatibility tests, legacy invocation artifact invariance, export correlation tests, hash-only external evidence tests, signing compatibility tests, optional chaining compatibility tests.
- Exit: workflow evidence is additive, versioned, export-ready, and compatible with optional integrity features before session code depends on it.

**Step 4. PR-04 `GovernanceSession` Core**

- Branch: `feat/v0.9-04-governance-session-core`
- Goal: create the deterministic workflow core independent of adapter logic.
- Implement: add internal workflow types for participants, steps, budgets, approvals, transitions, and artifact assembly.
- Implement: add `AIGC.open_session(...)` as the public constructor for workflow governance.
- Implement: enforce immutable session configuration after open.
- Implement: add context-manager behavior using the locked exit semantics from Step 2.
- Implement: make finalization deterministic and idempotent; reject double-finalize and post-finalize operations.
- Implement: keep session internals explicit enough that thin preset builders can compile into the same participant, policy, and manifest semantics without ambiguous alternate session behavior.
- Tests: lifecycle tests, context-manager tests, exception-path tests, concurrent independent sessions, finalize idempotence tests.
- Exit: session lifecycle is deterministic and fully specified without relying on adapter behavior.

**Step 5. PR-05 Session-Aware Step Enforcement**

- Branch: `feat/v0.9-05-session-step-enforcement`
- Goal: bind existing invocation governance to workflow steps without changing the invocation kernel contract.
- Implement: add `GovernanceSession.enforce_step(...)`, `enforce_step_pre_call(...)`, and `enforce_step_post_call(...)`.
- Implement: add `SessionPreCallResult` as the workflow-scoped split token and prohibit module-level post-call completion of wrapped session tokens.
- Implement: bind `step_id`, `step_name`, `step_index`, `participant_id`, `protocol`, and invocation checksum deterministically.
- Implement: reject unregistered step completions, replayed completions, participant mismatches, and post-finalize completions.
- Tests: unified and split parity tests, replay-prevention tests, wrapped-token misuse tests, checksum correlation tests.
- Exit: session-aware step execution is safe and compatible with existing invocation enforcement.

**Step 6. PR-06 Workflow DSL and Manifest Contracts**

- Branch: `feat/v0.9-06-workflow-dsl`
- Goal: make workflow governance declarative, stable, and restrictive by default.
- Implement: extend the policy DSL with `workflow.participants`, `max_steps`, `max_total_tool_calls`, `required_sequence`, `allowed_transitions`, `allowed_agent_roles`, `handoffs`, `escalation`, `protocol_constraints`, and a typed `validation` block or reserved future-safe equivalent.
- Implement: define public `AgentIdentity` and `AgentCapabilityManifest`.
- Implement: require manifests to carry protocol-specific identity blocks:
  - Bedrock alias-backed identity for governed collaborator binding
  - A2A identity needed to bind a validated remote Agent Card
- Implement: enforce restrictive composition rules and reject ambiguous or widening merges.
- Implement: make permission-bearing composition deterministic:
  - `allowed_agent_roles` and equivalent governed-authority fields must compose by intersection or an equivalent narrowing rule
  - transition, handoff, and protocol allowance sets may only narrow
  - compatibility or discovery metadata may be unioned only when it is explicitly non-authoritative and does not widen effective execution authority
- Implement: define the minimum viable governance lint targets that later CLI tooling must enforce:
  - explicit participants for governed handoffs
  - explicit protocol constraints for Bedrock and A2A workflows
  - bounded budgets for nontrivial multi-step workflows
  - approval TTL when review-required paths are configured
  - no widening composition
- Implement: require DSL and manifest layouts to remain compatible with public starter templates and preset builders without relying on internal-only defaults.
- Tests: DSL schema tests, composition tests, manifest validation tests, invalid handoff tests, protocol-identity validation tests, starter-template compatibility tests.
- Exit: policy shape, validation shape, and merge semantics are frozen before workflow engine work begins.

**Step 7. PR-07 Golden Path Adoption Kit and Ergonomics Checkpoint**

- Branch: `feat/v0.9-07-golden-path`
- Goal: pressure-test workflow ergonomics before later surface expansion ossifies rough edges.
- Implement: add a minimal end-to-end quickstart that creates policy and manifest inputs, opens a session, runs at least one governed step, and exports evidence using only public APIs.
- Implement: add one realistic example app flow and one copy-and-paste starter that can be lifted directly into adopter code.
- Implement: add one invocation-only migration example showing the smallest safe diff from invocation enforcement to `AIGC.open_session(...)`.
- Implement: add thin preset builders for supervisor-collaborator session, review-required session, and governed remote-handoff session; each preset must compile to ordinary session plus policy plus manifest behavior with no hidden orchestration.
- Implement: run an ergonomics review on API names, required arguments, default diagnostics, and import paths before later adapter and CLI surface expansion.
- Tests: quickstart smoke tests, realistic-example smoke tests, copy-and-paste starter smoke tests, public-import boundary tests, preset parity tests.
- Exit: at least one maintainer can complete the golden path within `15` minutes from docs alone, and no later workstream may expand public surface without preserving that path.

**Step 8. PR-08 Workflow Enforcement Engine**

- Branch: `feat/v0.9-08-workflow-engine`
- Goal: enforce workflow constraints around the invocation kernel without reordering current gates.
- Implement: enforce sequence, transitions, participants, roles, protocols, handoffs, approvals, `max_steps`, and `max_total_tool_calls`.
- Implement: use the locked budget model for local steps and adapter-observed events.
- Implement: accept preset and session-builder outputs through the same enforcement path as hand-authored workflow definitions; presets are syntax sugar, not alternate execution semantics.
- Implement: add explicit workflow failure reasons and stable reason codes for transition blocks, budget overruns, participant mismatches, protocol violations, and approval requirements so later `workflow doctor` output is explainable and machine-readable.
- Implement: keep invocation governance authoritative for invocation-level checks; workflow governance wraps it and never bypasses it.
- Tests: workflow state-machine tests, mixed local and session tests, budget accounting tests, restrictive-composition enforcement tests, doctor-reason mapping tests.
- Exit: the workflow engine can govern local workflows, preset-backed workflows, and doctor-friendly failure reporting before any external adapter lands.

**Step 9. PR-09 Bedrock Adapter**

- Branch: `feat/v0.9-09-bedrock-adapter`
- Goal: normalize Bedrock supervisor and collaborator evidence into workflow events without loosening identity requirements or overclaiming hidden runtime guarantees.
- Implement: add `BedrockTraceAdapter` for parsed trace parts plus host-supplied collaborator registry metadata.
- Implement: define and document Bedrock support tiers:
  - Tier 1 observational normalization: host supplies parsed trace parts and AIGC normalizes evidence without governed participant binding
  - Tier 2 governed participant binding: host additionally supplies trusted collaborator registry metadata that binds participant identity to alias-backed evidence
  - Tier 3 strict fail-closed governed handoff: host additionally supplies freshness and policy-compatible alias validation strong enough to block on missing or mismatched collaborator identity
- Implement: document host requirements for each tier, including trace availability, collaborator registry provenance, alias evidence quality, and any required freshness checks.
- Implement: make alias-backed identity mandatory for governed Bedrock participant binding.
- Implement: treat `TracePart.collaboratorName` and equivalent collaborator-name fields as descriptive metadata only.
- Implement: do not bind `participant_id` from manifest name matching or trace name matching alone; authoritative governed binding requires alias-backed or equivalent trusted host metadata when policy requires strong identity.
- Implement: preserve `callerChain`, collaborator alias evidence, and trace-derived event identity hashes in normalized metadata.
- Implement: fail closed on missing required trace, missing alias evidence, or collaborator identity mismatch.
- Implement: fail closed on name-only or otherwise ambiguous collaborator identity evidence whenever strong participant binding is required by policy.
- Tests: frozen official-shape fixture tests, tiered-host-requirement tests, missing-trace tests, alias-mismatch tests, participant-binding tests, no live AWS calls.
- Docs: Bedrock adapter design doc and operator recipe.
- Exit: Bedrock support is optional, tiered, boundary-correct, and honest about the host evidence required for stronger identity claims.

**Step 10. PR-10 A2A Adapter**

- Branch: `feat/v0.9-10-a2a-adapter`
- Goal: normalize remote-agent handoffs against the A2A 1.0 contract without taking over transport ownership and without widening scope beyond JSON-RPC and HTTP+JSON beta support.
- Implement: add `A2AAdapter` for parsed Agent Card data, request metadata, task envelopes, and streaming or task updates.
- Implement: validate compatibility against `supportedInterfaces[].protocolVersion`.
- Implement: validate host-supplied `A2A-Version` request metadata only where the in-scope binding uses that version negotiation surface.
- Implement: require wire-level validation of normative ProtoJSON `TASK_STATE_*` enum values and reject informal or descriptive names at the boundary.
- Implement: allow internal normalized shorthand only after successful boundary validation and normalization; shorthand values are never the protocol-boundary contract.
- Implement: support optional Agent Card signature verification when policy requires it.
- Implement: reject unsupported gRPC transport with a typed protocol violation.
- Implement: keep transport ownership, auth, retries, sockets, and remote session management in the host; the adapter normalizes parsed evidence only.
- Tests: Agent Card validation tests, task-state tests, transport-negative tests, signature-verification tests, streaming order tests, boundary enum validation tests that accept `TASK_STATE_*` and reject shorthand-at-boundary inputs, no live network calls.
- Docs: A2A adapter design doc and remote handoff recipe.
- Exit: A2A support is protocol-correct, explicitly scoped, limited to the in-scope 1.0 bindings, and safe for beta use.

**Step 11. PR-11 Human Review and Validator Hooks**

- Branch: `feat/v0.9-11-review-hooks`
- Goal: complete the fail-closed workflow control plane with deterministic human review and validator semantics.
- Implement: add pause and resume with approval tokens, approver identity, TTL, denial reasons, auditable checkpoints, and plain-English approval explanations.
- Implement: add public `ValidatorHook` interface with a canonicalized and versioned input envelope that carries `hook_schema_version`, session and step binding, policy and manifest references, input checksum, invocation checksum, deadline, and provenance metadata.
- Implement: define a strict typed output schema with `decision`, `reason_code`, `explanation`, `hook_id`, `hook_version`, `attempt`, `latency_ms`, `observed_at`, and optional structured details.
- Implement: support canonical result categories `allow`, `denial`, `warning`, `review_required`, `execution_failure`, and `timeout`; policy decides how each category maps to governance action.
- Implement: define timeout semantics explicitly:
  - timeout is distinct from denial
  - deadlines are part of the input contract
  - late results are recorded as stale evidence and are not authoritative
- Implement: define retry semantics explicitly:
  - no implicit retries by default
  - optional bounded retries may occur only for `execution_failure` or `timeout` when policy allows
  - `denial` and `review_required` are never retried automatically
- Implement: define stale-result semantics explicitly:
  - mismatched input checksum
  - obsolete attempt number
  - expired deadline
  - session already terminal or moved past the checkpoint
- Implement: capture hook provenance, schema version, input checksum, output payload, timeout configuration, attempt count, reason code, and artifact references in workflow evidence without storing raw provider payloads.
- Implement: preserve invocation ordering and attach hook outputs to workflow and session metadata instead of raw provider payload storage.
- Tests: approval-flow tests, TTL tests, denial-path tests, hook ordering tests, typed-output-schema tests, timeout and retry tests, stale-result tests, explainability tests.
- Exit: external review and semantic validation integrate without bypassing deterministic governance and produce auditable, doctor-friendly outcomes.

**Step 12. PR-12 Workflow CLI, Export, and Observability**

- Branch: `feat/v0.9-12-workflow-cli`
- Goal: make the new workflow surface observable, diagnosable, and operable for adopters and operators.
- Implement: add `aigc policy init`, `aigc workflow init`, `aigc workflow doctor`, `aigc workflow trace`, `aigc workflow export`, and `aigc workflow lint`.
- Implement: ship starter packs for `minimal`, `standard`, and `regulated-high-assurance` governance profiles through `policy init` and `workflow init`.
- Implement: make `workflow lint` enforce schema, cross-file consistency, public-import safety, and minimum viable governance rules rather than syntax alone.
- Implement: make `workflow doctor` explain common block reasons in plain English while also emitting stable reason codes and machine-readable JSON.
- Implement: reconstruct workflow timelines from invocation JSONL plus workflow artifacts.
- Implement: support operator and audit export modes that package workflow artifacts, correlated invocation artifacts, integrity metadata, sink results, and verification guidance in a portable format.
- Implement: surface sink failures explicitly so exports record whether required sinks succeeded, were skipped, or failed; if policy marks a sink as required, failure semantics must stay fail-closed.
- Implement: add optional structured events or callbacks, optional metrics surface, and optional OpenTelemetry-friendly mapping or emitter for governance latency, policy block rates, hook timeouts, approval checkpoints, participant transitions, and adapter failures.
- Implement: keep existing `policy` and `compliance export` commands intact.
- Tests: CLI fixture tests, malformed-file handling, doctor diagnostics tests, mixed legacy and new evidence tests, export verification tests, structured-event tests, metrics-emitter tests, JSON output shape tests.
- Docs: workflow CLI reference, export verification guide, and operator examples.
- Exit: users can scaffold, inspect, diagnose, observe, and export end-to-end workflow evidence through public tooling without turning AIGC into a monitoring platform.

**Step 13. PR-13 Adoption Kits, Migration, and Starter Policies**

- Branch: `feat/v0.9-13-adoption-kits`
- Goal: make `v0.9.0` easy to adopt without requiring internal knowledge.
- Implement: add starter workflow policies and starter packs for `minimal`, `standard`, and `regulated-high-assurance` maturity levels, covering supervisor and collaborator, review-required, source-required, tool-budget, and A2A remote-handoff cases.
- Implement: add runnable recipes for:
  - local host orchestration
  - FastAPI host integration
  - queue and worker host integration
  - Bedrock multi-agent evidence normalization
  - A2A remote handoff normalization
- Implement: add at least two copy-and-paste-usable starter examples and one docs-to-working-app path that can be followed from a clean environment.
- Implement: keep adapters behind optional extras so base install stays minimal.
- Implement: publish `WORKFLOW_QUICKSTART`, `MIGRATION_0_3_3_TO_0_9`, `SUPPORTED_ENVIRONMENTS`, `OPERATIONS_RUNBOOK`, and `TROUBLESHOOTING`, including a migration decision tree for when a user should stay invocation-only and when they should move to `GovernanceSession`.
- Implement: require all recipes, starter packs, presets, and docs to use public imports only and no `_internal` references.
- Tests: starter-policy tests, example smoke tests, clean-environment docs-to-app smoke tests, install and package smoke for base and extras, `_internal` import boundary checks, invocation-only to workflow migration smoke tests.
- Exit: adopters can evaluate `v0.9.0` from docs and copy-and-paste starters without reading internal code, and migration guidance is validated instead of aspirational.

**Step 14. PR-14 Beta Hardening and Release**

- Branch: `feat/v0.9-14-beta-hardening` then `release/v0.9.0`
- Goal: freeze the beta surface, complete release gates, and tag `v0.9.0`.
- Implement: add public API snapshot tests for the documented `v0.9.0` surface.
- Implement: lock CLI help text and machine-readable JSON output shapes for workflow commands.
- Implement: expand doc parity to cover the canonical beta docs and release-truth checks.
- Implement: verify adoption gates:
  - `15` minute quickstart completion budget
  - at least two copy-and-paste starter examples
  - docs-to-working-app path
  - public-import-only examples and presets
  - invocation-only migration path
- Implement: validate `workflow doctor` and `workflow lint` usability on common failure cases and ensure reason-code and plain-English-message parity.
- Implement: verify operator and audit exports, sink-failure handling, portability guidance, and verification guidance.
- Implement: verify evidence signing and integrity compatibility with workflow artifacts, including optional chaining when enabled.
- Implement: sanity-check optional structured events, optional metrics, and optional OpenTelemetry mapping surfaces without making them release-critical for the base install.
- Implement: update package metadata to `0.9.0` and classify the release as Beta.
- Implement: publish beta notes, changelog updates, and explicit statement that the `1.x` stability promise begins only at `1.0.0`.
- Tests: full CI matrix, coverage gate, package smoke, doc parity, API snapshot, quickstart smoke, example smoke, export verification, workflow integration suite.
- Exit: `v0.9.0` is publishable as a feature-complete beta that is adoption-ready, operator-ready, and free of contract ambiguity.

## Parallelization Plan

- Steps 1 through 6 are sequential and must merge in order.
- Step 7 starts immediately after Step 6 and is the first mandatory adoption checkpoint; it should land before Step 8 and before later public-surface expansion.
- Step 8 is sequential after Step 7 because the workflow engine must emit stable reason codes consumed by later doctor and export tooling.
- Steps 9 and 10 may run in parallel after Step 8 stabilizes the shared event model, preset and session-builder outputs, and failure-reason contract.
- Step 11 may start once the workflow engine is stable, but final adapter-specific hook coverage should wait for Steps 9 and 10.
- Step 12 may run in parallel with Step 11 after the workflow artifact, hook result schema, and structured event contract are stable.
- Step 13 should begin from the assets started in Step 7, but final docs polishing and migration copy should wait until Steps 11 and 12 lock public commands, exports, diagnostics, and observability semantics.
- No parallel worker may edit shared workflow schema, shared workflow types, public exports, or public starter asset shapes without rebasing onto the latest merged core.

## Security Acceptance Criteria

- Missing required protocol evidence always fails closed.
- Workflow composition can only narrow permissions, never widen them implicitly.
- Bedrock governed handoffs require alias-backed identity.
- A2A validation uses actual 1.0 compatibility and wire-state rules.
- External protocol evidence is treated as untrusted until validated against the relevant in-scope adapter contract.
- Provider metadata is treated as descriptive unless policy explicitly marks validated host-backed evidence authoritative.
- Session tokens are single-use and workflow-bound.
- External raw payloads are not persisted by default.
- Typed hook outcomes are deterministic, versioned, and auditable.
- Protocol-boundary normalization never relies on descriptive names alone.
- Approval checkpoints and validator outcomes are auditable and deterministic.
- Stronger evidence-integrity guarantees are preserved when signing or tamper-evident chaining is enabled.
- Optional adapters and optional observability surfaces do not weaken the core install path or core security guarantees.

## Adoption Acceptance Criteria

- Existing invocation-only users do not need rewrites to remain on supported APIs.
- Workflow evidence is additive and optional for users who do not adopt workflow governance.
- Base install remains small; adapter dependencies are optional extras.
- A new adopter can complete a workflow quickstart in `15` minutes or less using only public APIs.
- At least two public starter examples are copy-and-paste usable.
- `aigc policy init` and `aigc workflow init` produce working scaffolds for `minimal`, `standard`, and `regulated-high-assurance`.
- `aigc workflow doctor` explains common block reasons clearly in plain English and stable machine-readable reason codes.
- Every public example, preset, and adoption asset passes without `_internal` imports.
- Invocation-only to workflow migration is documented and tested.
- The docs-to-working-app path passes from a clean environment.

## Release Gates

`v0.9.0` beta gate:

- one canonical implementation plan is active and stale plan truth is CI-enforced as superseded or historical
- release-truth checks are green against live repo facts
- workflow artifact schema, integrity metadata, and invocation backward compatibility are locked
- workflow engine, Bedrock adapter, and A2A adapter all pass fixture-only test suites
- restrictive composition tests verify that permission-bearing fields such as `allowed_agent_roles` narrow rather than widen
- Bedrock strong-binding tests verify that name-only collaborator evidence is insufficient where policy requires authoritative identity and that ambiguous identity fails closed
- A2A boundary tests verify acceptance of normative `TASK_STATE_*` wire values and rejection of shorthand boundary values
- `15` minute quickstart budget is met and the docs-to-working-app smoke path passes
- at least two copy-and-paste starter examples are green and use only public imports
- `aigc policy init`, `aigc workflow init`, `aigc workflow doctor`, `aigc workflow lint`, `aigc workflow trace`, and `aigc workflow export` pass snapshot and UX validation
- doctor and lint diagnostics explain common block reasons clearly
- operator and audit export verification passes, including sink-failure reporting and integrity verification guidance
- optional observability and event surfaces pass sanity tests and do not affect the base install
- public API and CLI snapshot tests are green
- doc parity covers the canonical beta docs

`v1.0.0` promotion gate:

- minimum `14` day soak on `v0.9.x`
- zero open P0 or P1 correctness or security defects
- at least two adopter validations of the public workflow surface
- no unresolved API snapshot drift
- no pending migration-breaking changes

## Non-Goals for `v0.9.0`

- No SDK-owned network transport, remote session manager, or distributed infrastructure repositioning
- No hidden orchestration engine or transport ownership
- No model-serving runtime, Rust core, Rust or Tonic gateway rewrite, inference scheduler, or speculative decoding optimization
- No Wasm plugin runtime or plugin execution sandbox
- No deterministic inference replay or exfiltration-research feature train
- No multimodal generation, video, or text-to-video orchestration
- No benchmark-driven release platform claims beyond normal correctness, latency sanity, and CI coverage

## Bottom Line

- `v0.9.0` should ship as a secure, adoption-ready, operator-usable workflow governance beta.
- The release should stay narrow enough to land cleanly in the existing SDK, practical enough to adopt through public quickstarts and scaffolding, and strict enough to block protocol drift, identity ambiguity, and stale release truth early.
- Provider and protocol support must stay honest: Bedrock support is tiered, A2A support is scoped to in-scope 1.0 bindings, and neither adapter overclaims hidden orchestration guarantees.
- Anything that turns AIGC into a broader AI platform belongs in a different roadmap.
