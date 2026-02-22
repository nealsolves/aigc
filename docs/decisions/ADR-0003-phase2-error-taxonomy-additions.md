# ADR-0003: Phase 2 Error Taxonomy Additions

Date: 2026-02-16
Status: Accepted
Owners: AIGC SDK Team

---

## Context

Phase 2 introduced three new runtime enforcement modules — guard evaluation
(`src/guards.py`), named condition resolution (`src/conditions.py`), and tool
constraint enforcement (`src/tools.py`). Each module can fail in ways that are
semantically distinct from existing error categories.

The existing taxonomy (`PreconditionError`, `SchemaValidationError`,
`GovernanceViolationError`) does not provide machine-readable differentiation
between a precondition failure, a guard evaluation failure, a condition
resolution failure, and a tool constraint violation. Collapsing these into
existing types would make audit artifacts less precise and complicate
downstream triage.

CLAUDE.md §8 requires typed exceptions and prohibits collapsing distinct
failures into generic errors.

---

## Decision

Add three new typed exception classes to `src/errors.py`:

- `ConditionResolutionError` — raised when a named condition cannot be
  resolved (missing context key with no default, or non-boolean value).
  Code: `CONDITION_RESOLUTION_ERROR`.
- `GuardEvaluationError` — raised when a guard expression cannot be
  evaluated (unknown condition reference, malformed expression).
  Code: `GUARD_EVALUATION_ERROR`.
- `ToolConstraintViolationError` — raised when a tool invocation violates
  the policy allowlist or `max_calls` limit.
  Code: `TOOL_CONSTRAINT_VIOLATION`.

Both `ConditionResolutionError` and `GuardEvaluationError` extend `AIGCError`
directly. `ToolConstraintViolationError` extends `GovernanceViolationError`
because a tool constraint violation is an explicit policy invariant breach,
not a resolution ambiguity.

---

## Options Considered

### Option A: Extend existing types

Reuse `PreconditionError` for condition failures and `GovernanceViolationError`
for tool/guard failures, differentiated only by `code`.

Pros:
- No new class surface area.

Cons:
- Callers cannot `except ConditionResolutionError` — must inspect `.code`.
- Audit triage requires string matching, not type matching.
- Violates the typed taxonomy principle in CLAUDE.md §8.

### Option B: Three new typed exceptions (chosen)

Pros:
- Each failure domain is independently catchable by type.
- Machine-readable codes are stable and independently evolvable.
- Audit artifacts record distinct `failure_gate` values per error type.
- Consistent with existing pattern (`PreconditionError`, `SchemaValidationError`).

Cons:
- Increases class count by three.

### Option C: Single `Phase2EnforcementError` with sub-codes

Pros:
- Fewer classes.

Cons:
- Conflates three semantically distinct domains.
- Harder to handle selectively in callers or retry logic.

---

## Consequences

- Callers and tests can catch errors by type without inspecting `.code`.
- Retry logic in `src/retry.py` can distinguish retryable
  (`SchemaValidationError`) from non-retryable governance errors
  (`ToolConstraintViolationError`, `GuardEvaluationError`) by type.
- Adding a new Phase 3 error type follows the same pattern: subclass
  `AIGCError` or `GovernanceViolationError`, assign a stable code, add tests.

---

## Contract Impact

- Enforcement pipeline impact: three new raise sites in `src/guards.py`,
  `src/conditions.py`, and `src/tools.py`.
- Policy DSL impact: none — error taxonomy is internal.
- Schema impact: none.
- Audit artifact impact: `failure_gate` field in FAIL artifacts records the
  new error codes (`CONDITION_RESOLUTION_ERROR`, `GUARD_EVALUATION_ERROR`,
  `TOOL_CONSTRAINT_VIOLATION`).
- Golden replays impact: new FAIL golden replays added for each error type.
- Structural impact: `src/errors.py` — three new classes appended.
- Backward compatibility: existing error types unchanged; new types are
  additive.

---

## Validation

- `tests/test_conditions.py` asserts `ConditionResolutionError` with code
  `CONDITION_RESOLUTION_ERROR` on missing required condition and non-boolean
  default.
- `tests/test_guards.py` asserts `GuardEvaluationError` with code
  `GUARD_EVALUATION_ERROR` on unknown condition reference.
- `tests/test_tools.py` asserts `ToolConstraintViolationError` with code
  `TOOL_CONSTRAINT_VIOLATION` on allowlist and `max_calls` violations.
- Golden replay FAIL fixtures for each new error type in `tests/golden_replays/`.
