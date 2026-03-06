# AIGC Release Gates

This document defines the mandatory verification gates that must pass before a release.

CI enforces these gates.

If any gate fails, the release must stop.

---

## v0.2 Release Gates

### Determinism Guarantee

Repeated enforcement with identical inputs must produce identical results.

Verification:

* 1000 repeated runs
* same checksum

---

### Concurrency Safety

Enforcement must be safe across threads.

Verification:

* 50 concurrent enforcement threads
* no shared state corruption

---

### Precondition Bypass Impossible

Trivial values must not satisfy typed preconditions.

Examples tested:

* `true`
* `false`
* `0`
* `""`
* `null`

These must fail validation.

---

### Pipeline Ordering

Tool constraint validation must run before schema validation.

Test scenario:

Invocation that violates both constraints.

Expected result:

* `failure_gate = tool_validation`
* Schema validation must not execute.

---

### Pre-Action Boundary Proof

Audit artifact must include:

`metadata.gates_evaluated`

CI verifies gate order.

---

### Exception Sanitization

Sensitive data must not appear in audit artifacts.

Patterns scanned:

* API keys
* emails
* SSNs

Sanitized output required.

---

### Audit Artifact Schema

All artifacts must validate against:

`audit_artifact.schema.json`

---

### Documentation Completeness

Release must include updated documentation:

* README
* policy DSL specification
* migration guide

---

### Examples Verification

All example programs must run successfully.

---

### Test Coverage

Minimum required coverage:

>= 90%

---

## v0.3 Additional Gates

### Risk Score Determinism

Risk scoring must be deterministic.

Same invocation must produce identical risk score.

---

### Artifact Signature Verification

Signed artifacts must verify correctly.

Tampered artifacts must fail verification.

---

### Policy Restriction Validation

Child policies must not escalate privileges.

Fuzz testing validates composition rules.

---

### Plugin Isolation

Custom gates must not suppress core failures.

Failures must remain append-only.

---

## v1.0 Release Gates

### Workflow Governance

Multi-step workflow governance must succeed.

Example:

* 5 step agent workflow
* tool budgets enforced
* workflow postconditions validated

---

### Escalation Policy

High-risk actions must trigger escalation.

Timeout must default to denial.

---

### API Stability

Public API must follow semantic versioning.

Breaking changes require major version increment.

---

### Compliance Evidence

Audit artifacts must support compliance review.

Artifacts must demonstrate:

* integrity
* completeness
* correlation
* retention metadata
