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
- **Precondition validation** — required context keys checked before model
  output is evaluated
- **Output schema validation** — model outputs validated against JSON Schema
  defined in policy
- **Audit artifact generation** — SHA-256 checksummed records with model,
  role, and policy metadata
- **Custom exception hierarchy** — `PreconditionError`,
  `SchemaValidationError`, `GovernanceViolationError` for typed error handling
- **Golden trace testing** — deterministic fixtures for regression testing
  governance behavior
- **CI pipeline** — automated tests, linting, markdown lint, and policy
  schema validation

### Policy DSL (Schema Defined, Implementation In Progress)

- **Role allowlists** — exhaustive list of authorized roles per policy
- **Postcondition validation** — semantic checks after output schema
  validation
- **Conditional guards** — `when/then` rules that expand the effective
  policy based on runtime context
- **Tool constraints** — per-tool call caps (`max_calls`) and tool
  allowlists
- **Retry policy** — bounded, auditable retry behavior (`max_retries`,
  `backoff_ms`)
- **Named conditions** — boolean flags resolved from invocation context,
  used by guards

### Planned

- **Pluggable audit sinks** — file, SQLite, DynamoDB, CloudWatch
- **Custom validators** — host applications register domain-specific
  validation functions
- **Policy resolvers** — dynamic policy selection (multi-tenant,
  feature-flagged)
- **Async enforcement** — non-blocking enforcement for async orchestrators
- **Decorator/middleware pattern** — `@governed(policy="...")` for wrapping
  LLM calls
- **Structured logging** — Python `logging` integration for observability
- **TRACE integration** — tool gate, provider gate, compliance extension,
  audit correlator

---

## Architecture Overview

```text
enforce_invocation(invocation)
│
├── 1. Load Policy           policy_loader.py
│     Parse YAML, validate against JSON Schema
│
├── 2. Validate Role         validator.py           [Phase 1]
│     Check role ∈ policy.roles
│
├── 3. Resolve Guards        guard_evaluator.py     [Phase 2]
│     Evaluate when/then, merge into effective policy
│
├── 4. Validate Preconditions   validator.py
│     Check required context keys
│
├── 5. Validate Output Schema   validator.py
│     JSON Schema validation of model output
│
├── 6. Validate Postconditions  validator.py        [Phase 1]
│     Semantic checks on enforcement state
│
├── 7. Validate Tool Constraints tool_validator.py  [Phase 2]
│     Allowlist + max_calls enforcement
│
└── 8. Generate Audit Artifact   audit.py
      SHA-256 checksums, metadata, timestamp
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
│   ├── plans/
│   │   └── IMPLEMENTATION_PLAN.md     3-phase implementation roadmap
│   ├── GOLDEN_TRACES_CI_GUIDE.md      CI integration for golden traces
│   ├── GOLDEN_TRACES_README.md        Golden trace authoring guide
│   ├── GOLDEN_TRACE_CHECKLIST.md      Checklist for new golden traces
│   └── USAGE.md                       SDK usage guide with examples
│
├── policies/
│   ├── base_policy.yaml               Default governance policy
│   └── policy_dsl_spec.md             Full DSL specification
│
├── schemas/
│   ├── policy_dsl.schema.json         Extended DSL schema (primary)
│   └── invocation_policy.schema.json  Legacy schema (fallback)
│
├── scripts/
│   └── generate_golden_traces.py      Auto-generate golden traces from logs
│
├── src/
│   ├── __init__.py                    Package initialization
│   ├── enforcement.py                 Orchestrator — single entry point
│   ├── policy_loader.py               YAML loading + JSON Schema validation
│   ├── validator.py                   Precondition + schema validation
│   ├── audit.py                       Audit artifact generation
│   └── errors.py                      Custom exception hierarchy
│
├── tests/
│   ├── golden_traces/
│   │   ├── golden_policy_v1.yaml      Test policy
│   │   ├── golden_schema.json         Test output schema
│   │   ├── golden_invocation_success.json
│   │   ├── golden_invocation_failure.json
│   │   └── golden_expected_audit.json
│   ├── test_golden_trace_success.py   Regression: valid invocation
│   ├── test_golden_trace_failure.py   Regression: invalid invocation
│   ├── test_audit_artifact_contract.py Audit field presence contract
│   └── test_validation.py            Validation unit tests
│
├── CLAUDE.md                          AI assistant guidance
├── LICENSE                            MIT License
├── PROJECT.md                         This file
├── README.md                          Quick-start documentation
└── requirements.txt                   Python dependencies
```

---

## Quick Start

### Installation

```bash
git clone https://github.com/nealsolves/aigc-governance-sdk.git
cd aigc-governance-sdk
pip install -r requirements.txt
```

### Basic Usage

```python
from src.enforcement import enforce_invocation

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
#   "model_provider": "anthropic",
#   "model_identifier": "claude-sonnet-4-20250514",
#   "role": "planner",
#   "policy_version": "1.0",
#   "input_checksum": "a3f8c2...",
#   "output_checksum": "7b2e19...",
#   "timestamp": 1739750400
# }
```

### Handling Failures

```python
from src.enforcement import enforce_invocation
from src.errors import PreconditionError, SchemaValidationError

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

## Documentation

| Document | Purpose |
| -------- | ------- |
| [Architecture Design](docs/architecture/AIGC_HIGH_LEVEL_DESIGN.md) | High-level design, core abstractions, TRACE integration |
| [Implementation Plan](docs/plans/IMPLEMENTATION_PLAN.md) | 3-phase roadmap with deliverables and acceptance criteria |
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
| `flake8 >= 5.0` | Python linting |

---

## License

MIT License. See [LICENSE](LICENSE).
