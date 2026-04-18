# AIGC Workflow Troubleshooting Guide

This guide covers the diagnostic tools `aigc workflow doctor` and
`aigc workflow lint`, plus a reference for every first-user reason code and a
worked failure-and-fix flow.

## Using `aigc workflow doctor`

`aigc workflow doctor` inspects a generated starter directory and reports
advisories about policy correctness, manifest integrity, and common
misconfiguration patterns.

```bash
aigc workflow doctor governance/
```

The command exits 1 if any errors are found; 0 if only advisories (no errors).
Each advisory carries a reason code and a `next_action` that tells you exactly
what to fix. Run doctor after generating a starter, after editing `policy.yaml`,
or any time governance raises an unexpected error.

## Using `aigc workflow lint`

`aigc workflow lint` validates a policy file or an entire starter directory
against the policy DSL schema and known structural rules.

```bash
aigc workflow lint policy.yaml
aigc workflow lint governance/
```

Lint exits 0 if only advisories are found (the policy is schema-valid). It
exits 1 if hard errors are present (the policy would fail to load at runtime).
Run lint before committing policy changes.

## Reason codes

Each governance error carries a machine-readable reason code. The sections
below give the symptom, meaning, and fix for every first-user reason code.

### WORKFLOW_INVALID_TRANSITION

**Symptom:** A `SessionStateError` is raised when calling `enforce_step_pre_call`
or another session method.

**What it means:** The session is not in a state that allows the operation you
requested. For example, calling `enforce_step_pre_call` on a `PAUSED` session
or calling `complete()` on a session that is already `COMPLETED`.

**Fix:** Ensure your workflow follows the correct lifecycle:
`open_session()` -> `enforce_step_pre_call()` / `enforce_step_post_call()` ->
`complete()` or `cancel()`. Call `resume()` before adding steps when the
session is PAUSED.

---

### WORKFLOW_APPROVAL_REQUIRED

**Symptom:** A `WorkflowApprovalError` is raised when the session reaches an
approval checkpoint step.

**What it means:** The policy requires human approval before the workflow
continues. The session has paused and is waiting for an explicit approval
signal before the next step can proceed.

**Fix:** Implement a real approval callback to replace the simulated one in
`_request_human_approval()`. When approval is denied, call `session.cancel()`
explicitly. When approved, call `session.resume()` before continuing with
additional steps.

---

### WORKFLOW_SOURCE_REQUIRED

**Symptom:** A `CustomGateViolationError` is raised with code
`WORKFLOW_SOURCE_REQUIRED`.

**What it means:** The policy uses `ProvenanceGate(require_source_ids=True)`,
which requires every invocation context to carry
`context.provenance.source_ids`. The current invocation context is missing this
field.

**Fix:** Provide `context.provenance.source_ids` in every invocation context
when using `ProvenanceGate(require_source_ids=True)`. See
`docs/INTEGRATION_GUIDE.md` for provenance usage.

---

### WORKFLOW_TOOL_BUDGET_EXCEEDED

**Symptom:** A `ToolConstraintViolationError` is raised with code
`WORKFLOW_TOOL_BUDGET_EXCEEDED`.

**What it means:** The invocation's `tool_calls` list contains more calls to a
tool than the policy allows via `tools.allowed_tools[].max_calls`.

**Fix:** Reduce the number of `tool_calls` in your invocation to stay within
the `max_calls` limit defined in `policy.yaml` (`tools.allowed_tools`). See
`policies/policy_dsl_spec.md` for tool constraint syntax.

---

### WORKFLOW_UNSUPPORTED_BINDING

**Symptom:** A `WorkflowDiagnosticError` or policy load failure occurs with
code `WORKFLOW_UNSUPPORTED_BINDING`.

**What it means:** A condition or guard entry in the policy references a
protocol binding name that is not supported in v0.9.0. Only HTTP/REST adapter
bindings are supported. References to `grpc`, `websocket`, or `soap` bindings
will fail.

**Fix:** Remove or rename condition/guard entries that reference unsupported
protocol names (`grpc`, `websocket`, `soap`). Only HTTP/REST adapter bindings
are supported in v0.9.0.

---

### WORKFLOW_SESSION_TOKEN_INVALID

**Symptom:** A `SessionStateError` or `InvocationValidationError` is raised
when completing a `SessionPreCallResult`.

**What it means:** The session token provided to `enforce_step_post_call` is
invalid. Either it has already been used (tokens are single-use), it belongs to
a different session, or a well-formed token was not present in the required
precondition field.

**Fix:** Ensure callers provide a well-formed, non-replayed session token in
the required precondition field. Use `GovernanceSession` as a context manager
to manage token lifecycle automatically. Tokens are single-use; retry with a
fresh token if the session is still open.

---

### WORKFLOW_STARTER_INTEGRITY_ERROR

**Symptom:** A `WorkflowStarterIntegrityError` is raised when running a
generated starter, or `aigc workflow doctor` reports an integrity advisory.

**What it means:** The generated starter directory has been modified in a way
that breaks the expected file structure or checksums. The starter's internal
integrity check failed.

**Fix:** Re-run `aigc workflow init --profile <profile>` to regenerate the
starter, or fix the integrity issue described above. See the generated
`README.md` in the starter directory for usage.

---

### POLICY_LOAD_ERROR (shared)

**Symptom:** A `PolicyLoadError` exception is raised at invocation time, or
`aigc workflow lint` reports a load error.

**What it means:** The policy file has a YAML syntax error, a structural
problem, or a composition cycle (`extends` chain forms a loop).

**Fix:** Fix the policy file syntax or structure. See
`policies/policy_dsl_spec.md` for the full policy DSL reference.

---

### POLICY_SCHEMA_VALIDATION_ERROR (shared)

**Symptom:** A `PolicyValidationError` exception is raised, or `aigc workflow
lint` reports schema violations.

**What it means:** The policy file is valid YAML but does not conform to the
policy DSL JSON Schema. Required fields may be missing or field types may be
wrong.

**Fix:** Fix the schema violation in `policy.yaml`. Run `aigc policy lint
<file>` to list all violations. See `policies/policy_dsl_spec.md` for field
specifications.

---

### TOOL_CONSTRAINT_VIOLATION (shared)

**Symptom:** A `ToolConstraintViolationError` is raised at invocation time.

**What it means:** The invocation's `tool_calls` list includes a tool not in
the policy's `tools.allowed_tools` list, or the tool's call count exceeds
`max_calls`.

**Fix:** Fix the tool constraint issue in `policy.yaml`. See
`policies/policy_dsl_spec.md` for tool allowlist syntax.

---

## The failure-and-fix flow (regulated profile)

This walkthrough shows how to trigger a `WORKFLOW_SOURCE_REQUIRED` error and
fix it using `aigc workflow doctor`.

**Setup:** generate the regulated starter:

```bash
aigc workflow init --profile regulated-high-assurance
cd regulated-starter
```

**Step 1 — Remove `source_ids` from the invocation context**

Edit `workflow_example.py` and comment out or remove the `provenance` key from
the invocation context dict:

```python
# Before (correct):
context = {
    "user_id": "user-001",
    "provenance": {"source_ids": ["doc-42"]},
}

# After (broken — remove source_ids):
context = {
    "user_id": "user-001",
}
```

**Step 2 — Run the script and observe the error**

```bash
python workflow_example.py
```

Expected output includes a `CustomGateViolationError`:

```
CustomGateViolationError: WORKFLOW_SOURCE_REQUIRED — source_ids missing
  from context.provenance; ProvenanceGate requires it.
```

**Step 3 — Run `aigc workflow doctor` on the starter directory**

```bash
aigc workflow doctor regulated-starter/
```

**Step 4 — Read the advisory**

The doctor output includes an advisory with code `WORKFLOW_SOURCE_REQUIRED`:

```
ADVISORY  WORKFLOW_SOURCE_REQUIRED
  Provide context.provenance.source_ids in every invocation context when
  using ProvenanceGate(require_source_ids=True).
```

**Step 5 — Restore `source_ids` in the invocation context**

Edit `workflow_example.py` and restore the `provenance` key:

```python
context = {
    "user_id": "user-001",
    "provenance": {"source_ids": ["doc-42"]},
}
```

**Step 6 — Rerun and confirm success**

```bash
python workflow_example.py
```

Expected output:

```
Status:  COMPLETED
Steps:   2
Session: <uuid>
```
