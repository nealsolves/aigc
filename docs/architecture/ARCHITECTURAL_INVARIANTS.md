# AIGC Architectural Invariants

This document defines the non-negotiable engineering invariants of the AIGC Governance SDK.

These invariants exist to prevent architectural drift.

Current runtime baseline: `v0.3.3`, with audit schema `v1.4`.

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

Core governance gates (role, precondition, tool, schema, postcondition) are
always fail-closed. Risk scoring has two explicitly configured non-blocking
modes: `risk_scored` (records exceedance in artifact, does not block) and
`warn_only` (records without blocking). Only `strict` mode blocks on risk
threshold exceedance. Sink failures are configurable and do not affect the
governance decision.

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

1. custom gates (pre_authorization)
2. guard evaluation
3. role validation
4. precondition validation
5. tool constraint validation
6. custom gates (post_authorization)
7. custom gates (pre_output)
8. schema validation
9. postcondition validation
10. custom gates (post_output)
11. risk scoring (mode-dependent: strict blocks; risk_scored and warn_only record only)
12. audit artifact generation

Tool validation must occur before schema validation.

Unauthorized actions must fail before output processing.

Pipeline ordering must never change without an ADR.

---

## 5. Pre-Action Enforcement Proof

Audit artifacts must prove enforcement occurred before action.

Each artifact must include ordered gate evidence:

* unified mode: `metadata.gates_evaluated`
* split mode: `metadata.pre_call_gates_evaluated`
* split mode Phase B completion: `metadata.post_call_gates_evaluated`

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

Artifacts include governance-enrichment fields introduced in v0.3.0 (M2):

* `risk_score` — populated by the risk scoring engine when the policy declares risk configuration
* `signature` — populated by `ArtifactSigner` (HMAC-SHA256 via `HMACSigner`) when signing is enabled
* `chain_id`, `chain_index`, `previous_audit_checksum` — populated by `AuditChain` for sequential integrity verification

---

## 7. Append-Only Failure Model

Governance failures accumulate during enforcement.

Failures may be added by:

* core pipeline gates
* plugin enforcement gates

Failures may never be removed.

Plugins cannot suppress already-recorded governance violations. Once a core
gate records a failure, no subsequent plugin gate may remove or override it.
Failures are append-only within a pipeline execution.

Pre-authorization custom gates execute before core validation gates. A
pre-auth gate failure halts the pipeline before core gates run; this is
intentional pipeline sequencing. Their failures are classified as
`custom_gate_violation`, not a suppression of a recorded core failure,
because no core gate has yet evaluated.

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
is implemented in v0.3.0 (M2) through the `composition_strategy` policy field.

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

## 12. Split Enforcement Execution Mode

Split enforcement is an additive execution mode introduced in `v0.3.2`.

It does not change any architectural invariant. Specifically:

* Gate ordering remains fixed (Invariant 4). Phase A executes authorization gates; Phase B executes output gates; the model call occurs at the boundary between them.
* Fail-closed behavior remains unchanged (Invariant 2). Phase A FAIL stops execution before the model call.
* Exactly one audit artifact is emitted per invocation attempt (Invariant 6). A Phase-A-only FAIL produces one FAIL artifact. A complete split invocation produces one final artifact.
* Unified mode remains backward-compatible and fully supported.
* Policy evaluation in Phase B must use the Phase A effective policy — no reload from disk.

Hosts using legacy unified mode via `pre_call_enforcement=False` are unaffected
by split mode internals; the pipeline ordering and artifact contract are unchanged.

---

## 13. Additive Audit Schema Evolution

Schema versions may only add optional fields. No existing required field may be
removed or renamed. No new required fields may be added. Every artifact valid
under schema version `N` must remain valid under version `N+1`.

---

## 14. Provenance is Optional, Not Enforcement-Gating

`provenance` in audit artifacts is always optional. The enforcement pipeline
must not fail or alter its gate sequence based on the presence or absence of
provenance metadata unless a `ProvenanceGate` is explicitly registered by the
host.

---

## 15. Lineage Reconstruction is Read-Only and Off Hot Path

`AuditLineage` reads existing audit artifacts to reconstruct dependency graphs.
It must not modify artifacts, invoke enforcement, or run during the enforcement
hot path unless the host explicitly calls it.

---

## 16. One Audit Artifact Per Invocation Attempt

Every invocation attempt — whether it succeeds or fails, whether it runs in
unified mode or split mode — must produce exactly one audit artifact. This
invariant holds across `enforce_invocation`, `enforce_pre_call`/`enforce_post_call`,
`AIGC.enforce`, and `@governed`.

---

## 17. Advisory Utilities Must Not Alter Enforcement Semantics

`RiskHistory` and similar advisory utilities must not change the enforcement
pipeline outcome, gate order, or audit artifact content for any invocation they
observe. They are observers, not participants.

---

## Summary

The architectural invariants guarantee:

* deterministic governance
* provable enforcement
* auditability
* security
* compliance readiness

Any change that weakens these guarantees must not be accepted.
