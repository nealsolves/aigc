# Migrating from Invocation-Only to Workflow Governance

This guide shows the smallest safe diff to add workflow governance to existing
AIGC-governed code. The migration is **additive** — existing invocation-only code
continues to work without changes.

## When to migrate

Migrate when you want:
- **Correlated audit trail** across multiple model calls in one workflow
- **Lifecycle state** (`OPEN → COMPLETED/FAILED/CANCELED`) for multi-step processes
- **Approval checkpoints** or source-required enforcement at the session level

Single one-off calls are fine with invocation-only governance.

## The minimal diff

### Before (invocation-only)

```python
governance = aigc.AIGC()

pre = governance.enforce_pre_call(invocation)
output = call_model(...)
artifact = governance.enforce_post_call(pre, output)
```

### After (additive workflow adoption)

```python
governance = aigc.AIGC()

with governance.open_session(policy_file="policy.yaml") as session:  # + wrap
    pre = session.enforce_step_pre_call(invocation)                    # enforce_pre_call →
    output = call_model(...)                                            # unchanged
    session.enforce_step_post_call(pre, output)                        # enforce_post_call →
    session.complete()                                                  # + complete

workflow_artifact = session.workflow_artifact                           # + new artifact
```

The four changes are:
1. `with governance.open_session(...) as session:` — open a session context
2. `session.enforce_step_pre_call` instead of `governance.enforce_pre_call`
3. `session.enforce_step_post_call` instead of `governance.enforce_post_call`
4. `session.complete()` — mark the workflow as successfully finished

## What you get after migration

| Artifact | Before | After |
|----------|--------|-------|
| Invocation audit artifact | One per call | One per call (unchanged) |
| Workflow artifact | None | One per session (status + step checksums) |
| Session ID | None | UUID correlating all steps |
| Lifecycle state | None | `OPEN → COMPLETED / FAILED / CANCELED` |

## Verifying the migration

After migrating, assert:

```python
artifact = session.workflow_artifact
assert artifact["status"] == "COMPLETED"
assert len(artifact["steps"]) == <your step count>
```

## Example files

- `examples/migration/invocation_only.py` — the before pattern (2 independent calls)
- `examples/migration/workflow_adoption.py` — the after pattern (same 2 calls under a session)

## Error handling

`GovernanceSession.__exit__` never suppresses exceptions. If your model call raises,
the session transitions to `FAILED`, emits a workflow artifact with `status: FAILED`,
and re-raises the original exception. No special handling needed.

## Getting a starter scaffold

If you are starting fresh rather than migrating:

```bash
aigc workflow init --profile minimal
cd governance
python workflow_example.py
```
