# AIGC Extended Policy DSL Specification

**Version:** `1.0.0`  
**Status:** Draft

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

Save as:
`schemas/policy_dsl.schema.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "AIGC Extended Policy DSL Schema",
  "type": "object",
  "properties": {
    "policy_version": { "type": "string" },
    "description": { "type": "string" },
    "roles": {
      "type": "array",
      "items": { "type": "string" }
    },
    "conditions": {
      "type": "object",
      "additionalProperties": {
        "type": "object",
        "properties": {
          "type": { "type": "string", "enum": ["boolean"] },
          "required": { "type": "boolean" },
          "default": {}
        }
      }
    },
    "tools": {
      "type": "object",
      "properties": {
        "allowed_tools": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "name": { "type": "string" },
              "max_calls": { "type": "integer" }
            },
            "required": ["name", "max_calls"]
          }
        }
      }
    },
    "retry_policy": {
      "type": "object",
      "properties": {
        "max_retries": { "type": "integer" },
        "backoff_ms": { "type": "integer" }
      }
    },
    "pre_conditions": {
      "type": "object",
      "properties": {
        "required": {
          "type": "array",
          "items": { "type": "string" }
        },
        "optional": {
          "type": "array",
          "items": { "type": "string" }
        }
      }
    },
    "post_conditions": {
      "type": "object",
      "properties": {
        "required": {
          "type": "array",
          "items": { "type": "string" }
        },
        "optional": {
          "type": "array",
          "items": { "type": "string" }
        }
      }
    },
    "guards": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "when": {
            "type": "object",
            "properties": {
              "condition": { "type": "string" }
            },
            "required": ["condition"]
          },
          "then": {
            "type": "object"
          }
        }
      }
    }
  },
  "required": ["policy_version", "roles"]
}
```
