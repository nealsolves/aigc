# AIGC Release Gates

This document defines the verification gates for each release milestone,
organized by enforcement method.

---

## CI-Enforced Gates

These gates are automated in CI workflows (`sdk_ci.yml`, `doc_parity.yml`,
`release.yml`). If any fails, CI blocks the release.

### Test Coverage

Minimum required coverage: >= 90%.

Enforced via `pytest --cov-fail-under=90`.

### Lint

`flake8 aigc` must pass with zero errors.

### Markdown Lint

`npx markdownlint-cli2 "**/*.md"` must pass with zero errors.

### Policy/Schema Validation

All `policies/*.yaml` must validate against `schemas/policy_dsl.schema.json`.

Both `policy_dsl.schema.json` and `audit_artifact.schema.json` must pass
`Draft7Validator.check_schema()`.

### Golden Replay Regression

Golden replay test files must pass. CI runs these explicitly:

* `test_golden_replay_success.py`
* `test_golden_replay_failure.py`
* `test_golden_replay_guards.py`
* `test_golden_replay_tools.py`
* `test_golden_replay_conditions.py`
* `test_golden_replay_composition.py`
* `test_golden_replay_risk_scoring.py`
* `test_golden_replay_signing.py`
* `test_audit_artifact_contract.py`

### Documentation Parity

`python scripts/check_doc_parity.py` must pass. Validates current-state
values, public API boundary, schema-example parity, link hygiene, archive
hygiene, gate-ID consistency, and parity-set existence.

---

## Test-Suite-Verified Gates

These properties are verified by tests in the full pytest suite (which CI
runs), but are not separate CI steps with explicit pass/fail reporting.

### Determinism Guarantee

Repeated enforcement with identical inputs must produce identical results.

Verified by `test_checksum_determinism.py` and golden replay tests.

### Pipeline Ordering

Tool constraint validation must run before schema validation.

Verified by `test_pre_action_boundary.py` sentinel tests.

### Pre-Action Boundary Proof

Audit artifact must include `metadata.gates_evaluated`.

CI verifies gate order via sentinel tests.

### Precondition Bypass Impossible

Trivial values must not satisfy typed preconditions.

Verified by `test_adversarial_preconditions.py`.

### Audit Artifact Schema

All artifacts must validate against `audit_artifact.schema.json`.

Verified by `test_audit_artifact_contract.py`.

### Risk Score Determinism (v0.3)

Risk scoring must be deterministic. Same invocation must produce
identical risk score.

Verified by `test_risk_scoring.py` and golden replay tests.

### Artifact Signature Verification (v0.3)

Signed artifacts must verify correctly. Tampered artifacts must fail
verification.

Verified by `test_signing.py`.

### Policy Restriction Validation (v0.3)

Child policies must not escalate privileges.

Verified by `test_composition_semantics.py`.

### Plugin Isolation (v0.3)

Custom gates must not suppress already-recorded core failures. Once a core
gate failure is recorded (role, precondition, tool, schema, postcondition),
no subsequent custom gate may remove it. Failures are append-only.

Note: **Pre-authorization** custom gates run before role/precondition
validation by design. A pre-auth gate failure means downstream core gates
do not execute — this is intentional pipeline sequencing, not failure
suppression. The non-suppression guarantee applies to gates running *after*
a core gate has already evaluated and recorded a failure.

Verified by `test_custom_gates.py::test_post_auth_gate_cannot_suppress_role_failure`.

---

## Release Checklist (Manual Verification)

These items require manual verification before tagging a release.

### Documentation Completeness

Release must include updated documentation:

* README
* policy DSL specification

### Packaging (Restricted-Environment Verification)

Verify that both standard and no-network builds succeed before tagging.

**Standard build** (requires internet access to fetch build-system deps):

```bash
python -m build
```

**No-isolation build** (works in offline/enterprise environments):

```bash
python -m build --no-isolation
```

Both `aigc_sdk-<version>.tar.gz` (sdist) and `aigc_sdk-<version>-py3-none-any.whl` (wheel) must be produced. If only `--no-isolation` succeeds, document the reason in the release notes.

### Concurrency Safety

Enforcement must be safe across threads. Manual or local verification
recommended for major releases.

### Exception Sanitization

Sensitive data must not appear in audit artifacts. Verified by manual
review and targeted tests.

---

## Future Hardening (Planned Gates)

These gates are planned for future releases and are not yet enforced.

### Explicit Determinism Stress Test

1000 repeated runs producing identical checksums as explicit CI step.

### Examples Verification

Automated execution of example programs. Requires `examples/` directory
to be established.

---

## v1.0 Release Gates (Planned)

### Workflow Governance

Multi-step workflow governance must succeed.

### Escalation Policy

High-risk actions must trigger escalation. Timeout must default to denial.

### API Stability

Public API must follow semantic versioning. Breaking changes require
major version increment.

### Compliance Evidence

Audit artifacts must support compliance review: integrity, completeness,
correlation, retention metadata.
