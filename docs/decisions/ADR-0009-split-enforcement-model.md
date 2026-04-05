# ADR-0009: Split Enforcement Model

Date: 2026-04-04
Status: Accepted
Owners: Neal

---

## Context

AIGC `v0.3.1` enforces governance in unified post-call mode:

- `enforce_invocation()` accepts a complete invocation with `output`
- `enforce_invocation_async()` mirrors that behavior asynchronously
- `@governed` executes the wrapped function before governance checks

This means some deniable calls still consume tokens before rejection.

The repository already enforces several non-negotiable invariants:

- fixed gate ordering
- fail-closed behavior
- exactly one artifact per invocation attempt
- backward-compatible public APIs
- additive audit-schema evolution

`v0.3.2` needs a split model that stops pre-call-deniable executions without
breaking the released unified contract.

## Decision

Adopt split enforcement as an additive execution model.

The public surface adds:

- `enforce_pre_call(invocation)`
- `enforce_post_call(pre_call_result, output)`
- async variants of both
- `AIGC.enforce_pre_call()` and `AIGC.enforce_post_call()`
- `PreCallResult`
- `@governed(..., pre_call_enforcement=False)`

Unified mode remains supported and backward-compatible.

## Detailed Decision

### 1. Split Phases

Phase A runs before the model call and covers:

1. policy load
2. `pre_authorization` custom gates
3. guard evaluation and condition resolution
4. role validation
5. precondition validation
6. tool constraint validation
7. `post_authorization` custom gates

Phase B runs after the model call and covers:

1. `pre_output` custom gates
2. output schema validation
3. postcondition validation
4. `post_output` custom gates
5. risk scoring
6. final artifact generation and emission

### 2. `enforce_pre_call` Invocation Shape

`enforce_pre_call()` accepts the unified invocation shape minus `output`.

Required keys:

- `policy_file`
- `model_provider`
- `model_identifier`
- `role`
- `input`
- `context`

`output` is not required.

### 3. Invocation Validation Factoring

Invocation validation is factored into:

- `_validate_invocation_core(invocation)` for common checks
- `_validate_invocation(invocation)` for unified mode, which adds `output`
- `_validate_pre_call_invocation(invocation)` for split pre-call mode

This preserves the current unified contract while enabling split entry points.

### 4. `PreCallResult`

`PreCallResult` is a module-level frozen slotted dataclass:

```python
@dataclass(frozen=True, slots=True)
class PreCallResult:
    effective_policy: Mapping[str, Any]
    resolved_guards: tuple[dict[str, Any], ...]
    resolved_conditions: Mapping[str, Any]
    phase_a_metadata: Mapping[str, Any]
    invocation_snapshot: Mapping[str, Any]
    policy_file: str
    model_provider: str
    model_identifier: str
    role: str
    _consumed: bool = field(init=False, default=False, repr=False, compare=False)
```

`invocation_snapshot` captures exactly:

- `policy_file`
- `model_provider`
- `model_identifier`
- `role`
- `input`
- `context`

Phase B reconstructs the full invocation as `invocation_snapshot + output`.

### 5. `_consumed` Lifecycle Model

`PreCallResult` is logically immutable with one internal lifecycle bit.

Rules:

- `_consumed` starts as `False`
- `enforce_post_call()` validates that `_consumed` is still `False`
- on first valid consumption, `enforce_post_call()` flips `_consumed` to `True`
  using `object.__setattr__`
- second use fails closed with `InvocationValidationError`

`_consumed` is internal lifecycle state, not public API.

### 6. Concurrency Scope

`PreCallResult` is single-threaded.

Concurrent consumption of the same object is unsupported and undefined.

This is acceptable because the intended lifecycle is one Phase A result for one
Phase B call, and the decorator path keeps both phases in one wrapper scope.

### 7. Pickling Contract

Pickle round-trip preserves `_consumed` state.

- an unused token stays unused after round-trip
- a consumed token stays consumed after round-trip

Default dataclass pickling is sufficient because `_consumed` is a declared
field.

### 8. Phase B Policy Constraint

Phase B must not call `load_policy()`.

It must use `PreCallResult.effective_policy` from Phase A. This avoids policy
reload drift and preserves the exact Phase A decision basis.

### 9. Artifact Semantics

Exactly one artifact is emitted per invocation attempt.

- Phase A FAIL:
  - one final FAIL artifact
  - `metadata.enforcement_mode = "split_pre_call_only"`
- Phase A PASS then Phase B PASS or FAIL:
  - one final artifact
  - `metadata.enforcement_mode = "split"`
- Unified mode:
  - one artifact
  - `metadata.enforcement_mode = "unified"`

Phase-A-only FAIL artifacts use the checksum of `{}` as `output_checksum`.

No two-artifact model is allowed.

### 10. Telemetry

Span names:

- unified: `aigc.enforce_invocation`
- split Phase A: `aigc.enforce_pre_call`
- split Phase B: `aigc.enforce_post_call`

Required attribute:

- `aigc.enforcement_mode`

## Consequences

### Positive

- unauthorized or invalid pre-call invocations can be rejected before model
  execution
- split wrappers gain explicit pre-action governance behavior
- unified integrations continue to work unchanged

### Negative

- internal enforcement orchestration becomes more complex
- manual split integrations can misuse `PreCallResult`
- the enforcement core must preserve parity between unified and split flows

### Deferred / Out of Scope

- runtime logical staleness detection for manual split mode
- concurrent-use protection beyond documented unsupported behavior
- new split-specific retry helpers

## Validation

The change is accepted only if:

- unified tests remain green
- split tests prove Phase A and Phase B semantics
- one-artifact behavior is preserved across all paths
- schema `v1.3` remains additive
- Phase B never reloads policy

## References

- `docs/design/v0.3.2_DESIGN_SPEC.md`
- `docs/plans/v0.3.2_IMPLEMENTATION_PLAN.md`
- `docs/plans/v0.3.2_TEST_PLAN.md`
- `docs/plans/v0.3.2_SCHEMA_DIFF.md`
- `aigc/_internal/enforcement.py`
- `aigc/_internal/decorators.py`
- `aigc/_internal/audit.py`
- `docs/architecture/ARCHITECTURAL_INVARIANTS.md`
