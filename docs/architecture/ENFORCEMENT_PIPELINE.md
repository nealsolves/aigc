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
when: enterprise_customer
then:
  require:
    pii_scan: true
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
  web_search:
    max_calls: 2
```

Violations fail immediately.

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

## Plugin Extension Points

Custom enforcement gates may run at two extension points:

* `PRE_SCHEMA`
* `POST_SCHEMA`

Custom gates may:

* add failures
* add metadata

Custom gates may not:

* remove failures
* bypass enforcement stages

---

## Workflow Governance (Future)

Future releases introduce workflow governance.

A GovernanceSession will manage:

* step sequencing
* cross-invocation policy enforcement
* tool budgets
* workflow audit artifacts
