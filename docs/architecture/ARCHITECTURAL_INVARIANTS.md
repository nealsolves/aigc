# AIGC Architectural Invariants

This document defines the non-negotiable engineering invariants of the AIGC Governance SDK.

These invariants exist to prevent architectural drift.

Any change that violates these invariants must not be merged.

If an invariant must change, the change requires:

1. An ADR
2. Updated golden replay tests
3. Updated CI release gates
4. Documentation updates

---

## 1. Deterministic Governance Boundary

Governance must be deterministic.

Given identical:

* policy
* invocation input
* invocation output
* context

The enforcement result must always be identical.

No randomness is allowed in governance logic.

The governance system must never depend on:

* LLM output
* prompt interpretation
* probabilistic scoring

---

## 2. Fail-Closed Enforcement

Governance failures must stop execution.

Examples:

* invalid policy
* missing precondition
* unauthorized role
* tool constraint violation
* schema violation

Audit sink failures are configurable: `"raise"` mode propagates sink errors
as `AuditSinkError`; `"log"` mode (default) logs a warning and allows
enforcement to complete. The enforcement pipeline itself is always fail-closed.

The system must never degrade into permissive mode for governance gates.

There is no "warn and continue" for policy enforcement.

---

## 3. Enforcement Boundary

All governance must execute inside the enforcement pipeline.

No system component may bypass:

* policy validation
* authorization
* preconditions
* tool constraints
* schema validation
* postconditions
* audit artifact generation

All enforcement must route through the governance engine.

---

## 4. Pipeline Ordering

The enforcement pipeline executes in a fixed order.

1. guard evaluation
2. role validation
3. precondition validation
4. tool constraint validation
5. schema validation
6. postcondition validation
7. audit artifact generation

Tool validation must occur before schema validation.

Unauthorized actions must fail before output processing.

Pipeline ordering must never change without an ADR.

---

## 5. Pre-Action Enforcement Proof

Audit artifacts must prove enforcement occurred before action.

Each artifact must include:

`metadata.gates_evaluated`

This ordered list shows which gates executed.

This mechanism proves that enforcement occurred before output propagation.

---

## 6. Tamper-Evident Audit Artifacts

Audit artifacts must be immutable and verifiable.

Each artifact includes:

* input checksum
* output checksum
* timestamp
* enforcement result
* failure gate
* metadata

Artifacts include forward-compatibility placeholders:

* `risk_score` (null, reserved for future use)
* `signature` (null, reserved for future use)

Cryptographic chaining fields (`signer_key_id`, `previous_audit_checksum`)
are planned for a future release and not yet present in the audit schema.

---

## 7. Append-Only Failure Model

Governance failures accumulate during enforcement.

Failures may be added by:

* core pipeline gates
* plugin enforcement gates

Failures may never be removed.

Plugins cannot suppress governance violations.

---

## 8. Instance-Scoped Configuration

Global mutable state is discouraged for new code.

Configuration should exist within an `AIGC` instance.

Example:

```python
AIGC(
    sink=JsonFileAuditSink("audit.jsonl"),
    on_sink_failure="log",
    strict_mode=True,
    redaction_patterns=None,
)
```

The global `enforce_invocation()` function and `set_audit_sink()` registry
remain available for backward compatibility. New integrations should prefer
instance-scoped `AIGC.enforce()`.

---

## 9. Policy Composition Semantics

Policies compose via `extends` inheritance with recursive merge.

Current merge rules:

* arrays append
* dicts recurse
* scalars replace

Circular dependency chains are detected and rejected at load time.

Privilege escalation prevention via `union`/`intersect`/`replace` semantics
is planned for a future release (see the Architecture Redesign Roadmap).

---

## 10. Replayable Governance

Every enforcement must be replayable.

Replay requires:

* policy
* invocation
* context

Golden replay tests verify that replay produces identical results.

Replay capability is required for compliance investigations.

---

## 11. Provider Independence

Governance must remain provider-agnostic.

The enforcement system must not depend on:

* OpenAI APIs
* Anthropic APIs
* provider-specific safety layers

AIGC governs invocation boundaries.

Not model providers.

---

## Summary

The architectural invariants guarantee:

* deterministic governance
* provable enforcement
* auditability
* security
* compliance readiness

Any change that weakens these guarantees must not be accepted.
