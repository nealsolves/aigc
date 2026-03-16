# AIGC Implementation Plan

> **Status:** Milestone 1 (v0.2.0) is complete. Milestone 2 (v0.3.0)
> implementation is tracked in `implementation_status.md`. This document
> is retained as the architectural planning record for M1 workstreams.

**Date:** 2026-03-06
**Based on:** docs/architecture/AIGC_Architecture_Redesign_and_Roadmap.md
**SDK Version:** 0.1.3 (baseline)
**Target Version:** 0.2.0 (Milestone 1) — **Completed**

---

## 1. Roadmap Interpretation

The architectural redesign transforms AIGC from a Phase 3 single-invocation enforcement
SDK into a production-grade, instance-scoped governance engine with:

1. **Enforcement pipeline corrections** - D-04 (tools before schema) is already fixed.
   Remaining: typed preconditions (D-01), JSON serializability validation (D-14).
2. **Governance invariants** - Eliminate global mutable state (D-02), enforce fail-closed
   at sink layer, instance-scoped configuration via `AIGC` object.
3. **Pre-action enforcement guarantees** - `metadata.gates_evaluated` already implemented
   (ADR-0007). CI sentinel tests already enforce ordering.
4. **Audit artifact completeness** - Exception sanitization (D-05), schema bounds (D-13),
   audit artifact signing (v0.3.0), hash-chain linking (ADR-0008).
5. **Replay determinism** - Maintained throughout. All changes must preserve golden replay
   contract. Guard compilation (D-15) and caching (D-03) must not break determinism.
6. **CI-first governance validation** - `ci:pre-action-boundary` gate, schema validation,
   deterministic replay validation, coverage thresholds.

### Pre-Existing Completions

The following roadmap items are already implemented:

- **D-04 (Pipeline ordering):** Tool constraints run before schema validation.
  Verified by `test_pre_action_boundary.py`.
- **ADR-0007 (gates_evaluated):** Audit artifacts include ordered `metadata.gates_evaluated`.
- **Sentinel gate markers:** Authorization vs output gate classification in enforcement.py.

---

## 2. Implementation Workstreams

### WS-1: AIGC Instance-Scoped Configuration

**Scope:** Replace global mutable state with instance-scoped `AIGC` configuration object.
Foundation for all other workstreams.

**Affected modules:**
- `aigc/_internal/enforcement.py` - Add `AIGC` class with `enforce()` and `enforce_async()`
- `aigc/_internal/sinks.py` - Move sink registry to instance scope
- `aigc/__init__.py` - Export `AIGC` class, add backward-compat shims
- `aigc/sinks.py` - Re-export new APIs

**Architectural risks:**
- Thread safety of shared `AIGC` instance in multi-threaded deployments
- Backward compatibility for existing `enforce_invocation()` callers

**Determinism considerations:**
- `AIGC` config is immutable after construction - no runtime state changes
- Same config + same invocation = same result (determinism preserved)

**Audit implications:**
- Sink failure mode becomes configurable (`raise`/`queue`/`log`)
- Default changes to `raise` in strict mode (fail-closed at persistence)

---

### WS-2: Typed Precondition Validation (D-01)

**Scope:** Extend preconditions from key-existence checks to typed value validation
using inline JSON Schema subset.

**Affected modules:**
- `aigc/_internal/validator.py` - Add typed precondition validation
- `aigc/_internal/policy_loader.py` - Accept new precondition format
- `schemas/policy_dsl.schema.json` - Update precondition schema
- `policies/policy_dsl_spec.md` - Document new precondition syntax

**Architectural risks:**
- Backward compatibility with bare-string `required: [key]` syntax
- Performance impact of per-key JSON Schema validation

**Determinism considerations:**
- JSON Schema validation is deterministic
- Failure ordering must be stable (alphabetical key order)

**Audit implications:**
- New failure messages for typed precondition violations
- `failure_gate` remains `precondition_validation`

---

### WS-3: Exception Message Sanitization (D-05)

**Scope:** Sanitize exception messages before inclusion in audit artifacts.
Add configurable redaction patterns.

**Affected modules:**
- `aigc/_internal/audit.py` - Add `sanitize_failure_message()` function
- `aigc/_internal/enforcement.py` - Apply sanitization before artifact generation
- `schemas/audit_artifact.schema.json` - Add `redacted_fields` to artifact

**Architectural risks:**
- Regex-based sanitization may have false negatives
- Overly aggressive patterns may redact diagnostic information

**Determinism considerations:**
- Sanitization is deterministic (same input + same patterns = same output)
- Redaction patterns are fixed at AIGC instance construction time

**Audit implications:**
- Audit schema bumped to 1.2 (additive: `redacted_fields`)
- Golden replays must be updated for new artifact shape

---

### WS-4: Policy Caching (D-03)

**Scope:** LRU cache for compiled policies, keyed by `(canonical_path, file_mtime)`.
Cache lives on `AIGC` instance.

**Affected modules:**
- `aigc/_internal/policy_loader.py` - Add `PolicyCache` class
- `aigc/_internal/enforcement.py` - Use cache from AIGC instance

**Architectural risks:**
- Cache invalidation correctness (stale mtime edge cases)
- Memory usage for large cache sizes
- Race condition between mtime check and file read

**Determinism considerations:**
- Cache hit returns same policy dict - determinism preserved
- Cache miss triggers full load - identical to current behavior

**Audit implications:**
- No change to audit artifacts
- Performance improvement measurable in enforcement latency

---

### WS-5: Sink Failure Mode Configuration (D-02 completion)

**Scope:** Configurable sink failure behavior: `raise` (default), `queue`, or `log`.

**Affected modules:**
- `aigc/_internal/sinks.py` - Add failure mode handling
- `aigc/_internal/enforcement.py` - Propagate failure mode from AIGC instance

**Architectural risks:**
- `raise` mode changes existing behavior (currently `log`)
- Queue mode requires thread-safe queue implementation

**Determinism considerations:**
- Sink failure mode does not affect enforcement result (determinism preserved)
- Emission is a side effect, not part of governance logic

**Audit implications:**
- `raise` mode ensures no silent artifact loss
- `AuditSinkError` added to error taxonomy

---

### WS-6: Invocation Shape Validation (D-14)

**Scope:** Validate JSON serializability of invocation fields at pipeline entry.

**Affected modules:**
- `aigc/_internal/enforcement.py` - Add serializability check in `_validate_invocation()`

**Architectural risks:** None (additive validation at entry boundary)

**Determinism considerations:** Pure validation, no state

**Audit implications:**
- Clearer error messages for non-serializable inputs
- Errors caught at invocation time, not checksum time

---

### WS-7: Audit Schema Bounds (D-13)

**Scope:** Add `maxItems` and `maxProperties` constraints to audit schema.

**Affected modules:**
- `schemas/audit_artifact.schema.json` - Add bounds
- `aigc/_internal/audit.py` - Enforce bounds at generation time

**Architectural risks:** None (protective constraint)

**Determinism considerations:** Bounds enforcement is deterministic

**Audit implications:**
- Prevents multi-megabyte audit artifacts
- `failures` capped at 1000 items, `metadata`/`context` capped at 100 keys

---

### WS-8: Decorator Fix (D-11)

**Scope:** Use `inspect.signature()` for parameter binding instead of positional args.

**Affected modules:**
- `aigc/_internal/decorators.py` - Rewrite argument extraction
- `tests/test_decorators.py` - Add reordered-parameter tests

**Architectural risks:** None (behavioral fix)

**Determinism considerations:** No impact

**Audit implications:** Correct data in audit artifacts when parameters are reordered

---

### WS-9: Condition Resolution Improvements (D-12)

**Scope:** Emit INFO log for skipped optional conditions. Improve error diagnostics.

**Affected modules:**
- `aigc/_internal/conditions.py` - Add logging for skipped conditions
- `aigc/_internal/guards.py` - Improve error messages

**Architectural risks:** None

**Determinism considerations:** Logging is a side effect, not governance logic

**Audit implications:** Better diagnostics in guard evaluation metadata

---

### WS-10: Guard Compilation (D-15)

**Scope:** Compile guards at policy-load time. Single deep copy instead of per-guard copy.

**Affected modules:**
- `aigc/_internal/guards.py` - Optimize guard merging
- `aigc/_internal/policy_loader.py` - Pre-compile guard effects

**Architectural risks:**
- Compiled guard effects must produce identical results to current deep-copy approach

**Determinism considerations:**
- Must produce identical effective policies (verified by golden replays)

**Audit implications:** No change to audit artifacts

---

### WS-11: Backward-Compatible Shims

**Scope:** Deprecation shims for `enforce_invocation()`, `set_audit_sink()`,
`get_audit_sink()`, bare-string preconditions.

**Affected modules:**
- `aigc/__init__.py` - Add deprecation warnings
- `aigc/_internal/enforcement.py` - Shim implementation

**Architectural risks:**
- Shim must delegate correctly to default AIGC instance
- Deprecation warnings must not break existing test suites

**Determinism considerations:** Shims produce identical results to direct calls

**Audit implications:** None

---

### WS-12: Documentation Parity

**Scope:** Update all documentation to reflect implementation changes.

**Affected documents:**
- `CLAUDE.md` - Module layout, pipeline contract, current state
- `README.md` - Test count, enforced controls, public API
- `PROJECT.md` - Architecture overview, project structure, feature list
- `docs/AIGC_FRAMEWORK.md` - Enforcement pipeline description
- `docs/architecture/AIGC_HIGH_LEVEL_DESIGN.md` - Pipeline diagram, gate ordering
- `policies/policy_dsl_spec.md` - Precondition syntax updates
- `CHANGELOG.md` - Version history

**Architectural risks:** None

**Determinism considerations:** N/A

**Audit implications:** Documentation must accurately reflect audit artifact structure

---

## 3. Module-Level Implementation Tasks

### aigc/_internal/enforcement.py

**WS-1 changes:**
- Add `AIGC` class with `__init__(sink, cache_size, cache_ttl, enforcement_mode,
  strict_mode, redaction_patterns, on_sink_failure)` parameters
- Add `AIGC.enforce(invocation) -> dict` method
- Add `AIGC.enforce_async(invocation) -> dict` method
- Move `_run_pipeline()` to accept AIGC config context
- Add `_default_instance` module-level variable for backward compat
- Add deprecation shim for `enforce_invocation()` (delegates to default instance)

**WS-6 changes:**
- Add JSON serializability check to `_validate_invocation()`:
  ```python
  def _check_json_serializable(value, path=""):
      try:
          json.dumps(value)
      except (TypeError, ValueError) as e:
          raise InvocationValidationError(
              f"Field '{path}' is not JSON-serializable: {e}",
              details={"field": path},
          )
  ```
- Call for `input`, `output`, and `context` fields before pipeline entry

**New functions:**
- `AIGC.__init__()` - Instance configuration
- `AIGC.enforce()` - Instance-level sync enforcement
- `AIGC.enforce_async()` - Instance-level async enforcement
- `_check_json_serializable()` - Serializability validation

**Test updates:**
- `test_enforcement_pipeline.py` - Add AIGC instance tests
- New `test_aigc_instance.py` - Thread safety, config validation
- `test_invocation_validation.py` - Serializability rejection tests

**Schema updates:** None

**Documentation updates:** CLAUDE.md (architecture section), PROJECT.md (architecture overview)

---

### aigc/_internal/validator.py

**WS-2 changes:**
- Add `validate_typed_preconditions()` function:
  - Accept `required: {key: {type: string, pattern: "..."}}` format
  - Generate per-key JSON Schema and validate each context value
  - Reject `{"key": True}` for typed preconditions
- Add backward-compat shim for bare-string `required: [key]` format:
  - Detect list-of-strings vs dict format
  - Emit `DeprecationWarning` for bare-string format
  - Convert bare strings to `{key: {type: "any"}}` internally

**New functions:**
- `validate_typed_preconditions(context, precondition_spec)` - Typed validation
- `_precondition_shim(required)` - Convert bare strings to typed format

**Refactors:**
- `validate_preconditions()` dispatches to typed or legacy path based on format

**Test updates:**
- `test_validation.py` - Add typed precondition tests
- New golden replay fixtures for typed preconditions
- Backward-compat tests for bare-string format

**Schema updates:** `schemas/policy_dsl.schema.json` - Accept both formats

**Documentation updates:** `policies/policy_dsl_spec.md` - New precondition syntax

---

### aigc/_internal/audit.py

**WS-3 changes:**
- Add `sanitize_failure_message(message, patterns)` function:
  - Default patterns: API key (`sk-...`, `key-...`), Bearer tokens, emails, SSNs
  - Replace matches with `[REDACTED:<pattern_name>]`
  - Return `(sanitized_message, redacted_fields_list)`
- Modify `generate_audit_artifact()` to:
  - Apply sanitization to `failures[].message`
  - Add `redacted_fields` to artifact metadata

**WS-7 changes:**
- Add bounds enforcement:
  - `failures` array: `maxItems: 1000`
  - `metadata` object: `maxProperties: 100`
  - `context` object: `maxProperties: 100`
  - Truncate with warning if exceeded

**New functions:**
- `sanitize_failure_message(message, patterns)` - Regex-based redaction
- `_default_redaction_patterns()` - Built-in patterns
- `_enforce_artifact_bounds(artifact)` - Size constraint enforcement

**Test updates:**
- `test_audit_artifact_contract.py` - Sanitization and bounds tests
- New `test_failure_sanitization.py` - Per-pattern tests

**Schema updates:** `schemas/audit_artifact.schema.json` - Add `redacted_fields`,
`maxItems`, `maxProperties`

**Documentation updates:** Security docs, audit artifact contract in CLAUDE.md

---

### aigc/_internal/sinks.py

**WS-1 + WS-5 changes:**
- Add `SinkRegistry` class (instance-scoped):
  - `__init__(sink, on_failure)` - Configure sink and failure mode
  - `emit(artifact)` - Emit with failure mode handling
- Add `AuditSinkError` to error taxonomy
- Add failure mode enum: `raise`, `queue`, `log`
- Deprecate module-level `_registered_sink` and `set_audit_sink()`
- Add deprecation shim for `set_audit_sink()` and `get_audit_sink()`

**New classes:**
- `SinkRegistry` - Instance-scoped sink management
- `SinkFailureMode` - Enum for failure behavior

**New errors:**
- `AuditSinkError` in `aigc/_internal/errors.py`

**Test updates:**
- `test_audit_sinks.py` - Failure mode tests, thread safety tests
- New tests for `AuditSinkError` propagation

**Schema updates:** None

**Documentation updates:** Configuration docs, error taxonomy in CLAUDE.md

---

### aigc/_internal/decorators.py

**WS-8 changes:**
- Replace positional argument extraction with `inspect.signature()` binding:
  ```python
  sig = inspect.signature(func)
  bound = sig.bind(*args, **kwargs)
  bound.apply_defaults()
  input_data = bound.arguments.get("input_data", bound.arguments.get("prompt", {}))
  ```
- Raise `TypeError` if required parameters missing
- Support both positional and keyword argument passing

**Test updates:**
- `test_decorators.py` - Reordered params, keyword args, missing params

**Schema updates:** None

**Documentation updates:** Decorator documentation

---

### aigc/_internal/guards.py

**WS-10 changes:**
- Replace per-guard `copy.deepcopy()` with single-copy-then-apply pattern:
  ```python
  effective = copy.deepcopy(policy)  # Single copy
  for guard in matching_guards:
      _apply_guard_effect(effective, guard["then"])  # In-place merge
  ```
- Pre-compute guard match sets at load time where possible

**WS-9 changes:**
- Add `INFO` logging for skipped optional conditions
- Improve error messages for missing/misspelled conditions

**Test updates:**
- `test_guards.py` - Verify identical results with optimized path
- Performance test for policies with many guards

**Schema updates:** None

**Documentation updates:** None

---

### aigc/_internal/conditions.py

**WS-9 changes:**
- Add `logging.info()` calls for skipped optional conditions
- Include available conditions in error messages for misspelled conditions

**Test updates:**
- `test_conditions.py` - Log output assertions

**Schema updates:** None

**Documentation updates:** None

---

### aigc/_internal/utils.py

No changes required for v0.2.0 workstreams.

---

### aigc/_internal/tools.py

No changes required for v0.2.0 workstreams (D-04 already fixed).

---

### aigc/_internal/errors.py

**WS-5 changes:**
- Add `AuditSinkError(AIGCError)` class

**Test updates:**
- `test_errors.py` - New error class tests

**Schema updates:** None

**Documentation updates:** Error taxonomy in CLAUDE.md

---

### aigc/_internal/policy_loader.py

**WS-4 changes:**
- Add `PolicyCache` class:
  ```python
  class PolicyCache:
      def __init__(self, max_size=128, ttl=None):
          self._cache = {}
          self._max_size = max_size
          self._ttl = ttl
          self._lock = threading.Lock()

      def get_or_load(self, path):
          canonical = os.path.realpath(path)
          mtime = os.path.getmtime(canonical)
          key = (canonical, mtime)
          with self._lock:
              if key in self._cache:
                  return self._cache[key]
          policy = load_policy(path)
          with self._lock:
              if len(self._cache) >= self._max_size:
                  self._evict_oldest()
              self._cache[key] = policy
          return policy
  ```

**WS-2 changes:**
- Update schema validation to accept typed precondition format

**Test updates:**
- `test_policy_loader.py` - Cache hit/miss, mtime invalidation
- New `test_policy_cache.py` - Thread safety, eviction, TTL

**Schema updates:** `schemas/policy_dsl.schema.json`

**Documentation updates:** Configuration docs

---

## 4. Pipeline Redesign Plan

### Current Pipeline (v0.1.3 - Already Correct)

```
1. Guard evaluation          [AUTHORIZATION]  guards.py
2. Role validation           [AUTHORIZATION]  validator.py
3. Precondition validation   [AUTHORIZATION]  validator.py
4. Tool constraint validation [AUTHORIZATION] tools.py
5. Schema validation         [OUTPUT]         validator.py
6. Postcondition validation  [OUTPUT]         validator.py
7. Audit artifact generation [EVIDENCE]       audit.py
8. Sink emission             [PERSISTENCE]    sinks.py
```

This ordering is correct per ADR-D04. D-04 was already fixed in v0.1.3.

### v0.2.0 Pipeline Additions

```
0. Invocation shape validation     [ENTRY]          enforcement.py  (WS-6: NEW)
   - JSON serializability check
   - Required field validation (existing)
   - Type validation (existing)

1. Policy load (with cache)        [LOAD]           policy_loader.py (WS-4: ENHANCED)
   - LRU cache lookup by (path, mtime)
   - Cache miss: full YAML parse + schema validate
   - Cache hit: return compiled policy

2. Guard evaluation                [AUTHORIZATION]  guards.py        (WS-10: OPTIMIZED)
   - Single deep copy instead of per-guard copy
   - Identical behavior, improved performance

3. Role validation                 [AUTHORIZATION]  validator.py     (unchanged)

4. Precondition validation         [AUTHORIZATION]  validator.py     (WS-2: ENHANCED)
   - Typed preconditions: validate value types/formats
   - Backward-compat: bare-string syntax still works (deprecated)

5. Tool constraint validation      [AUTHORIZATION]  tools.py         (unchanged)

6. Schema validation               [OUTPUT]         validator.py     (unchanged)

7. Postcondition validation        [OUTPUT]         validator.py     (unchanged)

8. Audit artifact generation       [EVIDENCE]       audit.py         (WS-3, WS-7: ENHANCED)
   - Exception message sanitization
   - Schema bounds enforcement
   - redacted_fields metadata

9. Sink emission                   [PERSISTENCE]    sinks.py         (WS-5: ENHANCED)
   - Instance-scoped sink
   - Configurable failure mode (raise/queue/log)
```

### Ordering Rationale

1. **Guard evaluation first** - Guards expand the effective policy. All subsequent
   gates operate on the expanded policy. Must run before any validation.

2. **Role validation second** - If the role is unauthorized, no further validation
   is meaningful. Fail fast on identity.

3. **Precondition validation third** - Context requirements must be met before
   processing output. Authorization-relevant (proves required context exists).

4. **Tool constraint validation fourth** - Authorization gate. A banned tool must
   be caught before any output processing. This is the D-04 fix rationale:
   prohibited tools should never reach schema validation.

5. **Schema validation fifth** - Output processing gate. Only runs after all
   authorization gates pass. Validates structural correctness of model output.

6. **Postcondition validation sixth** - Semantic checks after schema validation.
   Depends on schema validation result (`output_schema_valid`).

7. **Audit artifact generation seventh** - Evidence gate. Produces the governance
   record. Must run after all gates to capture complete results.

8. **Sink emission eighth** - Persistence. Side effect, not governance logic.
   Failure mode determines whether persistence failure blocks the caller.

---

## 5. Determinism Safeguards

### Canonical Serialization Stability

- `canonical_json_bytes()` in `aigc/_internal/utils.py` enforces:
  - Sorted keys (deterministic key ordering)
  - Compact separators (no whitespace)
  - UTF-8 encoding
  - NaN/Infinity rejection
- **Safeguard:** Golden replay tests verify checksum stability across runs.
  Any change to serialization must update all golden replays.

### Deterministic Failure Ordering

- Failures are accumulated in pipeline execution order (gate-by-gate)
- Within a gate, failures are sorted by field name (alphabetical)
- **Safeguard:** `test_checksum_determinism.py` runs 100 iterations and
  verifies identical checksums.

### Guard Evaluation Stability

- Guards evaluated in declaration order (array index order in YAML)
- Conditions resolved deterministically from context
- Guard effects merged in declaration order (last-write-wins for scalars)
- **Safeguard:** Golden replay tests for guard scenarios verify exact
  `guards_evaluated` and `conditions_resolved` metadata.

### Deterministic Audit Checksums

- Checksums computed from `canonical_json_bytes()` of input and output
- Timestamp is the only non-deterministic field (frozen in tests)
- All other fields are deterministic given identical inputs
- **Safeguard:** 100-run determinism test in `test_checksum_determinism.py`

### Golden Replay Reproducibility

- Golden replays define the expected governance behavior
- Any change that modifies enforcement results must:
  1. Update golden replay fixtures
  2. Update expected stable fields
  3. Add ADR documenting the change
- **Safeguard:** Golden replay test suite runs in CI. Failures block merge.

### New Safeguards for v0.2.0

- **Typed precondition determinism:** Failure messages sorted by key name.
  Same typed precondition spec + same context = same failures.
- **Sanitization determinism:** Redaction patterns applied in fixed order.
  Same message + same patterns = same sanitized output.
- **Cache determinism:** Cache hit returns same policy dict. Enforcement
  results are identical for cache hit vs cache miss paths.

---

## 6. Test Expansion Plan

### New Test Files

| File | Purpose | Workstream |
|------|---------|------------|
| `test_aigc_instance.py` | AIGC instance creation, config validation, thread safety | WS-1 |
| `test_typed_preconditions.py` | Typed precondition validation, backward compat | WS-2 |
| `test_failure_sanitization.py` | Redaction pattern tests, custom patterns | WS-3 |
| `test_policy_cache.py` | Cache hit/miss, mtime invalidation, eviction, TTL | WS-4 |
| `test_sink_failure_modes.py` | raise/queue/log modes, AuditSinkError | WS-5 |
| `test_json_serializability.py` | Non-serializable type rejection at entry | WS-6 |

### Existing Test Updates

| File | Changes Required |
|------|-----------------|
| `test_enforcement_pipeline.py` | Add AIGC instance tests alongside existing function tests |
| `test_audit_artifact_contract.py` | Add sanitization field assertions, bounds tests |
| `test_decorators.py` | Add reordered-param and keyword-arg tests |
| `test_conditions.py` | Add log-output assertions for skipped conditions |
| `test_guards.py` | Verify identical results with optimized guard merging |
| `test_public_api.py` | Add AIGC class export assertion |
| `test_errors.py` | Add AuditSinkError test |
| `test_checksum_determinism.py` | Extend to cover sanitized artifacts |

### Pipeline Ordering Tests

- Existing `test_pre_action_boundary.py` verifies D-04 ordering
- Add test: typed precondition failure fires before tool validation
- Add test: JSON serializability failure fires before pipeline entry
- Add test: `gates_evaluated` never contains gates after the failing gate

### Deterministic Artifact Tests

- Existing `test_checksum_determinism.py` with 100-run verification
- Add: sanitized artifact determinism (same patterns = same output)
- Add: typed precondition failure determinism
- Add: cached vs uncached enforcement produces identical artifacts

### Replay Integrity Tests

- Update golden replays for audit schema v1.2 (additive `redacted_fields`)
- Add golden replay for typed precondition scenarios:
  - `golden_invocation_typed_precondition_success.json`
  - `golden_invocation_typed_precondition_failure.json`
  - `golden_policy_typed_preconditions.yaml`
- Add golden replay for sanitized failure messages

### Governance Invariant Tests

- Test: AIGC instance with `strict_mode=True` rejects bare-string preconditions
- Test: AIGC instance with `on_sink_failure="raise"` propagates AuditSinkError
- Test: No module-level mutable state accessed during AIGC.enforce()
- Test: Concurrent enforcement (10 threads) produces correct results

### Golden Replay Updates Required

When implementing workstreams, the following golden replays need updates:

1. **WS-2 (typed preconditions):** New policy fixtures with typed preconditions.
   Existing bare-string fixtures remain valid (backward compat).
2. **WS-3 (sanitization):** All existing golden expected artifacts gain
   `redacted_fields: []` (no redaction in test fixtures). New fixture with
   sensitive data shows redaction behavior.
3. **All workstreams:** Verify all 190+ existing tests still pass after each change.

---

## 7. CI Governance Gates

### Existing CI Gates (sdk_ci.yml)

1. **Test suite** - `pytest --cov=aigc --cov-report=term-missing --cov-fail-under=90`
2. **Lint** - `flake8 aigc`
3. **Markdown lint** - `npx markdownlint-cli2 "**/*.md"`
4. **Schema validation** - Validate policy YAML against JSON Schema
5. **Policy validation** - Validate example policies

### New CI Gates for v0.2.0

| Gate | Purpose | Command |
|------|---------|---------|
| `ci:pre-action-boundary` | Verify authorization gates before output gates | `pytest tests/test_pre_action_boundary.py -v` (already exists) |
| `ci:determinism` | Verify checksum stability across runs | `pytest tests/test_checksum_determinism.py -v` |
| `ci:golden-replay` | Verify all golden replays pass | `pytest tests/test_golden_replay_*.py -v` |
| `ci:schema-valid` | Verify all emitted artifacts pass schema validation | Integrated in test suite |
| `ci:backward-compat` | Verify deprecated APIs still work | `pytest tests/test_backward_compat.py -v` |

### Coverage Thresholds

- **Minimum:** 90% line coverage (existing gate)
- **Target:** Maintain 100% coverage on `aigc/_internal/` modules
- **New modules** must have 100% coverage from introduction

### Artifact Reproducibility

- Golden replay tests verify exact checksum match
- Determinism tests run 100 iterations
- CI fails if any golden replay fixture changes without ADR

---

## 8. Documentation Parity Rules

Every implementation change must update the following documents in the same commit:

| Document | What to Update |
|----------|----------------|
| `CLAUDE.md` | Module layout, pipeline contract, current state, error taxonomy |
| `README.md` | Test count, enforced controls, public API, quickstart |
| `PROJECT.md` | Architecture overview, project structure, feature list, phase notes |
| `docs/AIGC_FRAMEWORK.md` | Enforcement pipeline description |
| `docs/architecture/AIGC_HIGH_LEVEL_DESIGN.md` | Pipeline diagram, gate ordering rationale |
| `policies/policy_dsl_spec.md` | Policy syntax (when DSL changes) |
| `schemas/audit_artifact.schema.json` | Artifact contract (when schema changes) |
| `schemas/policy_dsl.schema.json` | Policy schema (when DSL changes) |
| `CHANGELOG.md` | Version history entry |

### Parity Enforcement Rule

A PR that changes enforcement behavior, pipeline ordering, gate names,
test counts, module structure, or audit artifact shape is **incomplete**
unless all affected documents are updated. This is a hard gate.

---

## 9. Implementation Execution Order

The workstreams have the following dependency graph:

```
WS-1 (AIGC instance)
  |
  +-- WS-4 (Policy caching)     [depends on WS-1: cache lives on instance]
  +-- WS-5 (Sink failure modes)  [depends on WS-1: sink is instance-scoped]
  +-- WS-11 (Backward compat)    [depends on WS-1: shims delegate to instance]

WS-2 (Typed preconditions)       [independent]
WS-3 (Sanitization)              [independent]
WS-6 (JSON serializability)      [independent]
WS-7 (Audit schema bounds)       [independent]
WS-8 (Decorator fix)             [independent]
WS-9 (Condition improvements)    [independent]
WS-10 (Guard optimization)       [independent]
WS-12 (Documentation)            [runs with every WS]
```

### Recommended Execution Order

1. **WS-6** (JSON serializability) - Small, independent, no dependencies
2. **WS-7** (Audit schema bounds) - Small, independent
3. **WS-8** (Decorator fix) - Small, independent
4. **WS-9** (Condition improvements) - Small, independent
5. **WS-10** (Guard optimization) - Small, independent
6. **WS-3** (Exception sanitization) - Medium, independent, schema bump
7. **WS-2** (Typed preconditions) - Medium, independent, DSL change
8. **WS-1** (AIGC instance) - Large, foundation for WS-4/5/11
9. **WS-5** (Sink failure modes) - Small, depends on WS-1
10. **WS-4** (Policy caching) - Medium, depends on WS-1
11. **WS-11** (Backward compat shims) - Small, depends on WS-1
12. **WS-12** (Documentation parity) - Runs continuously with each WS

### Governance Rules Per Workstream

Each workstream must satisfy:

1. All existing 190+ tests pass
2. New tests added for new functionality
3. Coverage >= 90% maintained
4. Golden replays pass (updated if behavior changes)
5. Documentation updated in same commit
6. Determinism preserved (verified by determinism tests)
7. No bypass paths introduced
8. Fail-closed behavior maintained
9. ADR created if changing pipeline ordering, error taxonomy, or audit schema

---

## 10. Scope Boundaries

### In Scope for v0.2.0

- D-01, D-02, D-03, D-05, D-07, D-11, D-12, D-13, D-14, D-15
- AIGC instance-scoped configuration
- Backward-compatible deprecation shims
- Audit schema v1.2 (additive)
- D-07: AST-based guard expression language (`and`, `or`, `not`, comparisons, `in`)
- Policy CLI (`aigc policy lint`, `aigc policy validate`)
- Strict mode for minimum viable policies
- InvocationBuilder pattern
- Internal import deprecation warnings

### Out of Scope for v0.2.0 (Deferred to v0.3.0+)

- D-06: Policy composition restriction semantics
- D-08: Risk scoring and graduated enforcement
- D-09: Workflow governance (GovernanceSession)
- D-10: Async timeout configuration
- Audit artifact signing (HMAC)
- Hash-chain linking (ADR-0008)
- Custom EnforcementGate plugin interface
- ObservabilityProvider interface
- PolicyLoader plugin interface

### D-04 Status

D-04 (pipeline ordering) is **already implemented**. Tool constraints run before
schema validation. Sentinel tests enforce this. No further work required.
