# Golden Traces CI Guide

This document explains how to integrate golden traces into CI pipelines so that
governance violations are detected automatically before merges.

Golden traces are executable governance specifications. In CI, they guard
against:

- Accidental policy regressions
- Schema violations
- Model integration drift
- Invariant changes without intent

## CI Goals

A golden trace CI pipeline should:

1. Validate every golden trace success case passes
2. Confirm every golden failure case fails as expected
3. Ensure audit artifacts match golden contracts
4. Block merges on unexpected behavior changes

## Recommended CI Workflow

Canonical GitHub Actions workflow snippet:

```yaml
name: "Golden Trace Governance Checks"

on:
  pull_request:
    branches:
      - main
      - dev

jobs:
  golden-traces:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.10"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e .[dev]

      - name: Run Golden Trace Tests
        run: |
          pytest tests/test_golden_trace_success.py \
                 tests/test_golden_trace_failure.py \
                 tests/test_audit_artifact_contract.py

      - name: Report Test Results
        run: echo "Golden trace tests completed"
```

## Interpretation of Results

### All Tests Pass

Governance rules are consistent with expectations. CI may proceed with merge.

### Failure Cases

Failures indicate:

- A governance rule changed unintentionally
- A policy or schema change broke expectations
- A model integration produced unexpected outputs
- A new model provider behaves differently

The CI failure output should include:

- Which golden trace failed
- What schema validation was violated
- A diff against expected audit fields

## Tips for CI Integration

### Use Versioned Golden Fixtures

When golden artifacts are updated intentionally, version them:

- `golden_policy_v2.yaml`
- `golden_schema_v2.json`
- `golden_expected_audit_v2.json`

This helps CI distinguish intentional from unintentional changes.

### Keep Golden Traces Fast

Avoid heavy external calls inside golden trace tests.

Stub or mock model calls so CI runs quickly and deterministically.

## Block Unintentional Drift

CI should enforce:

- No silent failures
- No skipped golden tests
- No bypass of the test suite
- No conditional test avoidance

CI gates should be fail-closed.

## Summary

Golden trace CI integration ensures the governance layer:

- Remains stable over time
- Detects regressions automatically
- Survives model upgrades and policy changes
- Shields production from silent behavior drift
