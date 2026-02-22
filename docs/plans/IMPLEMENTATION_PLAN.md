# AIGC SDK Implementation Plan

**3-Phase Roadmap to Production-Ready Governance**

Version: 1.0.0 | Status: Authoritative | Last Updated: 2026-02-16

Implementation status note (2026-02-16):

- **Phase 1: COMPLETE** ✅ (items 1.1-1.8 implemented)
  - Packaging, invocation validation, role enforcement, postconditions,
    canonical checksums, enriched audit artifacts, test coverage at 93%,
    and failure audit emission
  - Phase 1.8 (failure audit emission) discovered as critical gap during PR1
    validation and implemented as final Phase 1 item
  - ADR-0001 documents the course correction
- **Phase 2: COMPLETE** ✅ Guards, conditions, tools, retry policy, and policy
  composition via extends are fully implemented and tested. Coverage at 94%.
- **Phase 3 SDK items: COMPLETE** ✅ (3.1-3.4 implemented 2026-02-16)
  - Async enforcement (`enforce_invocation_async`), pluggable audit sinks
    (`AuditSink`, `JsonFileAuditSink`, `CallbackAuditSink`), structured logging
    (`aigc.*` namespace with NullHandler default), and `@governed` decorator.
  - Host integration items (3.5-3.7) remain in host-system repositories.
  - ADR-0004 documents Phase 3 architectural decisions.

---

## Overview

This plan defines the implementation roadmap for the AIGC Governance SDK
across three phases, progressing from a working prototype to a
production-ready governance layer for any AI-enabled host application.

Each phase has explicit deliverables, acceptance criteria, and the golden
trace test fixtures required to prove the work is complete.

```text
Phase 1: Foundation          Phase 2: Full DSL          Phase 3: Production
(Make it real)               (Deliver the promise)      (Production readiness)
─────────────────           ─────────────────          ─────────────────
Packaging                    Guard evaluation           Async enforcement
Role enforcement             Tool constraints           Audit sinks
Postconditions               Named conditions           Provider governance
Input validation             Retry policy               Decorator pattern
Canonical checksums          Extended audit             Compliance extension
Test coverage ≥80%           Test coverage ≥90%         Host integration tests
```

### Current State (Post-Phase 1 Hardening)

The SDK has a working enforcement pipeline:
`load_policy → validate_preconditions → validate_schema → generate_audit`.

**What works:** Policy loading, invocation validation, role enforcement,
precondition validation, output schema validation, postcondition validation,
canonical checksum generation, audit artifact contract, golden trace testing,
CI pipeline, and packaging (`pyproject.toml`, `aigc` import path).

**What is still missing:** Guard evaluation, tool constraint runtime
enforcement, retry policy runtime enforcement, and test coverage progression
to the long-term Phase 2/3 targets.

---

## Phase 1: Foundation and Packaging

**Goal:** Make the SDK installable, robust, and trustworthy. Close the
gap between "it runs" and "it is correct."

### 1.1 Python Packaging

**Problem:** The SDK has no `__init__.py`, no `pyproject.toml`, and cannot
be installed with `pip install -e .` despite documentation claiming
otherwise.

**Deliverables:**

- `src/__init__.py` — package initialization with public API exports
- `pyproject.toml` — PEP 621 compliant package configuration
- Importable as `from aigc.enforcement import enforce_invocation`
  (rename `src/` to `aigc/` or configure package discovery)

**Acceptance criteria:**

```bash
pip install -e .
python -c "from aigc.enforcement import enforce_invocation; print('OK')"
```

**Files to create/modify:**

| File | Action |
| ---- | ------ |
| `pyproject.toml` | Create — PEP 621 metadata, dependencies, tool config |
| `src/__init__.py` | Create — export `enforce_invocation` and error types |
| `CLAUDE.md` | Update — reflect new import paths |

### 1.2 Invocation Input Validation

**Problem:** `enforce_invocation()` accesses dict keys without validation.
A missing key produces a raw `KeyError` instead of a meaningful governance
error.

**Deliverables:**

- Validate invocation dict structure at the top of `enforce_invocation()`
- Raise `GovernanceViolationError` with a clear message for missing or
  invalid fields
- Required keys: `policy_file`, `model_provider`, `model_identifier`,
  `role`, `input`, `output`, `context`
- Type checks: `input`, `output`, `context` must be dicts; `role` must be
  a string

**Acceptance criteria:**

- `enforce_invocation({})` raises `GovernanceViolationError`, not `KeyError`
- `enforce_invocation({"policy_file": "x"})` error message names all
  missing fields
- Golden trace: `golden_invocation_missing_fields.json` (new)

**Files to modify:**

| File | Action |
| ---- | ------ |
| `src/enforcement.py` | Add validation at top of `enforce_invocation()` |
| `tests/test_input_validation.py` | Create — test missing/invalid fields |
| `tests/golden_traces/golden_invocation_missing_fields.json` | Create |

### 1.3 Role Allowlist Enforcement

**Problem:** Every policy defines a `roles` array, but the enforcement
pipeline never checks whether the invocation's role is authorized.

**Deliverables:**

- Add `validate_role(invocation, policy)` to the enforcement pipeline
- Check `invocation["role"] in policy["roles"]`
- Raise `GovernanceViolationError` if the role is not in the allowlist
- Place this check **before** precondition validation (reject
  unauthorized callers immediately)

**Acceptance criteria:**

- Invocation with `role: "attacker"` against a policy allowing only
  `["planner", "verifier"]` raises `GovernanceViolationError`
- Invocation with `role: "planner"` passes the role check
- Golden trace: `golden_invocation_unauthorized_role.json` (new)

**Files to modify:**

| File | Action |
| ---- | ------ |
| `src/validator.py` | Add `validate_role()` function |
| `src/enforcement.py` | Call `validate_role()` before preconditions |
| `tests/test_role_enforcement.py` | Create — success and failure tests |
| `tests/golden_traces/golden_invocation_unauthorized_role.json` | Create |

### 1.4 Postcondition Validation

**Problem:** Policies define `post_conditions.required` but the SDK
never evaluates them. The DSL spec and schema both support postconditions.

**Deliverables:**

- Add `validate_postconditions(invocation, policy)` to the enforcement
  pipeline
- Postconditions are evaluated **after** schema validation
- Initial postcondition: `output_schema_valid` is automatically satisfied
  if schema validation passes (intrinsic postcondition)
- Custom postconditions are checked against a postcondition registry

**Acceptance criteria:**

- Policy with `post_conditions.required: ["output_schema_valid"]` passes
  when schema validation passes
- Policy with `post_conditions.required: ["nonexistent_check"]` raises
  `GovernanceViolationError`
- Golden trace: `golden_invocation_postcondition_failure.json` (new)

**Files to modify:**

| File | Action |
| ---- | ------ |
| `src/validator.py` | Add `validate_postconditions()` |
| `src/enforcement.py` | Call `validate_postconditions()` after schema validation |
| `tests/test_postcondition_validation.py` | Create |
| `tests/golden_traces/golden_invocation_postcondition_failure.json` | Create |

### 1.5 Canonical Checksums

**Problem:** The current checksum uses `str(sorted(obj.items()))` which
is not deterministic for nested dicts, not portable across languages,
and not a recognized serialization format.

**Deliverables:**

- Replace checksum with canonical JSON serialization:
  `json.dumps(obj, sort_keys=True, separators=(",", ":"))`
- Update existing tests and golden traces that depend on checksum values
  (none should, since checksums are volatile — verify this)

**Acceptance criteria:**

- `checksum({"b": 1, "a": 2}) == checksum({"a": 2, "b": 1})`
  (order-independent)
- `checksum({"nested": {"z": 1, "a": 2}})` produces consistent results
  (nested sort)
- Checksum output is a 64-character hex string (SHA-256)

**Files to modify:**

| File | Action |
| ---- | ------ |
| `src/audit.py` | Replace `str(sorted(...))` with `json.dumps(sort_keys=True)` |
| `tests/test_audit_artifact_contract.py` | Add checksum determinism tests |

### 1.6 Enriched Audit Artifacts

**Problem:** Audit artifacts currently contain only 7 fields. They lack
enforcement result tracking, precondition details, and policy file
provenance.

**Deliverables:**

Expand the audit artifact to include:

```python
{
    # Existing fields
    "model_provider": "...",
    "model_identifier": "...",
    "role": "...",
    "policy_version": "...",
    "input_checksum": "...",
    "output_checksum": "...",
    "timestamp": 0,
    # New fields
    "policy_file": "policies/base_policy.yaml",
    "enforcement_result": "PASS",
    "preconditions_satisfied": ["role_declared", "schema_exists"],
    "postconditions_satisfied": ["output_schema_valid"],
    "schema_validation": "passed",  # or "skipped" if no output_schema
}
```

**Acceptance criteria:**

- All new fields present in audit artifacts
- `enforcement_result` is "PASS" on success
- Golden expected audit updated with new stable fields
- Existing golden trace tests still pass (only assert stable fields)

**Files to modify:**

| File | Action |
| ---- | ------ |
| `src/audit.py` | Expand `generate_audit_artifact()` |
| `src/enforcement.py` | Pass additional context to audit generator |
| `tests/golden_traces/golden_expected_audit.json` | Update |
| `tests/test_audit_artifact_contract.py` | Assert new fields |

### 1.7 Test Coverage Expansion

**Problem:** Only 4 test files with minimal assertions. `test_validation.py`
has a single test.

**Deliverables:**

- Expand `test_validation.py` with:
  - Precondition success path
  - Precondition with falsy value (not just missing key)
  - Schema validation success and failure
  - Multiple missing preconditions
- Add `test_policy_loader.py`:
  - Valid policy loading
  - Invalid YAML (parse error)
  - Schema validation failure (missing required fields)
  - DSL schema fallback to legacy schema
- Add `test_enforcement_integration.py`:
  - Full pipeline success
  - Each gate's failure mode
  - Invocation with output_schema vs without
- Target: **>= 80% line coverage**

**Acceptance criteria:**

```bash
python -m pytest --cov=src --cov-report=term-missing
# All tests pass, coverage >= 80%
```

**Files to create:**

| File | Action |
| ---- | ------ |
| `tests/test_validation.py` | Expand with 8+ tests |
| `tests/test_policy_loader.py` | Create — 6+ tests |
| `tests/test_enforcement_integration.py` | Create — 5+ tests |

### 1.8 Failure Audit Artifact Emission

**Problem (discovered 2026-02-16):** When enforcement fails at any gate
(role, preconditions, schema, postconditions), an exception is raised but
**no audit artifact is generated**. This violates the audit contract
principle: every enforcement attempt must produce an audit artifact,
whether PASS or FAIL. Compliance and forensic analysis require auditing
failed attempts.

**Why this was missed:** Phase 1.6 (Enriched Audit Artifacts) focused on
PASS artifacts. The implementation plan did not explicitly call out FAIL
artifact emission as a separate deliverable, assuming it would be handled
implicitly. This was a planning oversight.

**Course correction:** Adding this as Phase 1.8 (final Phase 1 item)
before Phase 2. This must complete before Phase 2 guard/tool/retry
implementation because Phase 2 will add more failure modes that also need
audit emission.

**Deliverables:**

- Wrap enforcement pipeline in try/except to catch all governance failures
- On exception, generate audit artifact with:
  - `enforcement_result: "FAIL"`
  - `failure_gate`: which gate failed (e.g., "role", "precondition",
    "schema", "postcondition")
  - `failure_reason`: exception message
  - `failures`: structured failure list from exception details
  - All standard audit fields (checksums, timestamps, policy metadata)
- Emit FAIL artifact (when audit sink is configured in future)
- Re-raise original exception (fail-closed behavior preserved)
- Update audit artifact schema to formalize `failure_gate` and
  `failure_reason` fields

**Acceptance criteria:**

- Role validation failure produces FAIL audit artifact + raises
  `GovernanceViolationError`
- Precondition failure produces FAIL audit artifact + raises
  `PreconditionError`
- Schema validation failure produces FAIL audit artifact + raises
  `SchemaValidationError`
- Postcondition failure produces FAIL audit artifact + raises
  `GovernanceViolationError`
- FAIL artifacts include same checksums/metadata as PASS artifacts
- Golden trace: `golden_invocation_failure_with_audit.json` (new)
- Audit artifact schema updated with FAIL-specific fields

**Files to modify/create:**

| File | Action |
| ---- | ------ |
| `src/enforcement.py` | Wrap pipeline in try/except for audit-before-raise |
| `src/audit.py` | Add `failure_gate` and `failure_reason` to artifact generation |
| `schemas/audit_artifact.schema.json` | Add FAIL-specific fields to schema |
| `tests/test_enforcement_pipeline.py` | Add FAIL artifact emission tests |
| `tests/golden_traces/golden_invocation_failure_with_audit.json` | Create |

**Original plan path (before course correction):**

```
Phase 1 (items 1.1-1.7) → Phase 2 (guards, tools, retry)
```

**Corrected plan path (2026-02-16):**

```
Phase 1 (items 1.1-1.8) → Phase 2 (guards, tools, retry)
                    ↑
                    └─ 1.8 added: FAIL audit emission (critical gap)
```

**Rationale:** Discovered that FAIL audits were not emitted during PR1
validation. This is a Phase 1 gap (audit contract completeness), not a
Phase 2 feature. Must fix before adding Phase 2 complexity.

### Phase 1 Definition of Done

- [x] `pip install -e .` works and SDK is importable
- [x] `enforce_invocation({})` raises `GovernanceViolationError` (not `KeyError`)
- [x] Unauthorized roles are rejected
- [x] Postconditions are validated
- [x] Checksums use canonical JSON
- [x] Audit artifacts include enforcement result and gate details
- [x] Test coverage >= 80% (current: 93%)
- [x] All existing golden traces still pass
- [x] 3 new golden trace pairs (missing fields, unauthorized role,
  postcondition failure)
- [x] CI passes (tests, lint, policy validation)
- [x] **Failure audit artifacts emitted before exception propagation (1.8)**
- [x] **CI coverage reporting with 80% threshold enforcement**

**Phase 1 Status:** ✅ **COMPLETE** (2026-02-16)

---

## Phase 2: Full DSL Implementation

**Goal:** Implement every feature declared in the policy DSL schema.
After this phase, the schema and the runtime are in full alignment.

**Dependency:** Phase 1 complete.

### 2.1 Guard Evaluation Engine

**Problem:** Guards (`when/then` conditional policy expansions) are
defined in the schema and DSL spec but not implemented.

**Deliverables:**

- `src/guard_evaluator.py` — new module
- `evaluate_guards(policy, context, invocation) -> effective_policy`
- Evaluation order: guards are processed in declaration order
- Guard effects are **additive** — a guard can add preconditions/
  postconditions but cannot remove them
- The effective policy is a new dict; the original policy is never mutated
- Condition expressions supported:
  - Simple boolean: `"is_enterprise"` resolves via
    `context.get("is_enterprise", default)`
  - Equality: `"role == verifier"` resolves via
    `invocation["role"] == "verifier"`

**Acceptance criteria:**

- Guard with `when.condition: "is_enterprise"` and
  `context.is_enterprise: true` adds the guard's postconditions to
  the effective policy
- Guard with `when.condition: "is_enterprise"` and
  `context.is_enterprise: false` has no effect
- Multiple guards can match and their effects accumulate
- Golden trace: `golden_invocation_guard_match.json` +
  `golden_invocation_guard_no_match.json`

**Files to create/modify:**

| File | Action |
| ---- | ------ |
| `src/guard_evaluator.py` | Create — guard evaluation engine |
| `src/enforcement.py` | Call `evaluate_guards()` before preconditions |
| `tests/test_guard_evaluation.py` | Create — 8+ tests |
| `tests/golden_traces/golden_policy_with_guards.yaml` | Create |
| `tests/golden_traces/golden_invocation_guard_match.json` | Create |
| `tests/golden_traces/golden_invocation_guard_no_match.json` | Create |

### 2.2 Named Condition Resolution

**Problem:** The `conditions` block in the policy schema allows named
boolean conditions with types and defaults, but they are never resolved.

**Deliverables:**

- Add condition resolution to the guard evaluator
- For each condition defined in `policy["conditions"]`:
  - Look up the value in the invocation context
  - If missing, use the declared `default`
  - If missing and no default, raise `GovernanceViolationError` when
    `required: true`
- Resolved conditions are available for guard evaluation

**Acceptance criteria:**

- Condition with `default: false` and no context value resolves to `false`
- Condition with `required: true` and no context value raises
  `GovernanceViolationError`
- Resolved condition value used correctly in guard `when` clause

**Files to modify:**

| File | Action |
| ---- | ------ |
| `src/guard_evaluator.py` | Add `resolve_conditions()` |
| `tests/test_guard_evaluation.py` | Add condition resolution tests |

### 2.3 Tool Constraint Enforcement

**Problem:** The policy schema defines `tools.allowed_tools` with
`name` and `max_calls`, but tool usage is never validated.

**Deliverables:**

- `src/tool_validator.py` — new module
- `validate_tool_constraints(invocation, effective_policy)`
- Invocation gains an optional `tool_calls` field:

  ```python
  "tool_calls": [
      {"name": "search_knowledge_base", "call_id": "tc-001"},
      {"name": "search_knowledge_base", "call_id": "tc-002"},
      {"name": "analyze_trends", "call_id": "tc-003"},
  ]
  ```

- Validation checks:
  1. Each tool name appears in `allowed_tools` (allowlist)
  2. Each tool's call count <= its `max_calls`
- If `tools` is not in the policy, tool validation is skipped
- If `tool_calls` is not in the invocation, tool validation is skipped

**Acceptance criteria:**

- Tool not in allowlist raises `GovernanceViolationError`
- Tool exceeding `max_calls` raises `GovernanceViolationError`
- Tool within limits passes silently
- Missing `tool_calls` field is not an error
- Golden trace: `golden_invocation_tool_violation.json` +
  `golden_invocation_tool_success.json`

**Files to create/modify:**

| File | Action |
| ---- | ------ |
| `src/tool_validator.py` | Create — tool constraint validation |
| `src/enforcement.py` | Call `validate_tool_constraints()` after postconditions |
| `tests/test_tool_validation.py` | Create — 6+ tests |
| `tests/golden_traces/golden_policy_with_tools.yaml` | Create |
| `tests/golden_traces/golden_invocation_tool_violation.json` | Create |
| `tests/golden_traces/golden_invocation_tool_success.json` | Create |

### 2.4 Retry Policy Enforcement

**Problem:** `retry_policy` (max_retries, backoff_ms) is defined in the
schema but not enforced.

**Deliverables:**

- `src/retry.py` — new module
- `RetryPolicy` class that wraps enforcement with retry semantics
- Retries only on `SchemaValidationError` (transient output failures)
- `PreconditionError` and `GovernanceViolationError` are **not retried**
  (policy-level failures)
- Each retry is individually audited
- Backoff between retries: `backoff_ms * attempt_number`

**Usage pattern:**

```python
from aigc.retry import with_retry

audit = with_retry(enforce_invocation, invocation)
```

The retry wrapper is **opt-in**. `enforce_invocation()` itself remains
single-shot. The host application decides whether to use retry semantics.

**Acceptance criteria:**

- `max_retries: 0` means no retries (single attempt)
- `max_retries: 2` allows up to 2 additional attempts after the first failure
- Each attempt is separately audited
- `PreconditionError` is never retried
- If all attempts fail, the last exception is raised

**Files to create:**

| File | Action |
| ---- | ------ |
| `src/retry.py` | Create — retry policy implementation |
| `tests/test_retry_policy.py` | Create — 5+ tests |

### 2.5 Extended Audit Artifacts

**Problem:** Audit artifacts need to capture guard evaluation results
and tool constraint details for forensic analysis.

**Deliverables:**

Expand audit artifacts with Phase 2 fields:

```python
{
    # Phase 1 fields (all retained)
    ...,
    # Phase 2 additions
    "guards_evaluated": [
        {"condition": "is_enterprise", "matched": True},
        {"condition": "role == verifier", "matched": False},
    ],
    "tool_constraints": {
        "tools_checked": ["search_knowledge_base", "analyze_trends"],
        "violations": [],
    },
    "conditions_resolved": {
        "is_enterprise": True,
        "premium_enabled": False,
    },
}
```

**Acceptance criteria:**

- `guards_evaluated` lists every guard with its match result
- `tool_constraints` summarizes tool validation (even if no tools in policy)
- `conditions_resolved` shows all resolved condition values
- Existing golden trace stable field assertions still pass

**Files to modify:**

| File | Action |
| ---- | ------ |
| `src/audit.py` | Add Phase 2 fields |
| `src/enforcement.py` | Pass guard/tool/condition results to audit |
| `tests/test_audit_artifact_contract.py` | Assert Phase 2 fields |

### 2.6 Policy Composition (Multi-Policy)

**Problem:** Complex systems need role-specific policies. Currently,
a single policy file governs all invocations.

**Deliverables:**

- Support a `policies/` directory structure with role-specific files:

  ```text
  policies/
  ├── base_policy.yaml          ← shared defaults
  ├── trace_planner.yaml        ← planner-specific overrides
  ├── trace_verifier.yaml       ← verifier-specific
  └── trace_synthesizer.yaml    ← synthesizer-specific
  ```

- Policy inheritance: role-specific policies can declare
  `extends: base_policy.yaml` to inherit and override
- Merge semantics: role-specific arrays are **appended** to base arrays;
  scalars are **replaced**

**Acceptance criteria:**

- `trace_planner.yaml` with `extends: base_policy.yaml` inherits base
  preconditions and adds planner-specific ones
- Override of `retry_policy` in child replaces the base value
- Circular `extends` raises `GovernanceViolationError`

**Files to create/modify:**

| File | Action |
| ---- | ------ |
| `src/policy_loader.py` | Add `extends` resolution and merge logic |
| `policies/trace_planner.yaml` | Create — example role-specific policy |
| `tests/test_policy_composition.py` | Create — 5+ tests |

### Phase 2 Definition of Done

- [x] Guards evaluate correctly — additive, ordered, context-driven
- [x] Named conditions resolve from context with defaults
- [x] Tool constraints enforce allowlists and max_calls
- [x] Retry policy wraps enforcement with bounded retries
- [x] Audit artifacts capture all gate evaluation details
- [x] Policy composition via `extends` works
- [x] 6 new golden trace pairs covering guards, tools, conditions
- [x] Test coverage >= 90% (achieved 94%)
- [x] CI passes (enforces 90% threshold)
- [x] `schemas/policy_dsl.schema.json` and runtime are in full alignment —
  every field in the schema has corresponding enforcement code

---

## Phase 3: Production Readiness

**Goal:** Make the SDK production-ready for integration with async host
applications.

**Dependency:** Phase 2 complete.

### 3.1 Async Enforcement

**Problem:** Async host applications (FastAPI, agentic frameworks) need
non-blocking enforcement. The SDK's synchronous `enforce_invocation()`
blocks the event loop during policy file I/O.

**Deliverables:**

- `async def enforce_invocation_async(invocation) -> dict`
- Async file I/O for policy loading (`aiofiles`)
- Synchronous `enforce_invocation()` preserved for non-async callers
- Shared enforcement logic — the async version is not a copy-paste of
  the sync version

**Acceptance criteria:**

- `await enforce_invocation_async(invocation)` produces identical results
  to `enforce_invocation(invocation)`
- Policy file is read without blocking the event loop
- All existing tests pass against both sync and async paths

**Files to create/modify:**

| File | Action |
| ---- | ------ |
| `src/enforcement.py` | Add `enforce_invocation_async()` |
| `src/policy_loader.py` | Add `load_policy_async()` |
| `tests/test_async_enforcement.py` | Create — async equivalents of sync tests |

### 3.2 Pluggable Audit Sinks

**Problem:** The SDK returns audit dicts but has no persistence mechanism.
Host applications must write their own storage code.

**Deliverables:**

- `src/audit.py` — `AuditSink` abstract base class
- Built-in sinks:
  - `JsonFileAuditSink` — append to JSONL file
  - `CallbackAuditSink` — call a user-provided function
- Host-specific sinks (in host repos, not in SDK):
  - `SQLiteAuditSink` — write to a host application's audit_log table
  - `DynamoDBSink` — write to AWS DynamoDB
- Sink registration on the enforcement engine:

  ```python
  from aigc.enforcement import set_audit_sink
  set_audit_sink(JsonFileAuditSink("audit.jsonl"))
  ```

**Acceptance criteria:**

- `JsonFileAuditSink` appends one JSON line per enforcement
- `CallbackAuditSink` invokes callback with the audit dict
- Sink failures do not prevent enforcement from completing (log warning)
- Default behavior (no sink) returns audit dict as before

**Files to create/modify:**

| File | Action |
| ---- | ------ |
| `src/audit.py` | Add `AuditSink` ABC and built-in sinks |
| `src/enforcement.py` | Emit to registered sink after generating artifact |
| `tests/test_audit_sinks.py` | Create — test each sink type |

### 3.3 Structured Logging

**Problem:** The SDK has no logging. Failures are silent except for
raised exceptions.

**Deliverables:**

- Configure `aigc` logger namespace
- Log at these points:
  - `DEBUG`: policy loaded, each gate passed
  - `INFO`: enforcement complete (PASS/FAIL)
  - `WARNING`: sink emit failure, deprecated schema fallback
  - `ERROR`: enforcement exception details
- No log output by default (NullHandler). Host application configures
  log level.

**Acceptance criteria:**

- `logging.getLogger("aigc")` returns a properly configured logger
- No log output unless host configures a handler
- Each gate logs at DEBUG level with gate name and result

**Files to modify:**

| File | Action |
| ---- | ------ |
| All `src/*.py` files | Add `logger = logging.getLogger("aigc")` calls |

### 3.4 Decorator / Middleware Pattern

**Problem:** Wrapping every LLM call in `enforce_invocation()` is
verbose. A typical host application has dozens of model invocations.

**Deliverables:**

- `src/decorators.py` — convenience wrappers
- `@governed(policy_file, role)` decorator:

  ```python
  from aigc.decorators import governed

  @governed(policy_file="policies/planner.yaml", role="planner")
  def plan_investigation(input_data, context):
      response = llm.generate(input_data)
      return response  # automatically enforced
  ```

- The decorator captures input, output, and context; calls
  `enforce_invocation()`; returns the output if enforcement passes
- Async-compatible: detects async functions and uses
  `enforce_invocation_async()`

**Acceptance criteria:**

- Decorated sync function is governed and returns audit alongside result
- Decorated async function works identically
- Decorator raises governance exceptions (not swallowed)
- Decorator can be stacked with other decorators

**Files to create:**

| File | Action |
| ---- | ------ |
| `src/decorators.py` | Create — `@governed` decorator |
| `tests/test_decorators.py` | Create — sync and async tests |

### 3.5–3.7 Host System Integration

Items 3.5 (tool invocation gate), 3.6 (provider governance gate), and 3.7
(audit correlation) are host-system integration concerns. See the
[Integration Guide](../INTEGRATION_GUIDE.md) for patterns and requirements.

These items live in the host system's repository, not the SDK.

### Phase 3 Definition of Done (completed 2026-02-17)

- [x] Async enforcement works identically to sync
- [x] Audit sinks persist artifacts automatically
- [x] Structured logging configured (silent by default)
- [x] `@governed` decorator works for sync and async functions
- [x] SDK passes `pip install` from clean environment
- [x] All golden traces pass
- [x] 100% line coverage across all `src/` modules (180 tests)
- [ ] Host system integration (tracked in host repositories)

---

## Cross-Cutting Concerns

### CI Pipeline Evolution

| Phase | CI Additions |
| ----- | ------------ |
| Phase 1 | Coverage reporting (`--cov`), coverage gate (>= 80%) |
| Phase 2 | Guard/tool golden trace validation, policy composition tests |
| Phase 3 | Async test runner, integration test suite, package build test |

### Golden Trace Inventory

| Phase | New Golden Traces |
| ----- | ----------------- |
| Pre-Phase 1 | `success`, `failure` (schema), `expected_audit` |
| Phase 1 | `missing_fields`, `unauthorized_role`, `postcondition_failure` |
| Phase 2 | `guard_match`, `guard_no_match`, `tool_violation`, `tool_success`, `condition_required_missing`, `policy_composition` |
| Phase 3 | `async_enforcement` (host integration golden traces live in host repo) |

### Documentation Updates

Each phase requires documentation updates:

| Phase | Documentation |
| ----- | ------------- |
| Phase 1 | Update USAGE.md with new error types, update CLAUDE.md with import paths |
| Phase 2 | Add guard/tool/condition examples to USAGE.md, update DSL spec status from "Draft" to "Implemented" |
| Phase 3 | Add async usage examples, add deployment guide, add host integration architecture |

---

## Dependency Graph

```text
Phase 1.1 (packaging) ───────────────────────────────────────▶ ALL
Phase 1.2 (input validation) ────────────────────────────────▶ 1.3+
Phase 1.3 (role enforcement) ────────────────────────────────▶ 1.4+
Phase 1.4 (postconditions) ──────────────────────────────────▶ 2.1
Phase 1.5 (canonical checksums) ─────────────────────────────▶ 2.5
Phase 1.6 (enriched audit) ──────────────────────────────────▶ 2.5
Phase 1.7 (test coverage) ───────────────────────────────────▶ 2.*

Phase 2.1 (guards) ──────────────────────────────────────────▶ 2.2
Phase 2.2 (conditions) ──────────────────────────────────────▶ 2.5
Phase 2.3 (tool constraints) ────────────────────────────────▶ 2.5
Phase 2.4 (retry) ───────────────────────────────────────────▶ 3.4
Phase 2.5 (extended audit) ──────────────────────────────────▶ 3.2
Phase 2.6 (policy composition) ──────────────────────────────▶ host integration

Phase 3.1 (async) ───────────────────────────────────────────▶ 3.4
Phase 3.2 (audit sinks) ─────────────────────────────────────▶ host integration
Phase 3.3 (logging) ─────────────────────────────────────────▶ host integration
Phase 3.4 (decorators) ──────────────────────────────────────▶ host integration
Phase 3.5–3.7 (host integration) ────────────────────────────▶ DONE (in host repo)
```

---

## Risk Register

| Risk | Impact | Mitigation |
| ---- | ------ | ---------- |
| Phase 1 packaging changes break existing imports in tests | High | Run full test suite after every packaging change; update imports incrementally |
| Guard expression language grows beyond simple conditions | Medium | Keep expressions to boolean lookups and equality checks only; no Turing-completeness |
| Policy composition creates circular extends chains | Medium | Detect cycles at load time; fail fast with clear error message |
| Async enforcement diverges from sync behavior | High | Share enforcement logic; async only differs in I/O; test both paths with same fixtures |
| Host integration requires SDK changes | Medium | Keep SDK interface stable; host adapts to SDK, not the other way around |
| Checksum format change invalidates external audit records | Low | Checksums are volatile fields; no external systems should depend on exact values yet |

---

## Success Criteria

SDK success criteria (all met as of 2026-02-17):

1. ✅ **Every field in `policy_dsl.schema.json` has corresponding enforcement
   code** — the DSL promise is fully delivered
2. ✅ **Every enforcement produces a comprehensive audit artifact** — full
   chain of custody from input to output
3. ✅ **Test coverage = 100%** with golden traces for every governance feature
   (180 tests, all passing)
4. ✅ **The SDK is installable, importable, and documented** — a developer
   can `pip install` and govern their first invocation in under 5 minutes

Host integration success criteria (tracked in host repository):

1. ☐ **Host tool executor and provider layer are governed** — no ungoverned
   model invocations (see [Integration Guide](../INTEGRATION_GUIDE.md))
2. ☐ **AIGC audit artifacts correlate with host audit logs** — unified
   governance reporting across the entire system
