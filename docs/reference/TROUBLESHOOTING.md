# AIGC Workflow Troubleshooting Guide

This guide covers `aigc workflow doctor`, `aigc workflow lint`, the frozen
first-user reason codes, and the regulated failure-and-fix walkthrough.

## `aigc workflow doctor`

Use doctor when you want runtime or evidence-aware diagnosis:

```bash
aigc workflow doctor governance/
aigc workflow doctor workflow_artifact.json
aigc workflow doctor audit.json --kind audit_artifact --json
```

Doctor exits `0` when no error-severity findings are present and exits `1` when
at least one error-severity finding is present.

## `aigc workflow lint`

Use lint for static checks before you run a workflow:

```bash
aigc workflow lint policy.yaml
aigc workflow lint governance/
```

Lint exits `0` when no error-severity findings are present and exits `1` when
at least one error-severity finding is present.

In the beta, lint covers policy schema validity, starter integrity,
public-import safety, impossible workflow budgets, invalid transition
references, and unsupported binding references.

## Frozen First-User Reason Codes

### `WORKFLOW_INVALID_TRANSITION`

Symptom: a public session method raises `SessionStateError`, or a failed
workflow artifact normalizes to `WORKFLOW_INVALID_TRANSITION`.

Fix: keep the lifecycle ordered:
`open_session()` -> `enforce_step_pre_call()` / `enforce_step_post_call()` ->
`complete()` or `cancel()`. If the session paused, call `resume()` before
adding more steps.

### `WORKFLOW_APPROVAL_REQUIRED`

Symptom: `WorkflowApprovalRequiredError`.

Fix: implement a real approval path, then call `session.resume()` to continue
or `session.cancel()` to stop the workflow.

### `WORKFLOW_SOURCE_REQUIRED`

Symptom: a regulated workflow raises `CustomGateViolationError` because
`context.provenance.source_ids` is missing.

Fix: provide `context.provenance.source_ids` on every governed invocation when
using `ProvenanceGate(require_source_ids=True)`.

### `WORKFLOW_TOOL_BUDGET_EXCEEDED`

Symptom: `WorkflowToolBudgetExceededError` or an audit artifact diagnosed as a
tool-budget failure.

Fix: reduce `tool_calls` or increase the allowed tool budget in policy.

### `WORKFLOW_UNSUPPORTED_BINDING`

Symptom: doctor or lint flags unsupported workflow binding references.

Fix: remove unsupported protocol references such as `grpc`, `websocket`, or
`soap`. The beta path supports local workflow use first; optional adapters come
later.

### `WORKFLOW_SESSION_TOKEN_INVALID`

Symptom: `InvocationValidationError` when completing a `SessionPreCallResult`.

Fix: use the exact single-use token returned by `enforce_step_pre_call()`,
complete it through the owning `GovernanceSession`, and mint a new token for a
new attempt.

### `WORKFLOW_STARTER_INTEGRITY_ERROR`

Symptom: lint or doctor reports missing/empty starter files, syntax errors, or
public-boundary violations.

Fix: regenerate the starter with `aigc workflow init --profile <profile>` or
repair the specific file called out by the finding.

## Regulated Failure-And-Fix Flow

This is the PR-07 stop-ship walkthrough. It uses the real regulated starter,
breaks that generated `workflow_example.py`, diagnoses that same directory, then
fixes and reruns it.

### 1. Generate the starter

```bash
aigc workflow init --profile regulated-high-assurance --output-dir regulated-demo
cd regulated-demo
```

### 2. Break the generated starter

Remove the two `source_ids` lines from `workflow_example.py` so the generated
starter still uses `ProvenanceGate(require_source_ids=True)` but no longer
supplies source provenance for either step.

### 3. Run the broken starter

```bash
python workflow_example.py
```

Expected result: the run fails with `CustomGateViolationError` because
`source_ids` are missing.

### 4. Diagnose that same directory

```bash
aigc workflow doctor regulated-demo/ --json
```

Expected finding set includes `WORKFLOW_SOURCE_REQUIRED`.

### 5. Restore the same file

Put the removed `source_ids` lines back into `workflow_example.py`.

### 6. Rerun the same starter

```bash
python workflow_example.py
```

Expected output:

```text
Status:  COMPLETED
Steps:   2
```
