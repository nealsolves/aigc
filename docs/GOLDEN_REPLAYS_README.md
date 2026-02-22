# Golden Replays for AIGC Governance

This document defines golden replays for the AIGC Governance SDK.
It is a single source of truth for humans, language models, and agents.

Golden replays are deterministic fixtures that encode expected governance
behavior and run as regression tests.

## Purpose

Golden replays exist to:

- Detect unintended governance changes
- Keep policy and schema enforcement stable
- Validate audit artifact contracts
- Make expected behavior explicit and testable

## Required Artifacts

Canonical layout:

```text
tests/
|-- golden_replays/
|   |-- golden_invocation_success.json
|   |-- golden_invocation_failure.json
|   |-- golden_policy_v1.yaml
|   |-- golden_schema.json
|   `-- golden_expected_audit.json
|-- test_golden_replay_success.py
|-- test_golden_replay_failure.py
`-- test_audit_artifact_contract.py
```

Artifact contract:

- `golden_policy_v1.yaml`: policy used for enforcement
- `golden_schema.json`: output schema used for validation
- `golden_invocation_success.json`: invocation that must pass
- `golden_invocation_failure.json`: invocation that must fail
- `golden_expected_audit.json`: stable expected audit fields

## Test Mapping

- `test_golden_replay_success.py`: valid invocation must succeed
- `test_golden_replay_failure.py`: invalid invocation must fail
- `test_audit_artifact_contract.py`: required audit fields must exist

Together these tests keep governance behavior invariant unless intentionally
versioned.

## Authoring Rules

1. Keep each replay focused on one behavior dimension.
2. Version artifacts when behavior changes intentionally.
3. Assert only stable fields in expected audit artifacts.
4. Pair complex success replays with corresponding failure replays.

Stable audit fields usually include:

- `audit_schema_version`
- `model_provider`
- `model_identifier`
- `policy_version`
- `role`
- `policy_file`
- `policy_schema_version`
- `enforcement_result`

Avoid strict checks on volatile fields like timestamps or full checksums unless
you canonicalize them.

## Automatic Golden Replay Generation Pipeline

Use `scripts/generate_golden_replays.py` to build fixtures from invocation logs.

### What This Pipeline Does

The generator:

1. Reads recorded invocation objects from an input JSON file.
2. Applies governance enforcement per invocation.
3. Normalizes fixture data for deterministic test reuse.
4. Writes golden invocation JSON fixtures.
5. Writes expected audit templates with stable fields.

### Expected Invocation Log Format

Input file example:

```json
[
  {
    "model_provider": "openai",
    "model_identifier": "gpt-4.1",
    "role": "planner",
    "policy_file": "policies/base_policy.yaml",
    "input": {},
    "output": {},
    "context": {}
  }
]
```

Requirements:

- `policy_file` must point to a valid policy
- `context` must include required preconditions
- `output` should match the active schema

### Run the Generator

```bash
python scripts/generate_golden_replays.py --input logs/invocations.json
```

Typical outputs:

- `tests/golden_replays/auto_golden_invocation_0.json`
- `tests/golden_replays/auto_golden_expected_audit_0.json`

### What Gets Generated

- Deterministic invocation fixtures
- Expected audit templates with stable fields only

Volatile fields are intentionally omitted from expected audit templates.

Example generated invocation fixture:

```json
{
  "model_provider": "openai",
  "model_identifier": "gpt-4.1",
  "role": "planner",
  "policy_file": "policies/base_policy.yaml",
  "input": {},
  "output": {},
  "context": {}
}
```

Example expected audit template:

```json
{
  "audit_schema_version": "1.0",
  "model_provider": "openai",
  "model_identifier": "gpt-4.1",
  "policy_version": "1.0",
  "role": "planner",
  "policy_file": "policies/base_policy.yaml",
  "policy_schema_version": "http://json-schema.org/draft-07/schema#",
  "enforcement_result": "PASS"
}
```

Fields that vary run-to-run, such as timestamps and full checksums, should be
validated in contract tests rather than strict golden equality checks.

### Workflow Integration

Developer workflow:

1. Record invocations during development.
2. Run the generator periodically.
3. Review generated fixtures.
4. Commit approved fixtures.

CI workflow:

1. Run golden replay tests on pull requests.
2. Block merges on mismatches.
3. Version fixtures when policy or schema changes are intentional.

### Versioning Golden Replays

When a fixture changes intentionally, introduce versioned file names, for
example:

- `golden_policy_v2.yaml`
- `golden_schema_v2.json`
- `golden_expected_audit_v2.json`
- `auto_golden_invocation_v2_0.json`

This preserves historical behavior checks and supports controlled upgrades.

### Best Practices

- Inspect generated fixtures before committing them.
- Remove values that are non-deterministic across runs.
- Keep file names aligned with policy or schema version identifiers.
- Maintain both success and failure replay coverage.

### Why This Matters

Automatic replay generation ensures:

- Golden tests reflect real-world invocation behavior.
- Governance invariants stay protected over time.
- Test coverage evolves with system and policy changes.
- Humans and agents can generate valid fixtures consistently.

## Update Workflow

1. Modify policy, schema, or enforcement logic.
2. Run golden replay tests.
3. Classify failures as intentional or unintentional.
4. If intentional, add or version artifacts.
5. Keep older versions when historical behavior must stay auditable.

## Governance Contract

Golden replays are executable contract artifacts:

> Behavior in a golden replay must remain true unless replaced by an
> intentional, versioned update.

This protects CI pipelines from silent drift during model upgrades, policy
evolution, and multi-contributor changes.
