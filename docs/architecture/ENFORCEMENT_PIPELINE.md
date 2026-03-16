# AIGC Enforcement Pipeline

This document describes how governance enforcement occurs for every AI invocation.

The enforcement pipeline is deterministic and fail-closed.

---

## High Level Flow

```
Application
│
▼
AIGC Enforcement Engine
│
▼
Policy Load
│
▼
Guard Evaluation
│
▼
Role Validation
│
▼
Precondition Validation
│
▼
Tool Constraint Validation
│
▼
Output Schema Validation
│
▼
Postcondition Validation
│
▼
Audit Artifact Generation
│
▼
Result Returned
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

Typed validation is required.

Key existence alone is insufficient.

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

Audit artifacts contain:

`metadata.gates_evaluated`

Example:

```json
[
  "guard_evaluation",
  "role_validation",
  "precondition_validation",
  "tool_validation"
]
```

This proves enforcement occurred before action.

---

## Custom Enforcement Gates

Custom enforcement gates allow plugins to inject additional governance checks
at defined points in the pipeline. Available since v0.3.0.

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

## Workflow Governance (Planned)

Future releases will introduce workflow governance.

A `GovernanceSession` will manage:

* step sequencing
* cross-invocation policy enforcement
* tool budgets
* workflow audit artifacts

These features are tracked in the Architecture Redesign Roadmap.
