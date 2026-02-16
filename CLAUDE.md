# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Test Commands

```bash
pip install -e .                              # Install in dev mode
python -m pytest                              # Run all tests
python -m pytest tests/test_golden_trace_success.py  # Run a single test file
python -m pytest tests/test_golden_trace_success.py::test_golden_success_produces_audit  # Run a single test
flake8 src                                    # Lint Python source
npx markdownlint-cli2 "**/*.md"              # Lint markdown files
```

**Policy schema validation** (inline, as done in CI):
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

**Generate golden traces from invocation logs:**
```bash
python scripts/generate_golden_traces.py --input logs/invocations.json
```

## Architecture

The SDK enforces governance over AI model invocations through a pipeline:

```
enforce_invocation(invocation)
  → load_policy()        [src/policy_loader.py]
  → validate_preconditions()  [src/validator.py]
  → validate_schema()         [src/validator.py]
  → generate_audit_artifact() [src/audit.py]
  → return audit record
```

**`src/enforcement.py`** — Orchestrator. `enforce_invocation(invocation)` is the single entry point. An invocation dict must include: `policy_file`, `input`, `output`, `context`, `model_provider`, `model_identifier`, `role`.

**`src/policy_loader.py`** — Loads YAML policy files and validates them against JSON Schema. Prefers `schemas/policy_dsl.schema.json` (extended DSL), falls back to `schemas/invocation_policy.schema.json` (legacy).

**`src/validator.py`** — Two validation functions: `validate_preconditions(context, policy)` checks context keys against `policy.pre_conditions.required`; `validate_schema(output, schema)` validates output against a JSON Schema.

**`src/audit.py`** — Generates audit artifacts with SHA256 checksums of input/output, timestamps, and policy metadata. `checksum(obj)` produces deterministic hashes via canonical string representation.

**`src/errors.py`** — Three exception types: `PreconditionError`, `SchemaValidationError`, `GovernanceViolationError`.

## Policy System

Policies are YAML files validated against `schemas/policy_dsl.schema.json` (JSON Schema Draft-07). Key fields: `policy_version`, `roles` (allowlist), `pre_conditions.required`, `post_conditions.required`, `output_schema`, `conditions`, `tools`, `retry_policy`, `guards`. The full DSL spec is in `policies/policy_dsl_spec.md`.

## Testing Patterns

Tests use **golden traces** — deterministic fixtures in `tests/golden_traces/` that encode expected governance behavior:

- `golden_policy_v1.yaml` + `golden_schema.json` — test policy and output schema
- `golden_invocation_success.json` / `golden_invocation_failure.json` — valid and invalid invocations
- `golden_expected_audit.json` — stable fields to assert against (excludes timestamps/checksums)

Test files follow a naming convention: `test_golden_trace_success.py`, `test_golden_trace_failure.py`, `test_audit_artifact_contract.py`. When adding new governance behaviors, create paired success/failure golden traces.

Only assert **stable** audit fields (`model_provider`, `model_identifier`, `policy_version`, `role`). Timestamps and checksums are volatile.

## Dependencies

`PyYAML`, `jsonschema`, `pytest`, `flake8` — listed in `requirements.txt`.
