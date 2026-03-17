# AIGC Extended Policy DSL Specification

**Version:** `1.0.0`
**Status:** Authoritative

This document defines the extended policy DSL used by the AIGC Governance SDK.
It is written for humans, language models, and enforcement agents.

## Scope

This DSL governs:

- role authorization
- precondition and postcondition checks
- conditional guard logic
- tool usage constraints
- retry behavior

The DSL is data, not executable policy code.

## Design Intent

The format is intentionally:

- machine-parseable
- human-readable
- deterministic at enforcement time
- schema-validatable

## Top-Level Structure

```yaml
policy_version: "1.0"
description: "Optional human-readable policy intent"

roles:
  - planner
  - verifier
  - synthesizer

conditions:
  is_enterprise:
    type: boolean
    required: false
    default: false

tools:
  allowed_tools:
    - name: "vector_search"
      max_calls: 2

retry_policy:
  max_retries: 2
  backoff_ms: 500

pre_conditions:
  required:
    - role_declared
    - schema_exists
  optional:
    - is_enterprise

post_conditions:
  required:
    - output_schema_valid

guards:
  - when:
      condition: "is_enterprise"
    then:
      pre_conditions:
        required:
          - enterprise_flag
      post_conditions:
        required:
          - audit_level_high
```

## Field Semantics and Intent

### `policy_version`

Intent: Provide explicit version control for policy evolution.

- Required
- Should follow semantic versioning for compatibility tracking

### `description`

Intent: Record policy purpose for maintainers and auditors.

- Optional
- Recommended for policy governance clarity

### `roles`

Intent: Declare the full role allowlist for the policy boundary.

- Required
- Invocations with undeclared roles must fail enforcement

### `conditions`

Intent: Define named context-driven booleans used by guards.

- Optional
- Values are resolved from invocation context at runtime

Example:

```yaml
conditions:
  premium_enabled:
    type: boolean
    default: false
```

### `tools`

Intent: Constrain tool proposals in model output.

- Optional
- Each tool may define per-invocation call caps

Example:

```yaml
tools:
  allowed_tools:
    - name: "calculate_metrics"
      max_calls: 3
```

### `retry_policy`

Intent: Bound retries to deterministic and auditable behavior.

- Optional
- Retries must be explicit and finite
- Silent retry loops are not allowed

### `pre_conditions` and `post_conditions`

Intent: Define baseline validation gates before and after invocation.

- `required`: must be satisfied
- `optional`: may be used by downstream logic or guards

Preconditions support two formats:

**Typed preconditions** (recommended):

```yaml
pre_conditions:
  required:
    tenant_id:
      type: string
      pattern: "^[A-Z0-9]{8}$"
    score:
      type: number
      minimum: 0
      maximum: 1
```

**Legacy bare-string preconditions** (deprecated):

```yaml
pre_conditions:
  required:
    - role_declared
    - schema_exists
```

Bare-string preconditions emit a `DeprecationWarning` at runtime. Typed
preconditions enforce value constraints (type, pattern, enum, min/max) beyond
key existence.

### `guards`

Intent: Apply conditional policy expansions based on runtime context.

- Evaluated in listed order
- Guard effects should be additive and explicit

Example:

```yaml
guards:
  - when:
      condition: "role == verifier"
    then:
      post_conditions:
        required:
          - verified_signature
```

## Common Use Patterns

### Role-Specific Hardening

```yaml
guards:
  - when:
      condition: "role == verifier"
    then:
      post_conditions:
        required:
          - verified_signature
```

Intent: Add stricter output guarantees for verification workflows.

### Tool-Cap Governance

```yaml
tools:
  allowed_tools:
    - name: "fetch_data"
      max_calls: 1
```

Intent: Prevent excessive tool usage and enforce bounded cost/risk.

### Feature Gating

```yaml
guards:
  - when:
      condition: "premium_enabled"
    then:
      post_conditions:
        required:
          - advanced_proof
```

Intent: Activate stricter checks only when feature flags are enabled.

## Validation and Provenance Requirements

Every policy change should be:

- versioned
- linked to a decision record
- regression-tested with golden replays

The DSL should be validated against:
`schemas/policy_dsl.schema.json`

## JSON Schema Reference

The canonical schema is `schemas/policy_dsl.schema.json`. Always validate
policies against that file. Do not rely on inline copies, which may lag
behind the canonical schema.

Top-level properties defined in the canonical schema (v0.3.0):

- `extends` — path to base policy for composition
- `composition_strategy` — merge strategy: `intersect`, `union`, `replace`
- `policy_version` — version string (required)
- `description` — human-readable description
- `effective_date` — activation date (`YYYY-MM-DD`)
- `expiration_date` — expiration date (`YYYY-MM-DD`)
- `roles` — allowed roles (required, non-empty array)
- `conditions` — typed boolean conditions for guards
- `tools` — tool constraints (`allowed_tools` with `name`/`max_calls`)
- `retry_policy` — retry configuration (`max_retries`, `backoff_ms`)
- `risk` — risk scoring configuration (`mode`, `threshold`, `factors`)
- `pre_conditions` — preconditions (typed dict or legacy bare-string list)
- `post_conditions` — postconditions
- `output_schema` — JSON Schema for output validation
- `guards` — conditional policy activation rules
