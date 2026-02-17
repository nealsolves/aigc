# AIGC — Auditable Intelligence Governance Contract

**The governance primitive for trustworthy AI systems.**

---

## What is AIGC?

AIGC is a Python SDK that enforces deterministic governance over AI model
invocations. It ensures that every interaction with an AI model — regardless
of provider, framework, or orchestration pattern — is:

1. **Explicitly specified** — governance rules are declared in versioned
   YAML policies, not buried in code
2. **Deterministically enforced** — the same invocation + policy always
   produces the same pass/fail decision
3. **Observable** — every enforcement produces a structured audit artifact
   with checksums and metadata
4. **Replayable and auditable** — golden trace fixtures enable forensic
   regression testing of governance behavior
5. **Model/provider independent** — governance sits above the provider
   layer; switch from OpenAI to Anthropic to Bedrock without touching
   governance logic

## Why AIGC Exists

Agentic AI systems (multi-model orchestrators, tool-calling agents, RAG
pipelines) make autonomous decisions at scale. Without governance:

- There is no proof that the right model was used under the right constraints
- Outputs cannot be deterministically replayed for audit
- Role boundaries, tool budgets, and output contracts are advisory, not enforced
- When something goes wrong, there is no forensic chain of custody

AIGC makes governance a **first-class engineering concern** — not a
compliance afterthought.

## Relationship to TRACE

AIGC is the governance layer for the
[TRACE project](https://github.com/nealsolves/trace/tree/develop) (Temporal
Root-cause Analytics & Correlation Engine), an agentic RAG system for
root-cause analysis. TRACE uses AIGC to govern:

- Model invocations across planner, verifier, and synthesizer agents
- Tool usage constraints (which tools, how many calls)
- Output schema compliance (structured RCA outputs)
- Audit trail generation for compliance reporting

While built for TRACE, AIGC is designed to be **portable** — it has no
dependency on TRACE internals and can be embedded in any Python system that
invokes AI models.

---

## Features

### Core (Implemented)

- **Policy-driven enforcement** — YAML policies validated against JSON Schema
  (Draft-07) at load time
- **Invocation contract validation** — required invocation fields and types
  validated before enforcement (typed fail-closed errors)
- **Role allowlist enforcement** — invocation role must be declared in
  policy `roles`
- **Precondition validation** — required context keys checked before model
  output is evaluated
- **Output schema validation** — model outputs validated against JSON Schema
  defined in policy
- **Postcondition validation** — `output_schema_valid` enforced after schema
  validation
- **Audit artifact generation** — SHA-256 checksummed records with model,
  role, and policy metadata via `schemas/audit_artifact.schema.json`
- **Failure audit emission** — FAIL audit artifacts emitted and attached to
  exceptions before propagation (Phase 1.8)
- **Custom exception hierarchy** — typed exceptions with machine-readable
  error codes/details
- **Golden trace testing** — deterministic fixtures for regression testing
  governance behavior
- **CI pipeline** — tests with coverage gates, linting, markdown lint, and
  policy schema validation

### Policy DSL (Phase 2 - Fully Implemented)

- **Conditional guards** — `when/then` rules that expand the effective
  policy based on runtime context (guards evaluated before role validation;
  effects are additive and merge into effective policy)
- **Named conditions** — boolean flags resolved from invocation context
  with defaults and required enforcement (used by guards for dynamic policy
  expansion)
- **Tool constraints** — per-tool call caps (`max_calls`) and tool
  allowlists (validated after postconditions; violations emit FAIL audits)
- **Retry policy** — bounded, auditable retry wrapper (`max_retries`,
  `backoff_ms`) for transient SchemaValidationError failures (opt-in via
  `with_retry()`)
- **Policy composition** — inheritance via `extends` field with recursive
  merging (arrays append, dicts recurse, scalars replace; circular
  dependency detection)

### Phase 3 (Production Readiness - In Progress)

- **Async enforcement** — `enforce_invocation_async()` via `asyncio.to_thread`
  for non-blocking policy I/O in async orchestrators (Phase 3.1)
- **Pluggable audit sinks** — `AuditSink` ABC with `JsonFileAuditSink` and
  `CallbackAuditSink`; registered via `set_audit_sink()`; sink failures log
  a warning and do not block enforcement (Phase 3.2)
- **Structured logging** — `aigc` logger namespace with `NullHandler` default;
  gate-level DEBUG, INFO on complete, WARNING on sink failure (Phase 3.3)
- **Decorator/middleware pattern** — `@governed(policy_file, role,
  model_provider, model_identifier)` for sync and async LLM call sites (Phase 3.4)

### Planned (Post-Phase 3)

- **Custom validators** — host applications register domain-specific
  validation functions
- **Policy resolvers** — dynamic policy selection (multi-tenant,
  feature-flagged)
- **TRACE integration** — tool gate, provider gate, compliance extension,
  audit correlator

---

## Architecture Overview

```text
enforce_invocation(invocation)
│
├── 1. Load Policy              policy_loader.py    [Phase 1 + 2.6]
│     Parse YAML, resolve extends (composition), validate JSON Schema
│
├── 2. Evaluate Guards          guards.py           [Phase 2.1]
│     Resolve conditions (conditions.py), evaluate when/then rules,
│     merge effects into effective policy
│
├── 3. Validate Role            validator.py        [Phase 1]
│     Check role ∈ effective_policy.roles
│
├── 4. Validate Preconditions   validator.py        [Phase 1]
│     Check required context keys in effective policy
│
├── 5. Validate Output Schema   validator.py        [Phase 1]
│     JSON Schema validation of model output
│
├── 6. Validate Postconditions  validator.py        [Phase 1]
│     Semantic checks on enforcement state (output_schema_valid)
│
├── 7. Validate Tool Constraints tools.py           [Phase 2.3]
│     Check allowlists and max_calls, fail on violations
│
└── 8. Generate Audit Artifact  audit.py            [Phase 1 + 2.5]
      SHA-256 checksums, Phase 2 metadata (guards, conditions, tools)

Optional Wrapper:
  with_retry(invocation)        retry.py            [Phase 2.4]
    Opt-in retry wrapper for transient SchemaValidationError failures

Async Entry Point:
  enforce_invocation_async()    enforcement.py      [Phase 3.1]
    Async wrapper; policy I/O via asyncio.to_thread; shared sync pipeline

Audit Sinks:
  set_audit_sink(sink)          sinks.py            [Phase 3.2]
    Register AuditSink; emits after every enforcement (PASS and FAIL)

Decorator Pattern:
  @governed(policy_file, role)  decorators.py       [Phase 3.4]
    Sync/async LLM call wrapper; captures input/output/context
```

For the full architecture, see
[docs/architecture/AIGC_HIGH_LEVEL_DESIGN.md](docs/architecture/AIGC_HIGH_LEVEL_DESIGN.md).

For the implementation roadmap, see
[docs/plans/IMPLEMENTATION_PLAN.md](docs/plans/IMPLEMENTATION_PLAN.md).

---

## Project Structure

```text
aigc-governance-sdk/
├── .github/
│   └── workflows/
│       └── sdk_ci.yml                 CI pipeline (tests, lint, policy validation)
│
├── docs/
│   ├── architecture/
│   │   └── AIGC_HIGH_LEVEL_DESIGN.md  High-level architecture design
│   ├── audits/
│   │   └── PHASE1_AUDIT_REPORT.md     Phase 1 audit findings and fixes
│   ├── decisions/
│   │   └── ADR-0001-phase1-failure-audit-emission.md  Phase 1 audit decision
│   ├── plans/
│   │   └── IMPLEMENTATION_PLAN.md     3-phase implementation roadmap
│   ├── prs/
│   │   └── PR1_DETERMINISTIC_CHECKSUM_AUDIT_CONTRACT.md  PR documentation
│   ├── GOLDEN_TRACES_CI_GUIDE.md      CI integration for golden traces
│   ├── GOLDEN_TRACES_README.md        Golden trace authoring guide
│   ├── GOLDEN_TRACE_CHECKLIST.md      Checklist for new golden traces
│   └── USAGE.md                       SDK usage guide with examples
│
├── policies/
│   ├── base_policy.yaml               Default governance policy
│   ├── base_policy_composable.yaml    Base policy for composition testing (Phase 2.6)
│   └── policy_dsl_spec.md             Full DSL specification
│
├── schemas/
│   ├── audit_artifact.schema.json     Audit artifact contract (Phase 1)
│   ├── policy_dsl.schema.json         Extended DSL schema (primary)
│   └── invocation_policy.schema.json  Legacy schema (fallback)
│
├── scripts/
│   └── generate_golden_traces.py      Auto-generate golden traces from logs
│
├── aigc/
│   ├── __init__.py                    Stable public API package
│   ├── enforcement.py                 Public enforcement import (sync + async)
│   ├── errors.py                      Public exception imports
│   ├── policy_loader.py               Public policy loader import
│   ├── validator.py                   Public validator imports
│   ├── audit.py                       Public audit helpers
│   ├── sinks.py                       Public audit sink imports (Phase 3.2)
│   └── decorators.py                  Public decorator imports (Phase 3.4)
│
├── src/
│   ├── __init__.py                    Package initialization
│   ├── enforcement.py                 Orchestrator — sync + async entry points (Phase 3.1)
│   ├── policy_loader.py               YAML loading + composition + JSON Schema validation
│   │                                  load_policy_async added in Phase 3.1
│   ├── validator.py                   Precondition + schema validation
│   ├── audit.py                       Audit artifact generation
│   ├── guards.py                      Guard evaluation engine (Phase 2.1)
│   ├── conditions.py                  Named condition resolution (Phase 2.2)
│   ├── tools.py                       Tool constraint validation (Phase 2.3)
│   ├── retry.py                       Retry policy wrapper (Phase 2.4)
│   ├── sinks.py                       Audit sink registry + built-in sinks (Phase 3.2)
│   ├── decorators.py                  @governed decorator (Phase 3.4)
│   ├── utils.py                       Canonical JSON serialization + checksums
│   └── errors.py                      Custom exception hierarchy
│
├── tests/
│   ├── golden_traces/
│   │   ├── golden_policy_v1.yaml      Test policy (complete)
│   │   ├── golden_policy_postcondition_only.yaml  Postcondition-only policy
│   │   ├── golden_schema.json         Test output schema
│   │   ├── golden_invocation_success.json         Success case
│   │   ├── golden_invocation_failure.json         Schema validation failure
│   │   ├── golden_invocation_failure_with_audit.json  Role validation failure
│   │   ├── golden_invocation_missing_fields.json  Invocation validation failure
│   │   ├── golden_invocation_postcondition_failure.json  Postcondition failure
│   │   ├── golden_expected_audit.json Expected audit for success case
│   │   ├── invalid_policy.yaml        Invalid policy for testing
│   │   ├── policy_missing_roles.yaml  Policy missing roles
│   │   ├── policy_postcondition_without_schema.yaml  Postcondition without schema
│   │   ├── policy_with_guards.yaml    Policy with guards (Phase 2.1)
│   │   ├── policy_with_retry.yaml     Policy with retry (Phase 2.4)
│   │   ├── policy_with_tools.yaml     Policy with tools (Phase 2.3)
│   │   ├── policy_child_extends_base.yaml  Policy composition child (Phase 2.6)
│   │   ├── golden_invocation_guards_*.json  Guard golden traces
│   │   ├── golden_invocation_tools_*.json   Tool golden traces
│   │   └── policy_extends_nonexistent.yaml  Missing base test
│   ├── test_golden_trace_success.py   Regression: valid invocation
│   ├── test_golden_trace_failure.py   Regression: schema validation failure
│   ├── test_golden_trace_failure_with_audit.py  Regression: role failure + audit
│   ├── test_golden_trace_missing_fields.py  Regression: invocation validation
│   ├── test_golden_trace_postcondition_failure.py  Regression: postcondition
│   ├── test_golden_trace_guards.py    Regression: guard evaluation (Phase 2.1)
│   ├── test_golden_trace_tools.py     Regression: tool constraints (Phase 2.3)
│   ├── test_audit_artifact_contract.py  Audit field presence contract
│   ├── test_checksum_determinism.py   Canonical JSON checksum tests
│   ├── test_conditions.py             Condition resolution unit tests (Phase 2.2)
│   ├── test_guards.py                 Guard evaluation unit tests (Phase 2.1)
│   ├── test_tools.py                  Tool constraint unit tests (Phase 2.3)
│   ├── test_retry.py                  Retry policy unit tests (Phase 2.4)
│   ├── test_policy_composition.py     Policy composition unit tests (Phase 2.6)
│   ├── test_enforcement_pipeline.py   End-to-end enforcement tests
│   ├── test_invocation_validation.py  Invocation shape validation tests
│   ├── test_policy_loader.py          Policy loading and validation tests
│   ├── test_public_api.py             Public API import tests
│   ├── test_validation.py             Validation unit tests
│   ├── test_async_enforcement.py      Async enforcement tests (Phase 3.1)
│   ├── test_audit_sinks.py            Audit sink tests (Phase 3.2)
│   └── test_decorators.py             @governed decorator tests (Phase 3.4)
│
├── .flake8                            Flake8 linter configuration
├── .markdownlint-cli2.yaml            Markdown lint configuration
├── CLAUDE.md                          AI assistant governance contract
├── LICENSE                            MIT License
├── PROJECT.md                         This file (authoritative structure)
├── README.md                          Quick-start documentation
├── pyproject.toml                     Packaging metadata + build config
└── requirements.txt                   Python dependencies
```

---

## Quick Start

### Installation

```bash
git clone https://github.com/nealsolves/aigc-governance-sdk.git
cd aigc-governance-sdk
python3 -m venv aigc-env
source aigc-env/bin/activate
python -m pip install --upgrade pip setuptools wheel
pip install -e .[dev]
```

### Basic Usage

```python
from aigc.enforcement import enforce_invocation

invocation = {
    "policy_file": "policies/base_policy.yaml",
    "model_provider": "anthropic",
    "model_identifier": "claude-sonnet-4-20250514",
    "role": "planner",
    "input": {"task": "Generate architecture proposal"},
    "output": {"result": "Architecture proposal v1"},
    "context": {
        "role_declared": True,
        "schema_exists": True,
    },
}

audit = enforce_invocation(invocation)
print(audit)
# {
#   "audit_schema_version": "1.0",
#   "policy_file": "policies/base_policy.yaml",
#   "policy_schema_version": "http://json-schema.org/draft-07/schema#",
#   "model_provider": "anthropic",
#   "model_identifier": "claude-sonnet-4-20250514",
#   "role": "planner",
#   "policy_version": "1.0",
#   "enforcement_result": "PASS",
#   "failures": [],
#   "input_checksum": "a3f8c2...",
#   "output_checksum": "7b2e19...",
#   "timestamp": 1739750400,
#   "metadata": {
#     "preconditions_satisfied": ["role_declared", "schema_exists"],
#     "postconditions_satisfied": ["output_schema_valid"],
#     "schema_validation": "passed"
#   }
# }
```

### Handling Failures

```python
from aigc.enforcement import enforce_invocation
from aigc.errors import PreconditionError, SchemaValidationError

try:
    audit = enforce_invocation(invocation)
except PreconditionError as e:
    print(f"Context incomplete: {e}")
except SchemaValidationError as e:
    print(f"Output invalid: {e}")
```

### Running Tests

```bash
python -m pytest                          # All tests
python -m pytest tests/test_golden_trace_success.py  # Single file
flake8 src                                # Lint
```

### Validating Policies

```bash
python -c "
import json, yaml, jsonschema
from pathlib import Path
schema = json.load(open('schemas/policy_dsl.schema.json'))
for p in Path('policies').glob('*.yaml'):
    jsonschema.validate(yaml.safe_load(open(p)), schema)
    print(f'OK: {p}')
"
```

---

## Phase 2 Implementation (Completed 2026-02-16)

Phase 2 brought all DSL features from schema-declared to runtime-enforced:

### What Changed

1. **Guard Evaluation Engine** (Phase 2.1)
   - Guards processed in declaration order before role validation
   - Supports boolean conditions (`is_enterprise`) and role equality (`role == verifier`)
   - Effects are additive — multiple matching guards merge into effective policy
   - Audit metadata includes `guards_evaluated` list

2. **Named Condition Resolution** (Phase 2.2)
   - Conditions resolved from invocation context with defaults
   - Required conditions fail-closed if missing
   - Type-checked (must be boolean)
   - Audit metadata includes `conditions_resolved` dict

3. **Tool Constraint Enforcement** (Phase 2.3)
   - Validates tool calls against allowlist and per-tool `max_calls`
   - Violations raise `ToolConstraintViolationError` with FAIL audit
   - Audit metadata includes `tool_constraints` summary
   - New failure gate: `tool_validation`

4. **Retry Policy Enforcement** (Phase 2.4)
   - Opt-in wrapper `with_retry(invocation)` for transient failures
   - Only retries `SchemaValidationError` (not policy violations)
   - Backoff: `backoff_ms * attempt_number`
   - `max_retries=0` means single attempt (no retries)
   - Raises `RetryExhaustedError` when exhausted

5. **Extended Audit Artifacts** (Phase 2.5)
   - Audit metadata now includes Phase 2 fields:
     - `guards_evaluated`: List of guard evaluation results
     - `conditions_resolved`: Dict of resolved condition values
     - `tool_constraints`: Tool validation summary
   - Schema updated with new failure gates

6. **Policy Composition** (Phase 2.6)
   - Policies can inherit via `extends: "base_policy.yaml"`
   - Recursive merging with cycle detection
   - Merge rules: arrays append, dicts recurse, scalars replace
   - `extends` field removed from final merged policy
   - Resolved at load time before schema validation

### Test Coverage

- **107 tests** (all passing)
- **98% coverage** (exceeds 90% target)
- **28+ new unit tests** across Phase 2 modules
- **11 new golden trace tests** (guards, tools, conditions, composition)
- All DSL features have regression fixtures

### Architectural Impact

- **No fail-closed feature gates** — all schema-declared features are enforced
- **Determinism preserved** — guards evaluated deterministically, retry is opt-in wrapper
- **Backward compatible** — Phase 1 invocations unchanged, Phase 2 fields optional
- **Typed error taxonomy** — 3 new exception types (ConditionResolutionError, GuardEvaluationError, ToolConstraintViolationError)

---

## Documentation

| Document | Purpose |
| -------- | ------- |
| [Architecture Design](docs/architecture/AIGC_HIGH_LEVEL_DESIGN.md) | High-level design, core abstractions, TRACE integration |
| [Implementation Plan](docs/plans/IMPLEMENTATION_PLAN.md) | 3-phase roadmap with deliverables and acceptance criteria |
| [Architecture Decisions](docs/decisions/) | ADRs documenting significant architectural choices |
| [Policy DSL Spec](policies/policy_dsl_spec.md) | Full specification of the policy YAML format |
| [Usage Guide](docs/USAGE.md) | Code examples and best practices |
| [Golden Traces Guide](docs/GOLDEN_TRACES_README.md) | How to author and maintain golden trace fixtures |
| [Golden Traces CI](docs/GOLDEN_TRACES_CI_GUIDE.md) | CI integration for golden trace regression |
| [Golden Trace Checklist](docs/GOLDEN_TRACE_CHECKLIST.md) | Checklist for adding new golden traces |

---

## Dependencies

| Package | Purpose |
| ------- | ------- |
| `PyYAML >= 6.0` | YAML policy parsing |
| `jsonschema >= 4.0` | JSON Schema validation (policies and outputs) |
| `pytest >= 7.0` | Test framework |
| `pytest-cov >= 4.1` | Test coverage reporting |
| `flake8 >= 5.0` | Python linting |

---

## License

MIT License. See [LICENSE](LICENSE).
