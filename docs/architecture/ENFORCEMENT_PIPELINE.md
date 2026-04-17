# AIGC Enforcement Pipeline

This document describes how governance enforcement occurs for every AI invocation.

The enforcement pipeline is deterministic and fail-closed.

---

## High Level Flow

Split enforcement is the default since `v0.3.3`: `@governed` runs Phase A
(authorization gates) before the model call and Phase B (output gates) after.
Unified mode (`enforce_invocation`) is retained as a direct API and as a
deprecated opt-out via `pre_call_enforcement=False` on `@governed`.

```
Application
│
├─ split mode (default for @governed)
│  ▼
│  Phase A / enforce_pre_call
│  ▼
│  Policy Load -> pre_authorization -> Guard Evaluation -> Role Validation
│  -> Precondition Validation -> Tool Constraint Validation -> post_authorization
│  ▼
│  Model Call Boundary
│  ▼
│  Phase B / enforce_post_call
│  ▼
│  pre_output -> Output Schema Validation -> Postcondition Validation
│  -> post_output -> Risk Scoring -> Audit Artifact Generation
│
└─ unified mode (direct API / deprecated opt-out)
│  ▼
│  AIGC Enforcement Engine
│  ▼
│  Policy Load
│  ▼
│  pre_authorization custom gates
│  ▼
│  Guard Evaluation
│  ▼
│  Role Validation
│  ▼
│  Precondition Validation
│  ▼
│  Tool Constraint Validation
│  ▼
│  post_authorization custom gates
│  ▼
│  pre_output custom gates
│  ▼
│  Output Schema Validation
│  ▼
│  Postcondition Validation
│  ▼
│  post_output custom gates
│  ▼
│  Risk Scoring (if configured)
│  ▼
│  Audit Artifact Generation
```

---

## Pipeline Stages

### 1. Policy Load

The enforcement engine loads the policy file.

Policy validation includes:

* YAML parsing
* JSON Schema validation
* policy composition
* guard expansion

Invalid policies fail immediately.

---

### 2. Guard Evaluation

Conditional guards expand the effective policy.

Example:

```yaml
guards:
  - when:
      condition: "is_enterprise"
    then:
      pre_conditions:
        required:
          - enterprise_flag
```

Guards only add constraints.

They never remove them.

---

### 3. Role Validation

Role authorization determines whether the invocation may proceed.

Example:

```yaml
roles:
  - planner
  - analyst
```

Unlisted roles are rejected.

---

### 4. Precondition Validation

Preconditions validate the invocation context.

Examples:

* session id format
* tenant id presence
* authorization tokens

Typed validation is preferred. Legacy bare-string preconditions are still
supported but deprecated; a `DeprecationWarning` is emitted at runtime.

Key existence alone is insufficient for typed preconditions.

---

### 5. Tool Constraint Validation

Tool constraints restrict external system access.

Example:

```yaml
tools:
  allowed_tools:
    - name: "web_search"
      max_calls: 2
```

Violations raise `ToolConstraintViolationError` with a FAIL audit artifact.

Tool validation occurs before schema validation.

---

### 6. Output Schema Validation

Model output must match the required structure.

Example:

```json
{
  "type": "object",
  "required": ["result"]
}
```

Invalid output fails governance.

---

### 7. Postcondition Validation

Postconditions verify the final output.

Examples:

* score thresholds
* data completeness
* workflow constraints

Postconditions execute after schema validation.

---

### 8. Audit Artifact Generation

Every enforcement emits a structured artifact.

Artifacts include:

* enforcement result
* failure gate
* metadata
* checksums

Both PASS and FAIL artifacts are emitted.

---

## Pre-Action Boundary Proof

Audit artifacts record the ordered gates that ran before the call boundary.

* Unified mode uses `metadata.gates_evaluated`.
* Split mode uses `metadata.pre_call_gates_evaluated` and, when Phase B runs,
  `metadata.post_call_gates_evaluated`.

Unified example:

Example:

```json
[
  "guard_evaluation",
  "role_validation",
  "precondition_validation",
  "tool_constraint_validation"
]
```

This proves enforcement occurred before action. In split mode, the Phase A list
is the explicit proof that the authorization-side gates completed before the
wrapped model call executed.

---

## Custom Enforcement Gates

Custom enforcement gates allow plugins to inject additional governance checks
at defined points in the pipeline. Available since v0.3.0. In split enforcement
mode (v0.3.2+), custom gates are carried across the pre/post boundary and run
during Phase B (`pre_output`, `post_output`) as they do in unified mode.

Gates implement the `EnforcementGate` ABC and return `GateResult` objects.

### Insertion Points

* `pre_authorization` — runs before guard evaluation and role/precondition checks
* `post_authorization` — runs after precondition validation, before output-processing stages
* `pre_output` — runs before output schema validation and postcondition checks
* `post_output` — runs after postcondition validation, before audit artifact generation

### Gate Contract

Gates receive immutable views of the policy and invocation. Any attempt to
mutate these objects is converted into a gate failure.

Custom gates may:

* add failures
* add metadata

Custom gates may NOT:

* remove failures
* bypass enforcement stages

---

## Built-In Enforcement Gates

Built-in gates ship with the SDK and can be registered alongside custom gates.

### ProvenanceGate (v0.3.3+)

`ProvenanceGate` runs at the `pre_output` insertion point and blocks
invocations whose runtime context lacks provenance source identifiers.
Provenance from `invocation["context"]["provenance"]` is also forwarded
into every audit artifact (PASS and FAIL), enabling `AuditLineage` to
traverse cross-invocation lineage.

Registration:

```python
from aigc import AIGC, ProvenanceGate
aigc = AIGC(custom_gates=[ProvenanceGate()])
```

Failure codes:

* `PROVENANCE_MISSING` — no provenance in `invocation["context"]`, value
  is None/empty, or value is not a Mapping.
* `SOURCE_IDS_MISSING` — provenance exists but `source_ids` is absent,
  empty, or not a list.

---

## Workflow Governance (Planned `1.0.0` Target State)

The shipped `0.3.3` runtime remains invocation-scoped. Its provenance, lineage,
and risk-history additions are groundwork for the upcoming unreleased v0.9.0-beta
line, which will ship the initial `GovernanceSession` primitive. The currently
shipped package remains `v0.3.3`.

A `GovernanceSession` will manage:

* step sequencing
* cross-invocation policy enforcement
* tool budgets
* workflow audit artifacts

These features are tracked in the Architecture Redesign Roadmap.
