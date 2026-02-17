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

AIGC is the governance primitive for the
[TRACE](https://github.com/nealsolves/trace/tree/develop) project (Temporal
Root-cause Analytics & Correlation Engine), but is designed to be portable
across any system that invokes AI models.

```text
┌──────────────────────────────────────────────────────────────────┐
│                    Calling System (e.g. TRACE)                   │
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
| **Portable** | The SDK has no dependency on TRACE internals. It can be embedded in any Python system. |
| **Schema-first** | Every contract (policy DSL, audit artifact, output format) is defined as JSON Schema before code is written. |

---

## 4. System Context

### 4.1 Where AIGC Sits

AIGC operates at the **invocation boundary** — the point where a system
decides to call an AI model and receives a response.

```text
                   ┌──────────────────────────────────────┐
                   │          Host Application             │
                   │  (TRACE, custom agent, pipeline)      │
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
- Replace compliance pipelines (it complements them — TRACE's
  verify_references/redact_pii are orthogonal)

---

## 5. Core Abstractions

AIGC has four core abstractions. Everything in the SDK exists to support these.

### 5.1 Policy

A **Policy** is a declarative YAML contract that defines the governance rules
for a class of invocations.

```yaml
policy_version: "1.0"
description: "Governance contract for TRACE planner agents"

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
    "policy_file": "policies/trace_planner.yaml",
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
  "policy_file": "policies/trace_planner.yaml",
  "input_checksum": "a3f8c2...sha256",
  "output_checksum": "7b2e19...sha256",
  "preconditions_satisfied": ["role_declared", "schema_exists"],
  "postconditions_satisfied": ["output_schema_valid"],
  "guards_evaluated": [
    {"condition": "is_enterprise", "matched": false}
  ],
  "schema_validation": "passed",
  "enforcement_result": "PASS",
  "timestamp": 1739750400
}
```

**Design constraints for audit artifacts:**

- **Stable fields** (deterministic): `audit_schema_version`, `policy_file`,
  `policy_schema_version`, `model_provider`, `model_identifier`, `role`,
  `policy_version`, `enforcement_result` — used in golden trace assertions
- **Volatile fields** (non-deterministic): `timestamp`, `input_checksum`,
  `output_checksum` — excluded from golden trace assertions
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
├─ 2. VALIDATE ROLE                          [Phase 1 — new]
│     Check invocation["role"] ∈ policy["roles"]
│     └─ Raise GovernanceViolationError if unauthorized
│
├─ 3. RESOLVE GUARDS                         [Phase 2 — implemented]
│     If policy declares guards or conditions, evaluate_guards() is called.
│     ├─ Resolve named conditions from context or defaults
│     ├─ Evaluate guard expressions in declaration order
│     ├─ Apply additive merge to produce effective_policy
│     └─ Raise GuardEvaluationError or ConditionResolutionError on failure
│
├─ 4. VALIDATE PRECONDITIONS
│     For each key in effective_policy["pre_conditions"]["required"]:
│       ├─ Check key exists in context and is truthy
│       └─ Raise PreconditionError if missing/falsy
│
├─ 5. VALIDATE OUTPUT SCHEMA
│     If effective_policy has "output_schema":
│       ├─ Validate invocation["output"] against schema
│       └─ Raise SchemaValidationError on mismatch
│
├─ 6. VALIDATE POSTCONDITIONS                [Phase 1 — new]
│     For each key in effective_policy["post_conditions"]["required"]:
│       ├─ Check key is satisfiable from invocation state
│       └─ Raise PreconditionError if unsatisfied
│
├─ 7. VALIDATE TOOL CONSTRAINTS              [Phase 2 — implemented]
│     If policy declares tools, validate_tool_constraints() is called.
│     ├─ Enforce tool allowlist
│     ├─ Enforce max_calls limits per tool
│     └─ Raise ToolConstraintViolationError on violation
│
├─ 8. GENERATE AUDIT ARTIFACT
│     Collect all enforcement decisions into structured record
│     ├─ Compute input/output checksums (SHA-256, canonical JSON)
│     ├─ Record all gate results
│     ├─ Stamp timestamp
│     └─ Return audit artifact
│
└─ RETURN audit_artifact
```

### 6.1 Gate Ordering Rationale

The gate order is intentional:

1. **Load policy first** — everything depends on having a valid policy
2. **Role check before preconditions** — reject unauthorized callers
   immediately; don't leak precondition semantics to unauthorized roles
3. **Guards before preconditions** — guards can inject additional
   preconditions, so they must be resolved before precondition evaluation
4. **Preconditions before schema** — if the context is invalid, schema
   validation results are meaningless
5. **Schema before postconditions** — output must be structurally valid
   before semantic postconditions can be evaluated
6. **Tool constraints last** — tools are the most granular check and
   depend on all prior context being valid
7. **Audit always** — only reached on full success; exceptions short-circuit

### 6.2 Exception Hierarchy

```text
Exception
├── PreconditionError          — required context key missing or falsy
├── SchemaValidationError      — output does not match JSON Schema
└── GovernanceViolationError   — role unauthorized, tool cap exceeded,
                                 postcondition unsatisfied, or any
                                 other policy-level violation
```

All exceptions are defined in `src/errors.py`. The host application catches
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
2. Role resolution      — Allowlist check (identity)
3. Guard evaluation     — Conditional expansion (context)
4. Precondition check   — Context requirements (readiness)
5. Schema validation    — Output structure (correctness)
6. Postcondition check  — Semantic requirements (completeness)
7. Tool constraints     — Usage limits (cost/risk)
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
| TRACE (local) | SQLite `audit_log` table via StateManager |
| TRACE (AWS) | DynamoDB audit table + S3 archival |
| Standalone | JSON file, database, or log stream |
| CI/CD | Golden trace fixtures in `tests/golden_traces/` |

This separation keeps the SDK portable.

### 8.3 Golden Trace Testing

Golden traces are deterministic fixtures that encode expected governance
behavior. They serve as regression tests for the enforcement pipeline.

```text
tests/golden_traces/
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
- Every new governance feature requires paired success/failure golden traces

---

## 9. TRACE Integration Architecture

### 9.1 Integration Points

AIGC integrates with TRACE at five specific points in the TRACE architecture:

```text
┌───────────────────────────────────────────────────────────────────┐
│                         TRACE v5.0                                │
│                                                                   │
│   ┌─────────────┐    ┌──────────────┐    ┌────────────────────┐  │
│   │  Orchestrator│───▶│ Tool Executor│───▶│  Model Provider    │  │
│   │  (Planner/  │    │              │    │  (Anthropic, etc.) │  │
│   │   Executor) │    └──────┬───────┘    └────────┬───────────┘  │
│   └──────┬──────┘           │                     │              │
│          │            ┌─────▼─────┐         ┌─────▼─────┐        │
│          │            │ ❶ AIGC    │         │ ❷ AIGC    │        │
│          │            │ Tool Gate │         │ Provider  │        │
│          │            │           │         │ Gate      │        │
│          │            └───────────┘         └───────────┘        │
│          │                                                       │
│          ▼                                                       │
│   ┌──────────────┐    ┌──────────────┐    ┌────────────────────┐│
│   │  Compliance  │───▶│   State      │───▶│  Audit Sink        ││
│   │  Pipeline    │    │   Manager    │    │  (SQLite/DynamoDB) ││
│   └──────┬───────┘    └──────┬───────┘    └────────────────────┘│
│          │                   │                                   │
│    ┌─────▼─────┐       ┌────▼──────┐                            │
│    │ ❸ AIGC    │       │ ❹ AIGC    │                            │
│    │ Compliance│       │ Audit     │                            │
│    │ Extension │       │ Correlator│                            │
│    └───────────┘       └───────────┘                            │
│                                                                  │
│          ❺ AIGC Policy Registry (shared policies for all gates)  │
│                                                                  │
└───────────────────────────────────────────────────────────────────┘
```

### 9.2 Integration Point Details

**❶ Tool Invocation Gate**

Intercepts tool execution in TRACE's ToolExecutor. Enforces tool allowlists
and per-tool call caps defined in the policy.

```python
# In TRACE's tool_executor.py
from aigc.enforcement import enforce_invocation

class GovernedToolExecutor(ToolExecutor):
    async def execute(self, tool_name, params, context):
        audit = enforce_invocation({
            "policy_file": context.governance_policy,
            "model_provider": context.provider,
            "model_identifier": context.model,
            "role": context.agent_role,
            "input": {"tool": tool_name, "params": params},
            "output": {},  # pre-invocation check
            "context": context.to_governance_context(),
        })
        result = await super().execute(tool_name, params, context)
        return result, audit
```

**❷ Provider Governance Gate**

Wraps TRACE's provider layer. Enforces that only approved models are used
for each role and that invocation outputs conform to declared schemas.

```python
# Governed provider wrapper
class GovernedLLMProvider(BaseLLM):
    async def generate(self, messages, tools=None):
        response = await self.inner.generate(messages, tools)
        audit = enforce_invocation({
            "policy_file": self.policy_file,
            "model_provider": self.provider_name,
            "model_identifier": self.model_id,
            "role": self.current_role,
            "input": {"messages": messages},
            "output": response,
            "context": self.governance_context,
        })
        return response, audit
```

**❸ Compliance Pipeline Extension**

TRACE's mandatory compliance pipeline (verify_references → redact_pii)
can delegate governance decisions to AIGC for policy-driven compliance
rules beyond reference verification and PII redaction.

**❹ Audit Correlator**

Extracts AIGC audit artifacts and correlates them with TRACE's native
audit log (session events, tool calls, compliance decisions) to produce
unified governance reports.

**❺ Policy Registry**

A shared directory of AIGC policies that govern all integration points.
Policies are versioned and validated in CI.

```text
policies/
├── trace_planner.yaml        ← policy for planner role
├── trace_verifier.yaml       ← policy for verifier role
├── trace_synthesizer.yaml    ← policy for synthesis role
├── trace_tools.yaml          ← tool-level governance
└── base_policy.yaml          ← default fallback
```

---

## 10. Extension Model

### 10.1 Custom Validators

Host applications can register custom validation functions that run as
part of the enforcement pipeline:

```python
from aigc.enforcement import register_validator

@register_validator("postcondition")
def validate_citation_integrity(output, context):
    """Custom postcondition: all citations must be verifiable."""
    citations = extract_citations(output.get("result", ""))
    for citation in citations:
        if not context.get("knowledge_base").verify(citation):
            raise GovernanceViolationError(
                f"Unverifiable citation: {citation}"
            )
```

### 10.2 Audit Sinks

The SDK provides a pluggable audit sink interface:

```python
from aigc.audit import AuditSink

class SQLiteAuditSink(AuditSink):
    def emit(self, artifact: dict) -> None:
        self.conn.execute(
            "INSERT INTO audit_log (artifact) VALUES (?)",
            [json.dumps(artifact)]
        )

class CloudWatchAuditSink(AuditSink):
    def emit(self, artifact: dict) -> None:
        self.client.put_log_events(...)
```

### 10.3 Policy Resolvers

For systems with dynamic policy selection (multi-tenant, feature-flagged),
the SDK supports custom policy resolvers:

```python
from aigc.policy_loader import register_resolver

@register_resolver
def tenant_policy_resolver(invocation):
    tenant = invocation["context"].get("tenant_id", "default")
    return f"policies/{tenant}/governance.yaml"
```

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
| Python version | >= 3.10 | Match TRACE's runtime |
| Thread safety | Enforcement is stateless and reentrant | Safe for async orchestrators |
| Package size | < 50KB (source only) | Embeddable in any project |
| Test coverage | >= 90% line coverage | Governance code demands high assurance |

---

## 13. Glossary

| Term | Definition |
| ---- | ---------- |
| **AIGC** | Auditable Intelligence Governance Contract — the SDK |
| **TRACE** | Temporal Root-cause Analytics & Correlation Engine — the host application |
| **Policy** | Declarative YAML contract defining governance rules |
| **Invocation** | Structured dict representing a single model interaction |
| **Enforcement** | The act of evaluating an invocation against a policy |
| **Audit Artifact** | Immutable record produced by successful enforcement |
| **Golden Trace** | Deterministic test fixture encoding expected governance behavior |
| **Guard** | Conditional policy expansion triggered by runtime context |
| **Gate** | A single validation step in the enforcement pipeline |
| **Effective Policy** | The result of merging base policy with matched guard expansions |
