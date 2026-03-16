# AIGC Threat Model

This document describes the threat model for the AIGC Governance SDK.

AIGC enforces deterministic governance over AI invocations.
The purpose of this threat model is to identify how governance could fail
and how the architecture prevents those failures.

This document assumes an adversarial environment.

---

## Security Objective

AIGC must guarantee:

1. governance enforcement occurs before irreversible actions
2. enforcement decisions are deterministic
3. governance artifacts are tamper-evident
4. enforcement cannot be bypassed through trivial manipulation
5. extensions cannot weaken core governance guarantees

---

## Security Boundary

The security boundary of AIGC is the enforcement engine.

```
Application
│
▼
AIGC Enforcement Boundary
│
▼
External Systems
```

All AI invocation governance must pass through this boundary.

Anything outside the enforcement boundary is considered untrusted.

---

## Threat Actor Classes

AIGC considers four attacker types.

### 1. Negligent Integrator

**Capabilities:**

* incorrectly configures policy
* provides incomplete invocation context
* bypasses enforcement APIs

**Risks:**

* governance bypass
* incomplete validation

**Mitigations:**

* fail-closed enforcement
* policy schema validation
* required invocation fields
* typed precondition validation

---

### 2. Malicious Insider

**Capabilities:**

* modifies invocation payload
* attempts to manipulate context
* attempts to hide violations

**Risks:**

* unauthorized tool execution
* role escalation
* policy bypass

**Mitigations:**

* deterministic enforcement
* role validation
* tool constraint enforcement
* audit artifact checksums
* enforcement ordering guarantees

---

### 3. Malicious Plugin Author

**Capabilities:**

* writes custom enforcement gates
* attempts to weaken enforcement logic
* attempts to hide failures

**Risks:**

* governance bypass through extension points

**Mitigations:**

* append-only failure model
* plugin isolation
* restricted extension points
* CI verification of failure propagation

Plugins cannot remove or suppress failures.

---

### 4. External Attacker

**Capabilities:**

* prompt injection
* malicious input payloads
* adversarial model output

**Risks:**

* tool abuse
* data exfiltration
* policy evasion

**Mitigations:**

* deterministic governance
* tool constraint validation
* schema validation
* precondition enforcement

AIGC does not trust model output.

All model output must pass schema validation.

---

## Attack Surface

The AIGC system exposes the following surfaces.

---

### Policy Files

**Attack vector:** malicious policy modification

**Risks:**

* unauthorized permissions
* weakened governance rules

**Mitigations:**

* policy schema validation
* optional policy signing
* versioned policy files

---

### Invocation Context

**Attack vector:** manipulated invocation payload

**Risks:**

* precondition bypass
* role escalation

**Mitigations:**

* strict field validation
* typed preconditions
* required context fields

---

### Model Output

**Attack vector:** malicious model output

**Risks:**

* schema violation
* tool abuse
* unsafe actions

**Mitigations:**

* schema validation
* postcondition checks
* tool constraints

Model output is treated as untrusted input.

---

### Tool Invocation

**Attack vector:** unauthorized external actions

**Examples:**

* uncontrolled web search
* database writes
* external API calls

**Mitigations:**

* tool constraint validation
* tool budgets
* allowed tool lists

---

## Governance Bypass Attempts

This section describes common bypass attempts and their mitigations.

---

### Bypass Attempt: Trivial Precondition

**Example:**

```python
context = { "tenant_id": true }
```

**Risk:** Key existence validation incorrectly passes.

**Mitigation:** Typed preconditions required.

```yaml
tenant_id:
  type: string
  pattern: "^[A-Z0-9]{8}$"
```

---

### Bypass Attempt: Plugin Suppresses Failure

**Example:** plugin removes failure

**Mitigation:** Failures are append-only. Plugins cannot remove failures.

---

### Bypass Attempt: Enforcement Ordering Manipulation

**Example:** schema validation before tool validation

**Risk:** Unauthorized tool calls could execute.

**Mitigation:** Fixed pipeline ordering. CI verifies pipeline ordering.

---

### Bypass Attempt: Silent Enforcement Failure

**Example:** audit sink failure ignored

**Risk:** audit artifact lost

**Mitigation:** Audit failures cause enforcement failure. Fail-closed behavior required.

---

## Enforcement Proof

Audit artifacts prove enforcement occurred.

Artifacts contain:

`metadata.gates_evaluated`

Example:

```json
[
  "guard_evaluation",
  "role_validation",
  "precondition_validation",
  "tool_validation"
]
```

This proves governance occurred before action.

---

## Audit Integrity

Artifacts include checksums.

* `input_checksum`
* `output_checksum`

Governance-enrichment fields (v0.3.0):

* `risk_score` — populated by the risk scoring engine when the governing policy declares risk configuration (v0.3.0)
* `signature` — populated by `ArtifactSigner` (HMAC-SHA256) when signing is enabled on the AIGC instance (v0.3.0)

Cryptographic chaining fields (v0.3.0):

* `chain_id`, `chain_index`, `previous_audit_checksum` — populated by `AuditChain` for tamper-evident sequential integrity (v0.3.0)

If any artifact is modified, checksum verification fails.

---

## Supply Chain Security

AIGC dependencies must be verified.

Recommended practices:

* pinned dependency versions
* vulnerability scanning
* reproducible builds

---

## Non-Goals

AIGC does not attempt to solve:

* model hallucinations
* model bias
* provider safety systems

AIGC governs invocation boundaries, not model reasoning.

---

## Residual Risk

Remaining risks include:

* integrator misuse of enforcement APIs
* compromised runtime environments
* malicious policy authors

These risks must be addressed through operational controls.

---

## Security Posture Summary

AIGC provides the following guarantees:

* deterministic governance enforcement
* fail-closed security model
* provable enforcement boundary
* tamper-evident audit artifacts
* plugin-safe extension architecture

These guarantees make AIGC suitable for environments requiring:

* regulatory compliance
* auditability
* AI governance enforcement
* controlled agent workflows
