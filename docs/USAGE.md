# AIGC Cookbook

This document is task-oriented. Use it when you already know what AIGC is and
want concrete integration patterns.

Use [README.md](../README.md) for the repo overview and
[INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) for the full host-integration
contract.

## Choosing the right API

- Use `enforce_invocation()` when you already have the model output and want
  one-call enforcement.
- Use `enforce_pre_call()` and `enforce_post_call()` when you need to block
  before token spend.
- Use `AIGC(...)` when you want instance-scoped configuration for sinks,
  signers, policy loaders, strict mode, or custom gates.
- Use `@governed(...)` when you want to wrap a model call site directly.

## Recipe 1: Unified enforcement

This is the shortest path when your host assembles a complete invocation.

```python
from aigc import enforce_invocation

artifact = enforce_invocation(
    {
        "policy_file": "policies/base_policy.yaml",
        "model_provider": "anthropic",
        "model_identifier": "claude-sonnet-4-6",
        "role": "assistant",
        "input": {"query": "Summarize incident INC-2847"},
        "output": {"result": "Summary text", "confidence": 0.94},
        "context": {
            "role_declared": True,
            "schema_exists": True,
            "tenant_id": "acme-prod",
        },
    }
)

print(artifact["enforcement_result"])
```

Use this mode when your application treats governance as a post-call boundary
around a complete model interaction.

## Recipe 2: Split enforcement

Use split mode when you want AIGC to authorize before the model call and only
validate output after the model responds.

```python
from aigc import enforce_post_call, enforce_pre_call

pre = enforce_pre_call(
    {
        "policy_file": "policies/base_policy.yaml",
        "model_provider": "anthropic",
        "model_identifier": "claude-sonnet-4-6",
        "role": "assistant",
        "input": {"query": "Summarize incident INC-2847"},
        "context": {
            "role_declared": True,
            "schema_exists": True,
            "tenant_id": "acme-prod",
        },
    }
)

output = model.generate(...)
artifact = enforce_post_call(pre, output)
```

Important split-mode rules:

- `output` is omitted from the pre-call invocation and supplied only in
  `enforce_post_call(...)`.
- `PreCallResult` is single-use. If the token has already been consumed, run
  `enforce_pre_call(...)` again to get a fresh one.
- Unified mode remains the default public behavior; split mode is opt-in.

## Recipe 3: Instance-scoped configuration

Prefer `AIGC(...)` when you want runtime configuration without mutating global
state.

```python
from aigc import AIGC, HMACSigner, JsonFileAuditSink

engine = AIGC(
    sink=JsonFileAuditSink("audit.jsonl"),
    on_sink_failure="raise",
    strict_mode=True,
    signer=HMACSigner(key=b"replace-with-a-real-secret"),
)

artifact = engine.enforce(invocation)
```

This pattern is the best default for applications that need predictable
configuration boundaries.

## Recipe 4: Wrapping a call site with `@governed`

Use the decorator when you want governance attached directly to a function that
performs the model call.

```python
from aigc import governed

@governed(
    policy_file="policies/base_policy.yaml",
    role="assistant",
    model_provider="anthropic",
    model_identifier="claude-sonnet-4-6",
)
def run_model(input_data, context):
    return model.generate(input_data)
```

To use split mode at the decorator boundary:

```python
from aigc import governed

@governed(
    policy_file="policies/base_policy.yaml",
    role="assistant",
    model_provider="anthropic",
    model_identifier="claude-sonnet-4-6",
    pre_call_enforcement=True,
)
def run_model(input_data, context):
    return model.generate(input_data)
```

With `pre_call_enforcement=True`, AIGC runs Phase A before the wrapped function
executes. If Phase A fails, the function is never called.

## Recipe 5: Persisting audit artifacts

Built-in sinks cover the common cases.

### File sink

```python
from aigc import AIGC, JsonFileAuditSink

engine = AIGC(sink=JsonFileAuditSink("audit.jsonl"))
artifact = engine.enforce(invocation)
```

### Callback sink

```python
from aigc import AIGC, CallbackAuditSink

engine = AIGC(sink=CallbackAuditSink(lambda artifact: db.insert(artifact)))
artifact = engine.enforce(invocation)
```

### Custom sink

```python
import json

from aigc import AIGC, AuditSink


class SQLiteAuditSink(AuditSink):
    def __init__(self, conn):
        self._conn = conn

    def emit(self, artifact: dict) -> None:
        self._conn.execute(
            "INSERT INTO governance_log (artifact) VALUES (?)",
            [json.dumps(artifact)],
        )


engine = AIGC(sink=SQLiteAuditSink(db_connection), on_sink_failure="raise")
artifact = engine.enforce(invocation)
```

Notes:

- In `"log"` mode, sink errors are logged and enforcement continues.
- In `"raise"` mode, sink errors propagate as `AuditSinkError`.
- Sinks receive a deep copy, so they cannot mutate the returned artifact.

## Recipe 6: Adding a custom enforcement gate

Custom gates let you inject host-specific checks at one of four insertion
points:

- `pre_authorization`
- `post_authorization`
- `pre_output`
- `post_output`

Example:

```python
from aigc import (
    AIGC,
    EnforcementGate,
    GateResult,
    INSERTION_POST_AUTHORIZATION,
)


class TenantIsolationGate(EnforcementGate):
    name = "tenant_isolation"
    insertion_point = INSERTION_POST_AUTHORIZATION

    def evaluate(self, invocation, policy, context):
        tenant_id = invocation["context"].get("tenant_id")
        allowed_tenant = policy.get("metadata", {}).get("tenant_id")

        if allowed_tenant and tenant_id != allowed_tenant:
            return GateResult(
                passed=False,
                failures=[
                    {
                        "code": "TENANT_MISMATCH",
                        "message": "Invocation tenant does not match policy tenant",
                        "field": "context.tenant_id",
                    }
                ],
                metadata={"tenant_id": tenant_id},
            )

        return GateResult(passed=True, metadata={"tenant_id": tenant_id})


engine = AIGC(custom_gates=[TenantIsolationGate()])
artifact = engine.enforce(invocation)
```

Custom-gate rules:

- Invocation and policy are read-only views.
- Gates return `GateResult`; they do not bypass the pipeline.
- Failures are append-only.
- Registration order is preserved within each insertion point.

## Recipe 7: Loading policies from somewhere other than disk

If policies live in a database, API, or secrets system, implement
`PolicyLoaderBase`.

```python
import yaml

from aigc import AIGC, PolicyLoaderBase, PolicyLoadError


class DatabasePolicyLoader(PolicyLoaderBase):
    def __init__(self, db):
        self._db = db

    def load(self, policy_ref: str) -> dict:
        row = self._db.query(
            "SELECT yaml FROM governance_policies WHERE id = ?",
            [policy_ref],
        )
        if not row:
            raise PolicyLoadError(
                f"Policy {policy_ref} not found",
                details={"policy_ref": policy_ref},
            )
        return yaml.safe_load(row["yaml"])


engine = AIGC(policy_loader=DatabasePolicyLoader(db))
artifact = engine.enforce(
    {
        **invocation,
        "policy_file": "planner-prod",
    }
)
```

The loader returns a raw policy dict. AIGC still performs schema validation,
composition resolution, and policy-date checks after loading.

## Recipe 8: Producing a compliance report from stored artifacts

Once audit artifacts are being persisted to JSONL, the CLI can build a report.

```bash
aigc compliance export --input audit.jsonl
```

Write the report to a file:

```bash
aigc compliance export --input audit.jsonl --output compliance-report.json
```

Include individual artifacts in the report:

```bash
aigc compliance export \
  --input audit.jsonl \
  --output compliance-report.json \
  --include-artifacts
```

This is an offline reporting step over stored evidence, not a runtime
enforcement gate.

## Recipe 9: Handling failures without losing the FAIL artifact

Every governance failure raises a typed exception and attaches the FAIL artifact
at `exc.audit_artifact`.

```python
from aigc import (
    GovernanceViolationError,
    PreconditionError,
    SchemaValidationError,
    enforce_invocation,
)

try:
    enforce_invocation(invocation)
except PreconditionError as exc:
    print(exc.code)
    print(exc.audit_artifact["failure_gate"])
except SchemaValidationError as exc:
    print(exc.audit_artifact["failures"])
except GovernanceViolationError as exc:
    # Role, policy, tool, and related governance failures land here.
    persist_fail_artifact(exc.audit_artifact)
```

Practical rules:

- Handle the most specific exception type you care about.
- Use `exc.audit_artifact` when you need to persist or inspect the FAIL path.
- Treat `AuditSinkError` separately if you run with `on_sink_failure="raise"`.

## Recipe 10: Public API boundary

Only import from the top-level `aigc` package:

```python
from aigc import AIGC, enforce_invocation, JsonFileAuditSink
```

Do not build production integrations on `aigc._internal.*`. That namespace is
private implementation detail and may change between releases.

## Recipe 11: Lineage-aware compliance report

Add `--lineage` to include DAG topology analysis alongside the standard compliance
stats. Useful for auditing agentic workflows where invocations derive from prior
invocations.

```bash
aigc compliance export --input audit_trail.jsonl --lineage
```

Write to a file and combine with `--include-artifacts`:

```bash
aigc compliance export \
  --input audit_trail.jsonl \
  --output compliance-report.json \
  --include-artifacts \
  --lineage
```

The report gains a `"lineage"` key with `total_nodes`, `duplicate_artifacts`,
`root_count`, `leaf_count`, `orphan_count`, `has_cycle`, and checksum lists
`roots`, `leaves`, `orphans`. `total_nodes == total_artifacts - duplicate_artifacts`
always holds.

## Recipe 12: Risk trend monitoring with `RiskHistory`

```python
from aigc import AIGC, RiskHistory

aigc = AIGC()
history = RiskHistory("summarizer-workflow")

for invocation in workflow_invocations:
    audit = aigc.enforce(invocation)
    risk_score = audit.get("risk_score")
    if risk_score is not None:
        history.record(risk_score)

if len(history.scores) >= 2:
    print(f"Trajectory: {history.trajectory()}")
    # "improving" | "stable" | "degrading"
```
