# AIGC High-Level Design

**Auditable Intelligence Governance Contract**

Version: 1.0.0 | Status: Authoritative | Last Updated: 2026-02-16

---

## 1. Executive Summary

AIGC (Auditable Intelligence Governance Contract) is a Python SDK that enforces
deterministic governance over AI model invocations. It sits between the caller
and the model, ensuring every invocation is policy-governed, schema-validated,
and produces a tamper-evident audit artifact — regardless of which model,
provider, or orchestration framework is used.

AIGC is designed to be portable across any system that invokes AI models.

```text
┌──────────────────────────────────────────────────────────────────┐
│                       Calling System                             │
│                                                                  │
│   invoke model ──▶ ┌──────────────────────────┐ ──▶ audit record │
│                    │   AIGC Governance SDK     │                  │
│                    │                           │                  │
│                    │  policy ─▶ enforce ─▶ audit│                 │
│                    └──────────────────────────┘                  │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. Problem Statement

Agentic AI systems make autonomous decisions: selecting tools, generating
content, routing between models. Without governance, these systems produce
outputs that are:

- **Unverifiable** — no proof that the right model was used with the right
  constraints
- **Non-reproducible** — no deterministic way to replay or audit a decision
- **Unconstrained** — roles, tool budgets, and output contracts are advisory,
  not enforced
- **Opaque** — when something goes wrong, there is no chain of custody from
  input to output

AIGC solves this by making governance a **compile-time contract** (policy YAML)
enforced at **runtime** (the SDK), producing **forensic evidence** (audit
artifacts) at every invocation.

---

## 3. Design Principles

| Principle | Meaning |
| --------- | ------- |
| **Governance is data, not code** | Policies are declarative YAML validated against JSON Schema. No executable policy logic. |
| **Enforcement is deterministic** | Given the same invocation and policy, the SDK always produces the same pass/fail decision. Timestamps and checksums are the only volatile fields. |
| **Audit is mandatory** | Every successful enforcement produces an artifact. There is no "silent" mode. |
| **Provider-agnostic** | The SDK governs invocations, not providers. It works with OpenAI, Anthropic, Bedrock, local models, or any future provider. |
| **Fail-closed** | Missing preconditions, invalid schemas, unauthorized roles — all raise typed exceptions. The default answer is "no." |
| **Portable** | The SDK has no dependency on any specific host application. It can be embedded in any Python system. |
| **Schema-first** | Every contract (policy DSL, audit artifact, output format) is defined as JSON Schema before code is written. |

---

## 4. System Context

### 4.1 Where AIGC Sits

AIGC operates at the **invocation boundary** — the point where a system
decides to call an AI model and receives a response.

```text
                   ┌──────────────────────────────────────┐
                   │          Host Application             │
                   │  (custom agent, orchestrator)         │
                   │                                       │
                   │    ┌─────────────────────────────┐    │
                   │    │     Application Logic        │    │
                   │    │  (orchestrator, tools, UI)   │    │
                   │    └──────────┬──────────────────┘    │
                   │               │                       │
                   │               ▼                       │
                   │    ┌─────────────────────────────┐    │
                   │    │  ╔═══════════════════════╗   │    │
                   │    │  ║   AIGC Governance SDK ║   │    │
                   │    │  ║                       ║   │    │
                   │    │  ║  Policy ─▶ Enforce    ║   │    │
                   │    │  ║           ─▶ Audit    ║   │    │
                   │    │  ╚═══════════════════════╝   │    │
                   │    └──────────┬──────────────────┘    │
                   │               │                       │
                   │               ▼                       │
                   │    ┌─────────────────────────────┐    │
                   │    │     Model Provider           │    │
                   │    │  (OpenAI, Anthropic, etc.)   │    │
                   │    └─────────────────────────────┘    │
                   │                                       │
                   └──────────────────────────────────────┘
```

### 4.2 What AIGC Does NOT Do

AIGC is intentionally scoped. It does **not**:

- Make LLM calls (it governs them)
- Store audit artifacts (it produces them; the host persists them)
- Manage sessions or state (that belongs to the host)
- Handle authentication or authorization (it enforces role allowlists
  declared in policy)
- Replace compliance pipelines (it complements them; host-level compliance
  steps such as reference verification and PII redaction are orthogonal)

---

## 5. Core Abstractions

AIGC has four core abstractions. Everything in the SDK exists to support these.

### 5.1 Policy

A **Policy** is a declarative YAML contract that defines the governance rules
for a class of invocations.

```yaml
policy_version: "1.0"
description: "Governance contract for planner agents"

roles:
  - planner
  - verifier

conditions:
  is_enterprise:
    type: boolean
    default: false

tools:
  allowed_tools:
    - name: "search_knowledge_base"
      max_calls: 5

retry_policy:
  max_retries: 2
  backoff_ms: 500

pre_conditions:
  required:
    - role_declared
    - schema_exists

post_conditions:
  required:
    - output_schema_valid

output_schema:
  type: object
  required: ["result", "confidence"]
  properties:
    result:
      type: string
    confidence:
      type: number
      minimum: 0
      maximum: 1

guards:
  - when:
      condition: "is_enterprise"
    then:
      post_conditions:
        required:
          - audit_level_high
```

**Key properties:**

- Validated against `schemas/policy_dsl.schema.json` (JSON Schema Draft-07)
  at load time
- Versioned (`policy_version`) for evolution tracking
- Role allowlist is exhaustive — unlisted roles are rejected
- Guards enable conditional policy expansion without code changes
- Full DSL specification: `policies/policy_dsl_spec.md`

### 5.2 Invocation

An **Invocation** is the structured input to the enforcement engine. It
captures everything about a single model interaction.

```python
invocation = {
    "policy_file": "policies/planner.yaml",
    "model_provider": "anthropic",
    "model_identifier": "claude-sonnet-4-20250514",
    "role": "planner",
    "input": {"task": "Analyze incident INC-2847"},
    "output": {"result": "Root cause identified", "confidence": 0.92},
    "context": {
        "role_declared": True,
        "schema_exists": True,
        "is_enterprise": False,
    },
}
```

**Required fields:**

| Field | Type | Purpose |
| ----- | ---- | ------- |
| `policy_file` | string | Path to the governing policy YAML |
| `model_provider` | string | Provider identifier (e.g. "anthropic", "openai") |
| `model_identifier` | string | Specific model used (e.g. "claude-sonnet-4-20250514") |
| `role` | string | The role this invocation is executing under |
| `input` | dict | The input sent to the model |
| `output` | dict | The output received from the model |
| `context` | dict | Runtime context for precondition evaluation |

### 5.3 Enforcement

**Enforcement** is the core pipeline that evaluates an invocation against its
policy. It is the single entry point to the SDK.

```python
from aigc.enforcement import enforce_invocation

audit = enforce_invocation(invocation)
```

The pipeline is detailed in Section 6.

### 5.4 Audit Artifact

An **Audit Artifact** is the immutable record produced by every successful
enforcement. It serves as the chain of custody for the invocation.

```json
{
  "model_provider": "anthropic",
  "model_identifier": "claude-sonnet-4-20250514",
  "role": "planner",
  "policy_version": "1.0",
  "policy_file": "policies/planner.yaml",
  "input_checksum": "a3f8c2...sha256",
  "output_checksum": "7b2e19...sha256",
  "enforcement_result": "PASS",
  "timestamp": 1739750400,
  "metadata": {
    "preconditions_satisfied": ["role_declared", "schema_exists"],
    "postconditions_satisfied": ["output_schema_valid"],
    "guards_evaluated": [
      {"condition": "is_enterprise", "matched": false}
    ],
    "conditions_resolved": {},
    "schema_validation": "passed",
    "tool_constraints": {}
  }
}
```

**Design constraints for audit artifacts:**

- **Stable fields** (deterministic): `audit_schema_version`, `policy_file`,
  `policy_schema_version`, `model_provider`, `model_identifier`, `role`,
  `policy_version`, `enforcement_result` — used in golden replay assertions
- **Volatile fields** (non-deterministic): `timestamp`, `input_checksum`,
  `output_checksum` — excluded from golden replay assertions
- **Checksums** use SHA-256 over canonical JSON (`json.dumps(obj,
  sort_keys=True)`) for cross-platform determinism
- **Append-only semantics** — artifacts are produced, never modified

---

## 6. Enforcement Pipeline

The enforcement pipeline is a strict sequence of gates. Each gate either
passes or raises a typed exception. There is no partial enforcement.

```text
enforce_invocation(invocation)
│
├─ 1. LOAD POLICY
│     policy_loader.load_policy(invocation["policy_file"])
│     ├─ Parse YAML
│     ├─ Validate against policy_dsl.schema.json
│     └─ Return policy dict
│
├─ 2. RESOLVE GUARDS                         [Phase 2 — implemented]
│     If policy declares guards or conditions, evaluate_guards() is called.
│     ├─ Resolve named conditions from context or defaults
│     ├─ Evaluate guard expressions in declaration order
│     ├─ Apply additive merge to produce effective_policy
│     └─ Raise GuardEvaluationError or ConditionResolutionError on failure
│
├─ 3. VALIDATE ROLE                          [Phase 1]
│     Check invocation["role"] ∈ effective_policy["roles"]
│     └─ Raise GovernanceViolationError if unauthorized
│
├─ 4. VALIDATE PRECONDITIONS
│     For each key in effective_policy["pre_conditions"]["required"]:
│       ├─ Check key exists in context and is truthy
│       └─ Raise PreconditionError if missing/falsy
│
├─ 5. VALIDATE TOOL CONSTRAINTS              [Phase 2 — implemented]
│     If policy declares tools, validate_tool_constraints() is called.
│     ├─ Enforce tool allowlist
│     ├─ Enforce max_calls limits per tool
│     └─ Raise ToolConstraintViolationError on violation
│
├─ 6. VALIDATE OUTPUT SCHEMA
│     If effective_policy has "output_schema":
│       ├─ Validate invocation["output"] against schema
│       └─ Raise SchemaValidationError on mismatch
│
├─ 7. VALIDATE POSTCONDITIONS                [Phase 1]
│     For each key in effective_policy["post_conditions"]["required"]:
│       ├─ Check key is satisfiable from invocation state
│       └─ Raise GovernanceViolationError if unsatisfied
│
├─ 8. GENERATE AUDIT ARTIFACT
│     Collect all enforcement decisions into structured record
│     ├─ Compute input/output checksums (SHA-256, canonical JSON)
│     ├─ Record all gate results + gates_evaluated ordering proof
│     ├─ Stamp timestamp
│     └─ Return audit artifact
│
└─ RETURN audit_artifact
```

### 6.1 Gate Ordering Rationale

The gate order is intentional:

1. **Load policy first** — everything depends on having a valid policy
2. **Guards before role** — guards can expand the effective policy (e.g., add
   additional preconditions or tool rules) based on runtime context, so they
   must be resolved before role validation uses the effective policy's roles list
3. **Role check before preconditions** — reject unauthorized callers before
   revealing any precondition semantics to unauthorized roles
4. **Preconditions before tools** — if the context is invalid, downstream
   validation results are meaningless
5. **Tool constraints before schema** — authorization gates (guards, role,
   preconditions, tools) must all run before output-processing gates (schema,
   postconditions); prohibited tools must be caught before model output is
   evaluated (see D-04 fix, enforced by `tests/test_pre_action_boundary.py`)
6. **Schema before postconditions** — output must be structurally valid
   before semantic postconditions can be evaluated
7. **Audit always** — only reached on full success; exceptions short-circuit

### 6.2 Exception Hierarchy

```text
AIGCError (base)
├── PreconditionError              — required context key missing or falsy
├── SchemaValidationError          — output does not match JSON Schema
├── ConditionResolutionError       — condition resolution failure
├── GuardEvaluationError           — guard expression evaluation failure
├── AuditSinkError                 — audit sink emission failure (raise mode)
└── GovernanceViolationError       — role unauthorized, tool cap exceeded,
    │                                postcondition unsatisfied, or any
    │                                other policy-level violation
    ├── InvocationValidationError  — invocation payload contract violation
    ├── PolicyLoadError            — policy loading/parsing failure
    ├── PolicyValidationError      — policy schema validation failure
    ├── ToolConstraintViolationError — tool constraint violation
    └── FeatureNotImplementedError — schema-declared feature not implemented
```

Exceptions are implemented in `aigc/_internal/errors.py` and exposed via `aigc/errors.py`. The host application catches
these to decide whether to retry, escalate, or block.

---

## 7. Policy DSL Architecture

### 7.1 Schema Layer

All policies are validated at load time against JSON Schema Draft-07:

```text
schemas/
├── policy_dsl.schema.json          ← Primary (extended DSL)
└── invocation_policy.schema.json   ← Legacy (minimal fallback)
```

The loader prefers the extended DSL schema. If it is missing (e.g. in a
minimal deployment), it falls back to the legacy schema.

### 7.2 Policy Evaluation Order

```text
1. Static validation    — JSON Schema at load time (structure)
2. Guard evaluation     — Conditional expansion (context)
3. Role resolution      — Allowlist check (identity)
4. Precondition check   — Context requirements (readiness)
5. Tool constraints     — Usage limits (cost/risk, authorization)
6. Schema validation    — Output structure (correctness)
7. Postcondition check  — Semantic requirements (completeness)
```

### 7.3 Guard Resolution

Guards are evaluated in declaration order. Their effects are **additive** —
a guard can add preconditions or postconditions but cannot remove them.

```yaml
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

Resolution produces an **effective policy** that merges the base policy with
all matched guard expansions. The base policy is never mutated.

```text
effective_policy = base_policy + Σ(matched_guard.then)
```

### 7.4 Condition Expressions

Conditions are resolved from the invocation context:

- **Simple boolean**: `"is_enterprise"` → `context.get("is_enterprise",
  default)`
- **Equality**: `"role == verifier"` → `invocation["role"] == "verifier"`

Conditions are evaluated as pure lookups. There is no expression language,
no Turing-completeness, no side effects. This is intentional — governance
logic must be auditable by reading the YAML alone.

---

## 8. Audit Architecture

### 8.1 Checksum Strategy

Checksums provide tamper-evidence. Given an audit artifact, any party can
independently recompute the checksums and verify integrity.

```python
import json
import hashlib

def checksum(obj: dict) -> str:
    canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

**Canonical JSON** is used (not Python `str(sorted(...))`):
- `sort_keys=True` — deterministic key ordering
- `separators=(",", ":")` — no whitespace variance
- UTF-8 encoding — cross-platform byte stability

### 8.2 Artifact Storage Model

AIGC **produces** artifacts but does not **store** them. The host application
chooses the persistence strategy:

| Host Context | Storage Strategy |
| ------------ | ---------------- |
| Local / dev | SQLite table or `JsonFileAuditSink` |
| Cloud | DynamoDB, S3 archival, or log stream |
| Standalone | JSON file, database, or log stream |
| CI/CD | Golden replay fixtures in `tests/golden_replays/` |

This separation keeps the SDK portable.

### 8.3 Golden Replay Testing

Golden replays are deterministic fixtures that encode expected governance
behavior. They serve as regression tests for the enforcement pipeline.

```text
tests/golden_replays/
├── golden_policy_v1.yaml              ← policy under test
├── golden_schema.json                 ← output schema
├── golden_invocation_success.json     ← input that must PASS
├── golden_invocation_failure.json     ← input that must FAIL
└── golden_expected_audit.json         ← stable fields to assert
```

**Testing contract:**
- Assert only **stable fields** (`model_provider`, `model_identifier`,
  `role`, `policy_version`, `enforcement_result`)
- Never assert timestamps or checksums (volatile)
- Every new governance feature requires paired success/failure golden replays

---

## 9. Host Integration

AIGC is designed to integrate with any agentic host system at the tool,
provider, and compliance pipeline layers. The recommended integration
pattern uses the `@governed` decorator or direct `enforce_invocation`
calls at each model invocation boundary.

For integration patterns and compliance requirements, see the
[Integration Guide](../INTEGRATION_GUIDE.md).

---

## 10. Extension Model

### 10.1 Custom Validators

> **Note:** Custom validation registration (`register_validator`) is planned but
> not yet implemented in the current SDK. Do not attempt to import or call it.
> Use policy guards and postconditions for runtime behavioral control in the
> interim.

### 10.2 Audit Sinks

The SDK provides a pluggable audit sink interface. Import from `aigc.sinks`:

```python
from aigc.sinks import AuditSink, set_audit_sink

class SQLiteAuditSink(AuditSink):
    def emit(self, artifact: dict) -> None:
        self.conn.execute(
            "INSERT INTO audit_log (artifact) VALUES (?)",
            [json.dumps(artifact)]
        )

class CloudWatchAuditSink(AuditSink):
    def emit(self, artifact: dict) -> None:
        self.client.put_log_events(...)

set_audit_sink(SQLiteAuditSink(conn))
```

Built-in implementations: `JsonFileAuditSink` (JSONL append) and
`CallbackAuditSink` (user-provided function). Register with `set_audit_sink()`,
also importable from `aigc.sinks` or the root `aigc` package.

### 10.3 Policy Resolvers

> **Note:** Dynamic policy resolution (`register_resolver`) is planned but not
> yet implemented in the current SDK. Do not attempt to import or call it.
> Use the `policy_file` field in each invocation for per-call policy selection
> in the interim.

---

## 11. Security and Trust Model

### 11.1 Trust Boundaries

```text
TRUSTED                          UNTRUSTED
────────────────────────────────────────────
Policy YAML files                Model outputs
JSON Schema definitions          User-provided context values
SDK enforcement logic            External provider responses
Audit artifact checksums         Runtime tool call counts
```

### 11.2 Threat Model

| Threat | Mitigation |
| ------ | ---------- |
| Tampered audit artifact | SHA-256 checksums over canonical JSON; recomputable by any party |
| Unauthorized role | Exhaustive role allowlist in policy; fail-closed on unlisted roles |
| Policy schema drift | JSON Schema validation at load time; CI validation of all policies |
| Excessive tool usage | Per-tool max_calls caps in policy; enforced at invocation time |
| Context spoofing | Context is provided by the host; AIGC validates structure, host validates authenticity |
| Policy bypass | Single entry point (`enforce_invocation`); no alternative code paths |

### 11.3 Invariants

These properties must hold for every enforcement:

1. **No silent pass** — every enforcement produces an audit artifact or
   raises an exception
2. **No partial enforcement** — all gates run or none do; exceptions
   short-circuit
3. **Policy immutability** — the loaded policy dict is never mutated during
   enforcement
4. **Checksum determinism** — same input/output always produces the same
   checksum
5. **Append-only audit** — artifacts are created, never updated or deleted

---

## 12. Non-Functional Requirements

| Requirement | Target | Rationale |
| ----------- | ------ | --------- |
| Enforcement latency | < 5ms per invocation (excluding I/O) | Must not be a bottleneck in agentic loops |
| Zero external dependencies at runtime | PyYAML + jsonschema only | Portability; no network calls |
| Python version | >= 3.10 | Compatible with modern async orchestrators |
| Thread safety | Enforcement is stateless and reentrant | Safe for async orchestrators |
| Package size | < 50KB (source only) | Embeddable in any project |
| Test coverage | >= 90% line coverage | Governance code demands high assurance |

---

## 13. Glossary

| Term | Definition |
| ---- | ---------- |
| **AIGC** | Auditable Intelligence Governance Contract — the SDK |
| **Policy** | Declarative YAML contract defining governance rules |
| **Invocation** | Structured dict representing a single model interaction |
| **Enforcement** | The act of evaluating an invocation against a policy |
| **Audit Artifact** | Immutable record produced by successful enforcement |
| **Golden Replay** | Deterministic test fixture encoding expected governance behavior |
| **Guard** | Conditional policy expansion triggered by runtime context |
| **Gate** | A single validation step in the enforcement pipeline |
| **Effective Policy** | The result of merging base policy with matched guard expansions |
