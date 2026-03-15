# ADR-0007: Pre-Action Enforcement Boundary Proof

Date: 2026-03-05
Status: Accepted
Owners: Neal

---

## Context

The enforcement pipeline validates tool constraints before schema validation
(ADR-D04 in the Architecture Redesign Roadmap). However, the pipeline ordering
alone does not *prove* to an auditor that authorization-relevant gates ran
before output processing gates. The audit artifact records `failure_gate` and
`failure_reason`, but these only indicate *what* failed — not *what ran before
the failure*.

In agentic systems, tool calls are irreversible side effects. The question
"did governance verify tool authorization before the action could proceed?"
must be answerable from the audit artifact alone, without trusting the
implementation to have maintained the correct ordering. This is the difference
between "we enforced the contract" and "we enforced and can prove it happened
pre-action."

### Constraints

- The audit artifact must be self-contained evidence of gate execution order
- CI must prevent pipeline ordering regressions (not just code review)
- The proof must survive across refactors of `_run_pipeline()`
- Golden replays must assert ordering, not just pass/fail outcomes

---

## Decision

Introduce three mechanisms:

### 1. `metadata.gates_evaluated` field

The enforcement pipeline records an ordered list of gate names as each gate
completes (pass or fail). This list is included in the audit artifact under
`metadata.gates_evaluated`.

Example for a PASS artifact:

```json
{
  "metadata": {
    "gates_evaluated": [
      "guard_evaluation",
      "role_validation",
      "precondition_validation",
      "tool_validation",
      "schema_validation",
      "postcondition_validation"
    ]
  }
}
```

Example for a FAIL artifact (tool constraint violation):

```json
{
  "metadata": {
    "gates_evaluated": [
      "guard_evaluation",
      "role_validation",
      "precondition_validation",
      "tool_validation"
    ],
    "failure_gate": "tool_validation"
  }
}
```

The list is append-only during pipeline execution. Gates that were not reached
(due to an earlier failure) do not appear.

### 2. CI gate: `ci:pre-action-boundary`

A CI regression test that asserts: for any invocation where both tool
constraints and schema validation would fail, the audit artifact's
`failure_gate` is `tool_validation` and `schema_validation` does not
appear in `metadata.gates_evaluated`.

This test uses golden replay fixtures with invocations designed to fail
at both gates. The assertion is on the *ordering evidence*, not just the
outcome.

### 3. Development rule

Any PR that modifies `_run_pipeline()` or adds new gates to the enforcement
pipeline MUST:

- Update `ci:pre-action-boundary` golden replay fixtures
- NOT reorder authorization gates (role, preconditions, tools) after output
  processing gates (schema, postconditions)
- Include the gate name in `metadata.gates_evaluated` at the correct position

This ordering is enforced by CI, not by code review alone.

---

## Options Considered

### Option A: `metadata.gates_evaluated` ordered list (chosen)

Pros:

- Self-contained proof in every artifact
- Machine-readable for compliance tooling
- Survives refactors (golden replays assert ordering)
- CI-enforceable

Cons:

- Adds a field to every artifact (minor size increase)
- Must be maintained as new gates are added

### Option B: Rely on `failure_gate` alone

Pros:

- No new fields
- Simpler implementation

Cons:

- `failure_gate` only records *what* failed, not *what ran before it*
- Cannot prove schema validation didn't run before tool validation
- Not auditable evidence of ordering

### Option C: Separate ordering assertion in metadata

Add `metadata.authorization_verified_before_output: true` boolean.

Pros:

- Simple, clear signal

Cons:

- A boolean claim, not a proof — the system asserts its own correctness
- No auditor can independently verify the claim from the artifact
- Gate ordering changes wouldn't be reflected

---

## Consequences

- What becomes easier:
  - Compliance auditors can verify pre-action enforcement from artifacts alone
  - Pipeline ordering regressions are caught by CI, not discovered in production
  - Golden replays now test *ordering semantics*, not just pass/fail outcomes

- What becomes harder:
  - Every new gate must be added to `gates_evaluated` at the correct position
  - Artifact size increases slightly per enforcement

- Risks introduced:
  - `gates_evaluated` could become stale if a gate is added without updating
    the recording logic
  - Mitigation: CI golden replays fail if expected gates are missing

---

## Contract Impact

- Enforcement pipeline impact: Each gate appends its name to a list before
  executing. List is passed to `generate_audit_artifact()`.
- Policy DSL impact: None
- Schema impact: `metadata.gates_evaluated` is a new array field (additive,
  no schema version bump required since `metadata` is `type: object` with
  no constraints)
- Audit artifact impact: New `metadata.gates_evaluated` field in every artifact
- Golden replays impact: New golden fixtures asserting ordering. Existing
  golden replays updated to include `gates_evaluated` in expected metadata.
- Structural impact: None
- Backward compatibility: Additive field. Existing consumers ignore unknown
  metadata keys.

---

## Validation

- `ci:pre-action-boundary` golden replay: invocation fails both tool and
  schema gates. Assert `failure_gate == "tool_validation"` and
  `"schema_validation" not in metadata["gates_evaluated"]`.
- PASS artifact golden replay: assert `gates_evaluated` contains all 6
  core gates in correct order.
- 100-run determinism test: `gates_evaluated` is identical across all runs
  for the same invocation.
