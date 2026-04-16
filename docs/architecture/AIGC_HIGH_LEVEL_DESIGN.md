# AIGC High-Level Design

**Auditable Intelligence Governance Contract**

Version: 1.0.0 | Status: Target-State Design | Last Updated: 2026-04-13

---

## 1. Executive Summary

AIGC (Auditable Intelligence Governance Contract) is a Python SDK for
fail-closed governance of AI behavior at runtime. In the 1.0.0 target design,
AIGC governs both individual invocation attempts and multi-step workflows while
preserving the existing invocation enforcement kernel.

AIGC remains an SDK. It is not a hosted platform, not an orchestrator, not a
protocol runtime, and not a replacement for the host application's business
logic.

One-line rule: the host performs actions; AIGC governs whether they are allowed
and emits evidence.

Availability boundary: this document describes the intended `1.0.0` public
surface. The shipped `0.3.3` package and CLI do not yet export
`GovernanceSession`, `SessionPreCallResult`, `AgentIdentity`,
`AgentCapabilityManifest`, `ValidatorHook`, `BedrockTraceAdapter`,
`A2AAdapter`, or `aigc workflow ...` commands, and `AIGC.open_session(...)`
is not part of the installable runtime yet.

Headline 1.0.0 capabilities:

- `GovernanceSession`
- workflow policy DSL
- `AgentIdentity` and `AgentCapabilityManifest`
- escalation checkpoints
- `ValidatorHook`
- workflow CLI (`trace`, `export`, `lint`)
- optional Bedrock adapter
- optional A2A adapter

```text
+--------------------------------------------------------------------------------+
| Host Application                                                               |
|                                                                                |
|  orchestration | model calls | tool execution | transport | business logic     |
|                                                                                |
|  +-------------------------+      +-----------------------------------------+  |
|  | Optional Adapters       | ---> | AIGC Workflow Governance Layer          |  |
|  | - BedrockTraceAdapter   |      | - GovernanceSession                     |  |
|  | - A2AAdapter            |      | - workflow DSL + manifests              |  |
|  +-------------------------+      | - handoffs, budgets, escalation         |  |
|                                   +-------------------+---------------------+  |
|                                                       |                        |
|                                                       v                        |
|                                   +-----------------------------------------+  |
|                                   | AIGC Invocation Governance Kernel       |  |
|                                   | - policy load + validation              |  |
|                                   | - ordered gates                         |  |
|                                   | - unified + split enforcement           |  |
|                                   +-------------------+---------------------+  |
|                                                       |                        |
|                        provider, tool, and protocol interactions remain       |
|                        host-owned; AIGC governs and evidences them            |
|                                                                                |
|  outputs: invocation artifacts + workflow artifacts + operator exports         |
+--------------------------------------------------------------------------------+
```

---

## 2. Goals and Non-Goals

### Goals

AIGC 1.0.0 is designed to provide:

- deterministic invocation governance at every invocation boundary
- first-class workflow governance for multi-step agentic systems
- additive evidence correlation across invocation and workflow scopes
- provider-agnostic normalization adapters for external workflow ecosystems
- a stronger adoption surface through stable public APIs, CLI tooling, starter
  policies, and recipes
- explicit boundary discipline so workflow support does not collapse into
  platform ownership

### Non-Goals

AIGC 1.0.0 does not:

- host agents, tools, or workflows as a managed runtime
- run an HTTP server or own protocol transport implementations
- execute tools on behalf of the host application
- own model-provider credentials, retries, auth flows, or TLS operations
- persist application business state beyond emitted governance evidence
- replace application authorization systems or vertical business rules
- ship cloud-specific required dependencies in the core path
- become a reference application for a specific provider, framework, or domain

AIGC 1.0.0 preserves the invocation kernel and extends it with workflow
primitives. It does not replace the invocation model with a new runtime.

---

## 3. Design Principles

| Principle | Meaning |
| --------- | ------- |
| **Governance is data, not code** | Policies and manifests are declarative contracts validated before runtime decisions are trusted. |
| **Fail-closed by default** | Missing context, invalid schemas, disallowed roles, disallowed transitions, or missing required protocol evidence all block progress. |
| **Deterministic decisions and evidence** | The same policy, normalized inputs, and governance state yield the same enforcement outcome and the same stable evidence fields. |
| **Audit is mandatory** | Every invocation attempt emits one invocation artifact, and every terminal session (`COMPLETED`, `FAILED`, or `CANCELED`) or session explicitly finalized from `OPEN` / `PAUSED` emits workflow evidence. |
| **Boundary discipline** | The host owns orchestration and execution; AIGC owns governance and evidence. |
| **Workflow governance wraps invocation governance** | Workflow checks constrain when steps may occur; invocation checks still govern each individual step. |
| **Additive schema evolution** | Existing invocation artifact contracts remain backward-compatible; workflow evidence is additive. |
| **Optional adapters only** | Bedrock and A2A support are integration layers, not required dependencies and not product centerpieces. |
| **Provider-agnostic core** | Core governance semantics are not owned by any single model provider, agent framework, or protocol. |
| **Schema-first contracts** | DSL fields, artifact fields, manifests, and operator outputs are defined as explicit schemas before they are treated as public contract. |

---

## 4. SDK Boundary and System Context

AIGC sits between host intent and host execution. The host decides what to try.
AIGC decides whether that step is policy-valid and what evidence must be
emitted.

### 4.1 Ownership Boundary

| Host Application Owns | AIGC Owns |
| --------------------- | --------- |
| orchestration and control flow | policy loading and validation |
| model calls and provider credentials | ordered invocation governance |
| tool execution | workflow and session governance |
| protocol transport | handoff, transition, and budget constraints |
| identity and auth flows | escalation and approval checkpoints |
| persistence beyond governance evidence | invocation and workflow evidence generation |
| UI and operator experience | workflow trace, export, and lint utilities |
| business logic and domain state | normalized governance decisions |

### 4.2 Invocation Boundary vs Workflow Boundary

```text
Invocation Boundary
-------------------
host prepares one invocation attempt
  -> AIGC validates policy + role + conditions + tools + output contract
  -> AIGC emits one invocation artifact

Workflow Boundary
-----------------
host coordinates many invocation attempts and handoffs
  -> AIGC tracks governance session state
  -> AIGC enforces sequencing, participant, protocol, budget, and escalation rules
  -> AIGC correlates invocation artifacts into workflow evidence
```

Workflow governance is stateful inside AIGC, but only for governance state.
AIGC tracks session identifiers, step progress, approvals, budgets, and
correlated evidence. It does not become the system of record for domain or
business state.

---

## 5. Core Public Abstractions

| Surface | Purpose | Public Ownership | Does Not Own |
| ------- | ------- | ---------------- | ------------ |
| `Policy` | Declarative contract for invocation and workflow governance | AIGC public DSL | application orchestration |
| `Invocation` | Structured description of one governed invocation attempt | host supplies, AIGC validates | provider runtime |
| `AIGC` | Instance-scoped SDK entry point for enforcement, sinks, loaders, and workflow sessions | AIGC public API | global app runtime |
| `GovernanceSession` | Stateful workflow-governance primitive coordinating many governed steps | AIGC public API | business state machine |
| `SessionPreCallResult` | Split-mode handoff token scoped to a governed workflow step | AIGC public API | general transport token |
| `AgentIdentity` | Stable identity for a participant in a governed workflow | AIGC public API | provider-specific auth |
| `AgentCapabilityManifest` | Declared capability and protocol contract for a participant | AIGC public API | transport implementation |
| `Audit Artifact` | Immutable evidence for one invocation attempt | AIGC output contract | workflow summary |
| `Workflow Artifact` | Session-level evidence correlated across many invocation artifacts | AIGC output contract | raw provider trace store |
| `ValidatorHook` | Optional extension point for semantic or content validators at workflow boundaries | AIGC public API | core policy kernel |
| `BedrockTraceAdapter` | Optional normalization layer from Bedrock collaborator and trace evidence into AIGC workflow events | AIGC optional adapter API | AWS runtime ownership |
| `A2AAdapter` | Optional normalization layer from A2A cards, envelopes, and task updates into AIGC workflow events | AIGC optional adapter API | A2A transport ownership |

Supporting primitives remain available, but they are not the center of the
1.0.0 design:

- `AuditLineage` reconstructs relationships from stored artifacts
- `ProvenanceGate` enforces source-presence requirements inside the invocation
  kernel
- `RiskHistory` tracks advisory risk trajectories over time

---

## 6. Invocation Governance Kernel

The invocation kernel remains the stable core of AIGC.

Its responsibilities are unchanged:

- load and validate the effective policy
- resolve conditions and guards
- enforce ordered authorization and output-side gates
- preserve fail-closed behavior
- emit exactly one invocation artifact per invocation attempt

The gate-order invariant remains unchanged. Authorization-side checks still run
before output-side checks, and split enforcement still preserves the same gate
semantics across pre-call and post-call phases.

### 6.1 Invocation Modes

- **Unified enforcement**: one call governs a full invocation attempt end to
  end.
- **Split enforcement**: pre-call enforcement authorizes the attempt before the
  model call; post-call enforcement validates output after the model returns.
- **Workflow-composed split enforcement**: `SessionPreCallResult` carries the
  split-mode handoff token inside a `GovernanceSession` so step-level workflow
  constraints and per-invocation constraints compose without changing kernel
  semantics.

### 6.2 Kernel Summary

```text
policy load -> guard/condition resolution -> role/precondition/tool checks
-> output schema/postcondition/risk checks -> invocation artifact emission
```

The detailed gate ordering, insertion points, and failure taxonomy remain in
[ENFORCEMENT_PIPELINE.md](ENFORCEMENT_PIPELINE.md).

---

## 7. Workflow Governance Model

Workflow governance is the architectural center of AIGC 1.0.0.

`GovernanceSession` governs a workflow as a sequence of authorized steps,
participant handoffs, approvals, and evidence-correlation events. The host
still drives orchestration; the session decides whether each next step is
allowed under declared policy.

Workflow adoption remains instance-scoped through `AIGC.open_session(...)`.
The target design does not add a module-level `open_session(...)` convenience.

### 7.1 Session Lifecycle

Canonical lifecycle states:

- `OPEN`
- `PAUSED`
- `FAILED`
- `COMPLETED`
- `CANCELED`
- `FINALIZED`

Canonical serialized workflow artifact `status` values:

- `COMPLETED`
- `FAILED`
- `CANCELED`
- `INCOMPLETE`

State-to-status mapping at emission:

| Lifecycle condition when the workflow artifact is emitted | Serialized `status` |
| --------------------------------------------------------- | ------------------- |
| `COMPLETED` | `COMPLETED` |
| `FAILED` | `FAILED` |
| `CANCELED` | `CANCELED` |
| `OPEN` or `PAUSED` finalized without terminal completion | `INCOMPLETE` |

Rules:

- `FINALIZED` is a lifecycle state only. It is never serialized as a workflow
  artifact `status`.
- `INCOMPLETE` is a workflow artifact `status` only. It is never a live session
  lifecycle state.
- `OPEN` and `PAUSED` are in-memory lifecycle states until the host either
  resumes work or finalizes the session.
- After a workflow artifact is emitted from `COMPLETED`, `FAILED`,
  `CANCELED`, or finalization from `OPEN` / `PAUSED`, the session closes into
  `FINALIZED`.

```text
            +--------+
            |  OPEN  |
            +--------+
             |   |   \
 authorize    |   |    \ fail
 and record   |   |     \
 steps        |   |      v
             pause |   +--------+
               v   |   | FAILED |
          +---------+  +--------+
          | PAUSED  |      |
          +---------+      |
             |   ^         |
          resume  |        |
             v    |        |
            +--------+     |
            |  OPEN  |-----+
            +--------+
                 |
      complete or cancel
          /            \
         v              v
   +-----------+   +-----------+
   | COMPLETED |   | CANCELED  |
   +-----------+   +-----------+
          \            /
           \          /
            v        v
            +----------+
            | FINALIZED|
            +----------+
```

### 7.2 Step Semantics

Each governed step has four distinct phases:

1. **registration**: the host declares the intended step, participant, and
   protocol context
2. **authorization**: AIGC validates transitions, participant identity,
   protocol constraints, budgets, and escalation rules
3. **completion**: the host provides invocation output or normalized external
   evidence, and AIGC binds the step to invocation evidence
4. **correlation**: the session stores the invocation artifact checksum and the
   normalized workflow event so the final workflow artifact is deterministic

### 7.3 Workflow Invariants

- one workflow can govern many invocation attempts
- workflow governance never bypasses invocation governance
- terminal sessions and explicit finalization from `OPEN` / `PAUSED` emit deterministic workflow evidence
- paused or failed sessions reject new steps unless resumed under policy
- handoffs are governed as explicit workflow events, not implied side effects
- workflow evidence summarizes and correlates invocation evidence; it does not
  replace it

### 7.4 Session Sequence

```text
Host                GovernanceSession         Invocation Kernel          Evidence
----                -----------------         -----------------          --------
AIGC.open_session() ---> OPEN
authorize step ---> validate transition and participant
                    -----------------------> enforce pre-call or unified checks
Host performs action ------------------------------------------------->
complete step ----> correlate invocation checksum and normalized event
finalize() -------> assemble workflow artifact -----------------------> emit
```

---

## 8. Policy DSL and Manifest Architecture

The 1.0.0 target design extends the existing policy DSL with explicit workflow
sections. Workflow participants are explicit and stable by `id`; they are not
role-only abstractions.

### 8.1 Workflow DSL Fields

| Field | Purpose |
| ----- | ------- |
| `participants` | Declares the stable workflow participants, their roles, allowed protocols, and manifest references |
| `max_steps` | Sets an upper bound on session step count |
| `max_total_tool_calls` | Caps aggregate tool usage across the workflow |
| `required_sequence` | Declares workflow steps that must occur in order |
| `allowed_transitions` | Declares valid next-step transitions |
| `allowed_agent_roles` | Restricts the set of roles that may participate in the workflow |
| `handoffs` | Declares which participants may hand work to which other participants and under which protocols or capability requirements |
| `escalation` | Declares when review or approval checkpoints are required |
| `protocol_constraints` | Declares Bedrock- and A2A-specific evidence and protocol requirements without putting transport logic into core governance |

### 8.2 `AgentCapabilityManifest` Fields

| Field | Purpose |
| ----- | ------- |
| `participant_id` | Stable participant identifier used in workflow policy |
| `role` | Declared governance role for the participant |
| `protocols` | Supported protocol families such as local, Bedrock, or A2A |
| `capabilities` | Declared action or tool capability set used for handoff validation |
| `version` | Manifest version identifier for compatibility tracking |
| protocol-specific identity fields | Provider or protocol identity needed for adapter binding, such as collaborator aliases or A2A agent-card identity |

### 8.3 High-Level Composition Rules

Workflow composition stays declarative and conservative:

- participants merge by stable `id`
- role sets compose by restriction, not implicit expansion
- transition and handoff rules must remain explicit after composition
- protocol constraints compose by named protocol section
- any ambiguity that weakens governance fails validation rather than choosing a
  permissive default

---

## 9. Evidence Architecture

AIGC 1.0.0 distinguishes between invocation evidence and workflow evidence.

### 9.1 Invocation Artifact

Invocation artifacts remain the per-attempt evidence contract.

They continue to provide:

- one artifact per invocation attempt
- deterministic pass/fail evidence
- gate and failure context
- provenance and correlation metadata

Invocation artifacts remain backward-compatible. The 1.0.0 target design only
adds workflow correlation metadata needed to bind an invocation artifact into a
session.

### 9.2 Workflow Artifact

Workflow artifacts are separate session-level evidence.

They summarize:

- workflow and session identifiers
- participants and manifests
- step sequence and state transitions
- handoffs and protocol usage
- approvals and denials
- invocation artifact checksums referenced by the workflow
- final workflow status and failure summary

### 9.3 Correlation Model

```text
+---------------------------+
| Workflow Artifact         |
| session_id                |
| participants              |
| steps                     |
| handoffs                  |
| approvals                 |
| invocation checksums      |
+-------------+-------------+
              |
   +----------+----------+-----------+
   |                     |           |
   v                     v           v
+---------+         +---------+  +---------+
| Inv A   |         | Inv B   |  | Inv C   |
| PASS    |         | FAIL    |  | PASS    |
| checksum|         | checksum|  | checksum|
+---------+         +---------+  +---------+
```

`AuditLineage` remains a consumer utility over emitted artifacts. It is useful
for offline reconstruction and DAG traversal, but it is not the primary
workflow evidence mechanism in the 1.0.0 design.

Operator tooling sits above emitted evidence:

- `aigc workflow trace`
- `aigc workflow export`
- `aigc workflow lint`

---

## 10. Adapter Architecture

Adapters normalize external workflow or protocol evidence into AIGC-native
workflow events. They are optional integration layers. They do not own
transport, auth, retries, orchestration, or provider runtimes.

### 10.1 Bedrock Adapter

`BedrockTraceAdapter` consumes host-supplied collaborator metadata and parsed
Bedrock `TracePart` payloads, then normalizes them into workflow events.

| Bedrock Evidence | Normalized Meaning |
| ---------------- | ------------------ |
| `collaboratorName` | participant binding |
| `callerChain` | upstream provenance metadata |
| `InvocationInput.invocationType=AGENT_COLLABORATOR` | handoff requested |
| `Observation.type=AGENT_COLLABORATOR` | handoff completed |
| `Observation.type=ACTION_GROUP` | tool observed |
| `Observation.type=KNOWLEDGE_BASE` | knowledge observed |
| `FailureTrace` | workflow failed |

Design rules:

- `relayConversationHistory` is governed as workflow policy evidence, not as
  transport logic
- when policy requires trace, Bedrock trace is mandatory and missing trace
  fails closed
- alias-backed collaborator identity is required for governed participant
  binding; `collaboratorName` alone is descriptive evidence only
- collaborator identity is validated against workflow participants and
  manifests before normalized events are trusted
- no required AWS dependency enters the core path; Bedrock support is optional
  and adapter-scoped

### 10.2 A2A Adapter

`A2AAdapter` targets the stable A2A 1.0 contract and normalizes agent cards,
request envelopes, task updates, and streaming evidence into workflow events.

Supported bindings in 1.0.0:

- `JSONRPC`
- `HTTP+JSON`

Explicitly unsupported in 1.0.0:

- `GRPC`

| A2A Evidence | Normalized Meaning |
| ------------ | ------------------ |
| `AgentCard` | participant and capability validation |
| `SendMessage` / `SendStreamingMessage` | remote handoff start |
| `GetTask` / `SubscribeToTask` | task-state progression |
| `TASK_STATE_INPUT_REQUIRED` / `TASK_STATE_AUTH_REQUIRED` | workflow pause and escalation |
| `TASK_STATE_COMPLETED` | handoff completed |
| `TASK_STATE_FAILED` / `TASK_STATE_REJECTED` / `TASK_STATE_CANCELED` | workflow failure or cancel |

Design rules:

- compatibility is validated from `supportedInterfaces[].protocolVersion`, not
  descriptive Agent Card version text
- Agent Card security schemes and signatures are validated as evidence when
  policy requires them
- OAuth, HTTP auth, TLS, retries, and request delivery remain host
  responsibilities
- SSE ordering is treated as evidence order and must not be reordered by the
  adapter
- non-normative or shorthand task-state names are rejected at the boundary
- unsupported bindings fail with explicit protocol violations rather than being
  silently accepted

---

## 11. Extension Model

AIGC remains extensible, but every extension point is constrained by the same
fail-closed model.

### 11.1 Extension Points

| Extension Point | Purpose | Ordering Constraint |
| --------------- | ------- | ------------------- |
| Custom gates | Add deterministic policy-aware checks at documented insertion points | stay inside the invocation kernel at insertion-point boundaries |
| Validator hooks | Add optional semantic or content validators at workflow step completion | run after invocation validation and before workflow step completion is committed |
| Policy loaders | Resolve policy from alternative sources | must still yield a valid effective policy before enforcement proceeds |
| Audit sinks | Persist emitted artifacts to storage or downstream systems | cannot suppress or bypass governance failures |

### 11.2 Ordering Guarantees

- custom gates remain insertion-point-based within the invocation kernel
- validator hooks attach at the documented workflow step completion boundary
- adapters normalize external evidence before workflow enforcement consumes it
- no extension point may suppress, downgrade, or bypass a governance failure

---

## 12. Security and Trust Model

AIGC treats governance as a trust-boundary problem. The SDK must be explicit
about what it trusts, what it normalizes, and what it refuses to infer.

### 12.1 Core Invariants

- exactly one invocation artifact is emitted per invocation attempt
- workflow artifacts are deterministic and additive
- invocation gate ordering is unchanged
- workflow governance wraps invocation governance
- missing required protocol evidence fails closed
- public integrations must not depend on `aigc._internal`
- adapters cannot become hidden alternate enforcement engines

### 12.2 Trust Boundaries

- host inputs are untrusted until validated against policy and workflow state
- provider and protocol evidence are untrusted until normalized by the relevant
  adapter
- audit and workflow artifacts are the canonical trust outputs of the SDK
- extension points may contribute failures or metadata, but they do not own the
  final governance decision

### 12.3 Adapter Trust Model

Bedrock traces are provider evidence normalized by host-supplied input.
A2A Agent Cards and task envelopes are remote-party evidence normalized by
host-supplied input.
AIGC never treats raw provider or transport state as trusted without explicit
normalization and validation.

---

## 13. Public API, Stability, and Migration

### 13.1 Shipped vs Planned Public Surface

The shipped `0.3.3` public surface remains invocation-scoped.

| Shipped in `0.3.3` | Role today |
| ------------------ | ---------- |
| `AIGC` | instance-scoped entry point for invocation governance |
| `enforce_invocation` | unified invocation governance |
| `enforce_pre_call` / `enforce_post_call` | split invocation governance |
| `PreCallResult` | single-use split handoff for invocation governance |

Planned-only additions for `1.0.0` — not exported by `0.3.3`, not available
in the `0.3.3` CLI, and not safe for current integrations to depend on yet:

| Planned surface (not in `0.3.3`) | Intended role in `1.0.0` |
| -------------------------------- | ------------------------ |
| `GovernanceSession` | workflow governance primitive |
| `SessionPreCallResult` | workflow-scoped split handoff |
| `AgentIdentity` | participant identity contract |
| `AgentCapabilityManifest` | capability and protocol contract |
| `ValidatorHook` | workflow validator extension point |
| `BedrockTraceAdapter` | optional Bedrock normalization adapter |
| `A2AAdapter` | optional A2A normalization adapter |
| workflow CLI commands | operator inspection and export surface |

### 13.2 Stability Contract After `1.0.0` GA

The `1.x` stability promise described here does not apply to the shipped
`0.3.3` artifact. It activates only after `1.0.0` formally ships and the
relevant exports, CLI commands, schema contracts, and contract tests land.

After `1.0.0` GA, the intended stability promise covers:

- documented public exports
- documented CLI commands and flags
- documented policy DSL fields
- documented artifact fields

It does not cover:

- `aigc._internal`
- undocumented helper modules
- internal lifecycle fields
- experimental adapter internals

Before `1.0.0` GA, this document is a design target, not an active
compatibility guarantee for planned-only workflow APIs.

### 13.3 Migration at a High Level

From `0.3.3` to `1.0.0`:

- invocation-only users can stay on invocation governance patterns
- workflow users adopt `GovernanceSession`
- Bedrock and A2A users adopt optional adapters where they need normalized
  external workflow evidence

Detailed migration steps belong in dedicated migration documents rather than in
this architecture reference.

---

## 14. Non-Functional Requirements

AIGC 1.0.0 targets the following release properties:

- Python support `>= 3.10`
- coverage gate `>= 90%`
- optional adapters with minimal core runtime dependencies
- doc parity enforced for canonical user-facing docs
- public API snapshot testing for the documented surface
- schema validation for policies and artifacts in CI
- packaging and install smoke coverage
- example smoke coverage for documented quickstarts and recipes

---

## 15. Glossary

| Term | Meaning |
| ---- | ------- |
| `GovernanceSession` | The workflow-governance primitive that tracks governance state across many governed steps |
| `Workflow Artifact` | Session-level evidence correlated across invocation artifacts |
| `Participant` | A stable actor in a governed workflow, identified by explicit `id` |
| `Manifest` | A capability and protocol contract for a workflow participant |
| `Handoff` | A governed transfer of work between participants |
| `Escalation Checkpoint` | A workflow point that requires approval, denial, or pause/resume handling |
| `Bedrock TracePart` | Provider evidence from Bedrock multi-agent execution normalized by the Bedrock adapter |
| `Agent Card` | Remote-agent description used by the A2A adapter for identity and capability validation |
| `TaskState` | Normalized remote task status used by workflow enforcement for pause, failure, completion, and escalation behavior |
| `Validator Hook` | An optional extension point for semantic or content validation at workflow step boundaries |
