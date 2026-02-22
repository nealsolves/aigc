# ADR-0001: Phase 1 Failure Audit Emission (Course Correction)

Date: 2026-02-16
Status: Accepted
Owners: AIGC SDK Team

---

## Context

During PR1 validation on 2026-02-16, we discovered a critical gap in the Phase 1 audit artifact contract: **enforcement failures do not emit audit artifacts**.

When any validation gate fails (role, preconditions, schema, postconditions), the enforcement pipeline raises an exception but does **not** generate an audit artifact documenting the failure. This violates the core governance principle:

> Every enforcement attempt must produce an audit artifact, whether PASS or FAIL.

### Why This Was Missed

The implementation plan defined Phase 1.6 (Enriched Audit Artifacts) focused on PASS artifacts with `enforcement_result: "PASS"`. The plan did not explicitly call out FAIL artifact emission as a separate deliverable, assuming it would be handled implicitly. This was a planning oversight.

### Constraints

- Compliance requires auditing failed attempts (attempted policy violations)
- Forensic analysis needs to know what failed and why
- The audit contract schema already supports `enforcement_result` and `failures` fields
- This should have been in Phase 1, not Phase 2
- The fail-closed behavior must be preserved (exceptions still propagate)

---

## Decision

Add **Phase 1.8: Failure Audit Artifact Emission** as the final Phase 1 deliverable before proceeding to Phase 2.

### Implementation

1. **Wrap enforcement pipeline in try/except** to catch all `AIGCError` subclasses
2. **Generate FAIL audit artifact** before re-raising exceptions:
   - `enforcement_result: "FAIL"`
   - `failure_gate`: which gate failed (e.g., "role_validation", "precondition_validation")
   - `failure_reason`: human-readable exception message
   - `failures`: structured failure list from exception details
   - All standard audit fields (checksums, timestamps, policy metadata)
3. **Attach audit artifact to exception** via `exc.audit_artifact` attribute
4. **Re-raise original exception** (fail-closed behavior preserved)
5. **Update audit artifact schema** to formalize `failure_gate` and `failure_reason` fields

### Exception-to-Gate Mapping

```python
InvocationValidationError → "invocation_validation"
PolicyLoadError/PolicyValidationError → "invocation_validation"
GovernanceViolationError (role check) → "role_validation"
PreconditionError → "precondition_validation"
SchemaValidationError → "schema_validation"
GovernanceViolationError (postcondition) → "postcondition_validation"
FeatureNotImplementedError → "feature_not_implemented"
```

---

## Options Considered

### Option A: FAIL Audits in Phase 1 (Chosen)

**Pros:**
- Completes the audit contract before Phase 2 complexity
- Forensic analysis available immediately
- Single source of truth for all enforcement outcomes
- Phase 2 features (guards, tools, retry) will inherit FAIL audit emission

**Cons:**
- Delays Phase 2 start by ~1-2 days
- Requires updating Phase 1 Definition of Done

### Option B: FAIL Audits in Phase 2

**Pros:**
- Doesn't delay Phase 2 start
- Could be bundled with Phase 2.5 (Extended Audit Artifacts)

**Cons:**
- Phase 1 audit contract incomplete (PASS-only)
- Forensic gap between Phase 1 and Phase 2
- Phase 2 adds more failure modes (guards, tools) — harder to retrofit

### Option C: FAIL Audits in Phase 3

**Pros:**
- Could be bundled with audit sink implementation

**Cons:**
- Unacceptable governance gap through Phase 1 and Phase 2
- Violates audit contract principle
- No forensic evidence for early testing

---

## Consequences

### What Becomes Easier

- **Complete audit trail** — every enforcement attempt is audited (PASS or FAIL)
- **Forensic analysis** — failures are documented with gate, reason, and context
- **Compliance** — failed attempts are auditable for policy violation detection
- **Testing** — failure modes are now testable via audit artifact assertions
- **Phase 2 readiness** — guard/tool/retry failures will auto-emit FAIL audits

### What Becomes Harder

- **Exception handling** — callers must handle `exc.audit_artifact` if they want FAIL audits
- **Backward compatibility** — existing exception handlers won't see audit artifacts (but this is new functionality)

### Risks Introduced

1. **Risk:** Audit generation failure could prevent exception propagation
   **Mitigation:** Wrap audit generation in try/except — if audit fails, log warning and re-raise original exception

2. **Risk:** Audit artifacts could leak sensitive exception details
   **Mitigation:** Only include structured failure fields (code, message, field) — no raw exception output

3. **Risk:** Performance overhead from generating FAIL audits
   **Mitigation:** Audit generation is already fast (<1ms) — FAIL path adds negligible overhead

---

## Contract Impact

### Enforcement Pipeline Impact

- **Before:** Exception raised → no audit artifact
- **After:** Exception raised → FAIL audit attached to exception → exception propagated

### Audit Artifact Impact

- **New fields:**
  - `failure_gate`: string | null (enum of gate identifiers)
  - `failure_reason`: string | null (human-readable message)
- **PASS artifacts:** `failure_gate` and `failure_reason` are `null`
- **FAIL artifacts:** `failure_gate` and `failure_reason` are non-null

### Schema Impact

Updated `schemas/audit_artifact.schema.json`:
- Added `failure_gate` property (nullable enum)
- Added `failure_reason` property (nullable string)
- Both fields are optional (not in `required` array)

### Golden Replays Impact

- **New golden replay:** `tests/golden_replays/golden_invocation_failure_with_audit.json`
- **New test:** `tests/test_golden_replay_failure_with_audit.py`
- **Updated tests:** `tests/test_enforcement_pipeline.py` (added 5 FAIL audit tests)

### Error Taxonomy Impact

- **Updated:** `AIGCError` base class gains `audit_artifact: dict | None` attribute
- **No changes** to exception hierarchy or error codes

---

## Validation

### Tests Added

1. `test_role_failure_emits_audit_artifact` — role validation FAIL audit
2. `test_precondition_failure_emits_audit_artifact` — precondition FAIL audit
3. `test_schema_failure_emits_audit_artifact` — schema validation FAIL audit
4. `test_postcondition_failure_emits_audit_artifact` — postcondition FAIL audit
5. `test_success_has_null_failure_fields` — PASS audit has null failure fields
6. `test_golden_replay_failure_with_audit` — golden replay regression

### Coverage Impact

- **Before Phase 1.8:** 93% coverage (199 statements)
- **After Phase 1.8:** 93% coverage (226 statements, +27 new lines)
- **Test count:** 35 → 41 tests (+6 new tests)

### Acceptance Criteria

- [x] Role validation failure produces FAIL audit artifact + raises `GovernanceViolationError`
- [x] Precondition failure produces FAIL audit artifact + raises `PreconditionError`
- [x] Schema validation failure produces FAIL audit artifact + raises `SchemaValidationError`
- [x] Postcondition failure produces FAIL audit artifact + raises `GovernanceViolationError`
- [x] FAIL audits include same checksums/metadata as PASS audits
- [x] Golden replay created and passing
- [x] Audit artifact schema updated with FAIL-specific fields

---

## Plan Path (Before and After)

### Original Plan Path (Before Course Correction)

```text
Phase 1 (items 1.1-1.7) → Phase 2 (guards, tools, retry)
```

### Corrected Plan Path (2026-02-16)

```text
Phase 1 (items 1.1-1.8) → Phase 2 (guards, tools, retry)
                    ↑
                    └─ 1.8 added: FAIL audit emission (critical gap)
```

### Rationale for Course Correction

Discovered during PR1 validation that FAIL audits were not emitted. This is a Phase 1 gap (audit contract completeness), not a Phase 2 feature. Must fix before adding Phase 2 complexity to ensure all future failures (guards, tools, retry) inherit FAIL audit emission.

---

## References

- Audit artifact schema: `schemas/audit_artifact.schema.json`
- Golden replay: `tests/golden_replays/golden_invocation_failure_with_audit.json`
