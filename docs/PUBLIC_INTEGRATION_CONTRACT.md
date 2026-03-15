# AIGC Public Integration Contract

This document is the primary onboarding reference for integrating AIGC into your system.
It contains a minimal hello-world example, a realistic end-to-end integration, the available
extension points, and a troubleshooting/FAQ section.

---

## 1. Hello AIGC — Minimal Runnable Example

Install and run governance enforcement in under five minutes.

### 1.1 Install

```bash
pip install aigc-sdk
```

Or from source (editable, with dev dependencies):

```bash
git clone https://github.com/nealsolves/aigc
cd aigc
python -m pip install --upgrade pip setuptools wheel
pip install --no-build-isolation -e '.[dev]'
```

### 1.2 Write a policy

Create `policies/hello_policy.yaml`:

```yaml
policy_version: "1.0"
roles:
  - assistant
pre_conditions:
  required:
    - user_id
output_schema:
  type: object
  required:
    - reply
  properties:
    reply:
      type: string
```

### 1.3 Call `enforce_invocation`

```python
from aigc import enforce_invocation, GovernanceViolationError, PreconditionError

invocation = {
    "policy_file": "policies/hello_policy.yaml",
    "model_provider": "openai",
    "model_identifier": "gpt-4o",
    "role": "assistant",
    "input": {"prompt": "Hello!"},
    "output": {"reply": "Hello, I am your assistant."},
    "context": {"user_id": "user-001"},
}

artifact = enforce_invocation(invocation)
print(artifact["enforcement_result"])  # PASS
```

The call returns an audit artifact on success and raises a typed exception on any governance
violation. No silent fallbacks. No best-effort checks.

---

## 2. End-to-End Integration Example

This example demonstrates a realistic integration: a governed async LLM call site using the
`@governed` decorator, a `JsonFileAuditSink` for audit persistence, and a policy with guards
that adjusts behavior based on runtime context.

### 2.1 Policy with guards

Create `policies/analyst_policy.yaml`:

```yaml
policy_version: "1.0"
roles:
  - analyst
pre_conditions:
  required:
    - tenant_id
    - session_id
output_schema:
  type: object
  required:
    - analysis
  properties:
    analysis:
      type: string
post_conditions:
  required:
    - output_schema_valid
guards:
  - when:
      condition: "is_enterprise"
    then:
      tools:
        allowed_tools:
          - name: internal_search
            max_calls: 10
```

### 2.2 Register an audit sink

Register the sink once at application startup, before any governed calls:

```python
from aigc import set_audit_sink
from aigc.sinks import JsonFileAuditSink

set_audit_sink(JsonFileAuditSink("audit/governance.jsonl"))
```

Every enforcement call — PASS and FAIL — automatically emits a JSON line to this file.
Sink failure behavior is configurable: `"log"` mode (default) logs a `WARNING` and allows enforcement to complete; `"raise"` mode propagates sink errors as `AuditSinkError`. Sinks receive a deep copy of the artifact and cannot mutate the caller's copy.

### 2.3 Governed async call site

```python
from aigc.decorators import governed

@governed(
    policy_file="policies/analyst_policy.yaml",
    role="analyst",
    model_provider="anthropic",
    model_identifier="claude-opus-4-6",
)
async def analyze(input_data: dict, context: dict) -> dict:
    # Replace this stub with your actual LLM provider call.
    class _StubLLM:
        async def generate(self, data: dict, ctx: dict) -> str:
            return f"analysis for: {data.get('question', '')}"

    result = await _StubLLM().generate(input_data, context)
    return {"analysis": result}
```

The decorator:
- Captures `input_data` as `input`, `context` as `context`, and the return value as `output`
- Calls `enforce_invocation_async()` transparently
- Propagates governance exceptions unchanged if any gate fails
- Emits an audit artifact to the registered sink on every call

### 2.4 Invoke

```python
output = await analyze(
    {"question": "Summarize Q4 results"},
    {"tenant_id": "acme-corp", "session_id": "sess-42", "is_enterprise": True},
)
print(output["analysis"])  # governed output on PASS
```

### 2.5 Direct enforcement with tool_calls

Use `enforce_invocation` directly when you need explicit control over the invocation dict,
or when wrapping an existing call site that is not async:

```python
from aigc import enforce_invocation, set_audit_sink
from aigc.sinks import JsonFileAuditSink

set_audit_sink(JsonFileAuditSink("audit/governance.jsonl"))

invocation = {
    "policy_file": "policies/analyst_policy.yaml",
    "model_provider": "anthropic",
    "model_identifier": "claude-sonnet-4-6",
    "role": "analyst",
    "input": {"question": "Summarize Q4 results"},
    "output": {"analysis": "Revenue increased 12% QoQ."},
    "context": {
        "tenant_id": "acme",
        "session_id": "sess-42",
        "role_declared": True,
        "schema_exists": True,
    },
    "tool_calls": [
        {"name": "internal_search", "call_id": "tc-1"},
    ],
}

artifact = enforce_invocation(invocation)
print(artifact["enforcement_result"])  # PASS or raises on violation
```

`enforce_invocation` returns the audit artifact dict on PASS and raises a typed exception
(`GovernanceViolationError`, `PreconditionError`, or `SchemaValidationError`) on any gate
failure. The artifact is also emitted to the registered sink automatically.

---

## 3. Extension Points

### 3.1 Custom audit sink

Subclass `AuditSink` to send artifacts to any destination:

```python
from aigc.sinks import AuditSink, set_audit_sink
import json

class SQLiteAuditSink(AuditSink):
    def __init__(self, conn):
        self._conn = conn

    def emit(self, artifact: dict) -> None:
        self._conn.execute(
            "INSERT INTO governance_log (artifact) VALUES (?)",
            [json.dumps(artifact)],
        )

set_audit_sink(SQLiteAuditSink(db_connection))
```

In `"log"` mode (default), any exception raised by `emit()` is caught and logged as a `WARNING`; enforcement continues. In `"raise"` mode, sink errors propagate as `AuditSinkError`. Sinks receive a deep copy; they cannot mutate the returned artifact.

### 3.2 Policy composition via `extends`

Policies can inherit from a base policy using `extends`. Child fields are merged additively
(arrays append, dicts recurse, scalars replace):

```yaml
# policies/child_policy.yaml
extends: "base_policy.yaml"
policy_version: "2.0"
roles:
  - analyst
  - reviewer
```

Load the child policy directly — resolution happens at load time:

```python
from aigc import enforce_invocation
artifact = enforce_invocation({
    "policy_file": "policies/child_policy.yaml",
    ...
})
```

### 3.3 Retry on transient failures

Wrap invocations with `with_retry` for bounded retries on `SchemaValidationError`:

```python
from aigc import with_retry

# retry_policy belongs in the policy YAML, not the invocation payload
artifact = with_retry(invocation)
```

### 3.4 Host tool adapter wrapper

AIGC does not provide a built-in tool execution adapter. The recommended pattern for governing
tool calls on the host side is to build a thin wrapper that constructs the invocation dict,
enforces governance, and then executes the tool:

```python
from aigc import enforce_invocation

def run_tool_with_governance(tool_name: str, params: dict, base_invocation: dict) -> dict:
    governed_invocation = {
        **base_invocation,
        "input": {"tool": tool_name, "params": params},
        "output": {"status": "tool_call_planned"},
        "tool_calls": [{"name": tool_name, "call_id": "generated-1"}],
    }
    enforce_invocation(governed_invocation)
    return execute_tool(tool_name, params)
```

This pattern keeps governance at the SDK boundary and avoids coupling the tool implementation
to the AIGC API.

### 3.5 Planned extension points (not yet available)

The following extension mechanisms appear in architecture documentation but are **not yet
implemented** in the current SDK. Do not attempt to import them:

- `register_validator` — custom postcondition validation functions
- `register_resolver` — dynamic per-invocation policy selection

These are planned for a future release. Use policy guards and composition for dynamic
behavior in the interim.

---

## 4. Troubleshooting / FAQ

### Q: `PolicyLoadError: Policy file not found`

**Cause**: The `policy_file` path in the invocation is incorrect or relative to the wrong
working directory.

**Fix**: Verify the path is correct relative to where you run the process, or use an
absolute path:

```python
from pathlib import Path
invocation["policy_file"] = str(Path(__file__).parent / "policies" / "my_policy.yaml")
```

---

### Q: `PolicyValidationError: Policy does not conform to schema`

**Cause**: The YAML policy file is missing a required field or has an invalid structure.

**Fix**: Validate the policy against the schema:

```python
import json, yaml
from jsonschema import validate
schema = json.load(open("schemas/policy_dsl.schema.json"))
policy = yaml.safe_load(open("policies/my_policy.yaml"))
validate(policy, schema)
```

The schema requires at minimum: `policy_version` and `roles`.

---

### Q: `PreconditionError: Required context key missing`

**Cause**: The `context` dict passed to `enforce_invocation` is missing a key declared in
the policy's `pre_conditions.required` list.

**Fix**: Ensure all required context keys are present before calling enforcement:

```python
invocation["context"]["user_id"] = get_user_id()
```

---

### Q: `SchemaValidationError: Output does not match policy output_schema`

**Cause**: The model output (the `output` dict in the invocation) does not conform to the
JSON Schema defined in the policy's `output_schema` field.

**Fix**: Check that all `required` output fields are present and have the correct types.
Enable retry for transient failures via `retry_policy`.

---

### Q: `GovernanceViolationError: Role not in policy roles`

**Cause**: The `role` field in the invocation is not declared in `policy["roles"]`.

**Fix**: Either add the role to the policy's `roles` list, or correct the `role` value
in the invocation.

---

### Q: `GovernanceViolationError: Tool not in allowed_tools`

**Cause**: The invocation's `tool_calls` list contains a tool not allowed by the policy.

**Fix**: Either add the tool to `policy.tools.allowed_tools`, or remove the unauthorized
tool call from the invocation.

---

### Q: The `@governed` decorator raises `TypeError` about my function signature

**Cause**: The decorator expects the first positional argument to be `input` (a dict) and
the second positional argument or `context` keyword argument to be `context` (a dict).

**Fix**: Ensure your wrapped function signature matches the convention:

```python
@governed(policy_file="...", role="...", model_provider="...", model_identifier="...")
def my_function(input_data: dict, context: dict) -> dict:
    ...
```

---

### Q: Audit artifacts are not appearing in my `JsonFileAuditSink` file

**Cause**: The sink was registered after the first enforcement call, or `set_audit_sink`
was not called at all.

**Fix**: Register the sink once at application startup, before any governed calls:

```python
from aigc import set_audit_sink
from aigc.sinks import JsonFileAuditSink
set_audit_sink(JsonFileAuditSink("audit.jsonl"))
```

---

### Q: Async enforcement is blocking my event loop

**Cause**: Policy file I/O is dispatched to a thread pool via `asyncio.to_thread`. If
you are using `enforce_invocation` (sync) inside an async context, it will block.

**Fix**: Use `enforce_invocation_async` in async contexts:

```python
from aigc import enforce_invocation_async
artifact = await enforce_invocation_async(invocation)
```

---

## 5. Audit Artifact Reference

Every `enforce_invocation` call returns an audit artifact. Stable fields (safe to assert
in tests):

| Field | Description |
| ----- | ----------- |
| `audit_schema_version` | Schema version (e.g., `"1.2"`) |
| `policy_file` | Path to the policy file used |
| `policy_version` | Value of `policy_version` from the policy YAML |
| `policy_schema_version` | JSON Schema draft used to validate the policy |
| `model_provider` | From invocation |
| `model_identifier` | From invocation |
| `role` | From invocation |
| `enforcement_result` | `"PASS"` or `"FAIL"` |
| `metadata` | Dict with `preconditions_satisfied`, `postconditions_satisfied`, `guards_evaluated`, `conditions_resolved`, `schema_validation`, `tool_constraints` |

Volatile fields (do not assert in tests without normalization):

| Field | Description |
| ----- | ----------- |
| `timestamp` | Unix epoch at enforcement time |
| `input_checksum` | SHA-256 of canonical input JSON |
| `output_checksum` | SHA-256 of canonical output JSON |
